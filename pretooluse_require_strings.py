#!/usr/bin/env python3
"""
pretooluse_require_strings.py
==============================

A Claude Code PreToolUse hook that allows a tool call only if the most
recent assistant message contains all of a configurable set of required
strings (case-insensitive, ignoring punctuation, in any order).

If all required strings are present:    allow the tool call
If any are missing:                     deny with a message naming what's missing


CLI USAGE
---------

  python3 pretooluse_require_strings.py \\
      --require "first phrase" \\
      --require "second phrase" \\
      --require "third phrase" \\
      --require "fourth phrase"

The --require flag may be repeated any number of times. Each value is one
required substring. Strings can be multi-word; matching ignores case and
punctuation.


SETTINGS.JSON WIRING
--------------------

Linux / macOS:

    {
      "hooks": {
        "PreToolUse": [
          {
            "matcher": "Bash",
            "hooks": [
              {
                "type": "command",
                "command": "python3 /absolute/path/to/pretooluse_require_strings.py --require 'foo' --require 'bar' --require 'baz' --require 'qux'"
              }
            ]
          }
        ]
      }
    }

Windows (use py launcher and forward slashes in paths):

    {
      "hooks": {
        "PreToolUse": [
          {
            "matcher": "Bash",
            "hooks": [
              {
                "type": "command",
                "command": "py C:/Users/you/scripts/pretooluse_require_strings.py --require \"foo\" --require \"bar\" --require \"baz\" --require \"qux\""
              }
            ]
          }
        ]
      }
    }

Change the matcher to "Bash", "Write|Edit", "*", etc. depending on which
tools you want to gate.


HOW IT WORKS
------------

1. Reads the PreToolUse payload from stdin (Claude Code's hook contract).
2. Extracts transcript_path. Opens the transcript JSONL.
3. Walks events from the end backward to find the most recent assistant
   message.
4. Extracts every "text" content block from that message; concatenates.
5. Normalizes: lowercase, strip punctuation, collapse whitespace.
6. For each --require string, normalizes it the same way and checks if
   it appears as a substring of the normalized message.
7. If all required strings are present: exits 0 with no output (allow).
8. If any are missing: emits the deny JSON and exits 0 (Claude Code reads
   the JSON and blocks the tool with the message visible to the agent).


WHY EXIT 0 WITH JSON FOR DENY (NOT EXIT 2)
-------------------------------------------

Exit 2 with stderr is the older "blocking error" pattern. The newer and
preferred pattern is exit 0 with hookSpecificOutput JSON containing
permissionDecision: "deny". The JSON pattern gives a structured reason
that Claude sees as feedback rather than a system error. Exit 2 is also
fine but JSON is more flexible.


CROSS-PLATFORM NOTES
--------------------

- Pure stdlib, no external dependencies.
- All file reads use encoding="utf-8" explicitly.
- stdin/stdout reconfigured to UTF-8 at startup to avoid Windows
  codepage corruption.
- Path handling uses pathlib.Path.
- No POSIX-specific syscalls, no shell escapes.


EXIT CODES
----------

  0 - hook completed successfully (allow OR structured-deny via JSON)
  1 - usage error, transcript not found, or malformed payload
"""

from __future__ import annotations

import argparse
import json
import re
import string
import sys
from pathlib import Path
from typing import Iterator

# Force UTF-8 on stdio regardless of host locale (Windows can default to
# cp1252; transcripts contain UTF-8).
try:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PreToolUse guard: allow only if the last assistant "
                    "message contains all required strings.",
    )
    parser.add_argument(
        "--require",
        action="append",
        required=True,
        help="A required substring. Repeat the flag for each. "
             "Matching is case-insensitive and ignores punctuation.",
    )
    return parser.parse_args()


def read_payload() -> dict:
    """Read the PreToolUse JSON payload from stdin."""
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"ERROR: stdin payload not valid JSON: {e}\n")
        sys.exit(1)


def parse_events(path: Path) -> Iterator[dict]:
    """Yield JSON events from a JSONL file; tolerate partial trailing lines."""
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def find_last_assistant_text(events: list[dict]) -> str:
    """Walk events from the end backward to find the most recent assistant
    message, then concatenate all its text-type content blocks.
    Returns empty string if no assistant message found."""
    for event in reversed(events):
        if event.get("type") != "assistant":
            continue
        message = event.get("message", {})
        content = message.get("content", [])
        if not isinstance(content, list):
            continue
        text_parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n".join(t for t in text_parts if t)
    return ""


# Strip punctuation, collapse whitespace, lowercase — used on both haystack
# and each needle so the comparison is robust to formatting differences.
_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")
_WS_RE = re.compile(r"\s+")


def normalize(s: str) -> str:
    s = s.lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s)
    return s.strip()


def find_missing(haystack: str, needles: list[str]) -> list[str]:
    """Return the list of needles NOT found in haystack (after normalizing
    both sides)."""
    norm_haystack = normalize(haystack)
    missing = []
    for needle in needles:
        norm_needle = normalize(needle)
        if norm_needle and norm_needle not in norm_haystack:
            missing.append(needle)
    return missing


def emit_deny(missing: list[str]) -> None:
    """Emit a PreToolUse deny JSON. Claude Code reads this from stdout and
    blocks the tool call, showing the reason to the agent."""
    missing_list = ", ".join(f'"{m}"' for m in missing)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Tool call blocked: the assistant message preceding this "
                f"tool call did not contain all required phrases. "
                f"Missing: {missing_list}. "
                f"Address each required item in your message before "
                f"attempting the tool call again."
            ),
        }
    }
    sys.stdout.write(json.dumps(output))
    sys.stdout.flush()


def main() -> int:
    args = parse_args()
    required = args.require  # list of strings

    payload = read_payload()
    transcript_path_str = payload.get("transcript_path")
    if not transcript_path_str:
        sys.stderr.write("ERROR: payload missing 'transcript_path'\n")
        return 1

    transcript_path = Path(transcript_path_str)
    if not transcript_path.exists():
        sys.stderr.write(f"ERROR: transcript not found at {transcript_path}\n")
        return 1

    events = list(parse_events(transcript_path))
    last_assistant_text = find_last_assistant_text(events)

    missing = find_missing(last_assistant_text, required)

    if not missing:
        # All required strings present — allow by exiting 0 with no output.
        return 0

    # Some missing — emit deny JSON, still exit 0 (the JSON does the work).
    emit_deny(missing)
    return 0


if __name__ == "__main__":
    sys.exit(main())
