# Install the WebSearch self-check hook

This hook intercepts every `WebSearch` call and **denies it unless the most recent assistant message contains four self-check phrases verbatim**. The goal is to disrupt hypothesis-confirming searches — the agent must answer a small set of questions before each search, in the message right before the tool call.

The script that does the checking is `pretooluse_require_strings.py` (shipped alongside this file). It is tool-agnostic — the `WebSearch` gating lives entirely in the hook's `matcher` field in your settings file.

---

## Choose a scope

| Scope | File | When to use |
|---|---|---|
| **Project (recommended)** | `<project>/.claude/settings.local.json` | This is the default. Keeps the hook scoped to one project so you can opt in per-repo without affecting unrelated work. `settings.local.json` is gitignored by default. |
| Global (alternative) | `~/.claude/settings.json` | Use only if you want the hook active in every Claude Code session on this machine. Not the default — global activation can be disruptive in projects where it isn't wanted. |

> Filename note: the project-scope file is named **`settings.local.json`** (not `local_settings.json`). The `.local.` segment is what makes it the per-user override.

---

## Install (project scope — default)

In your project root, edit (or create) `.claude/settings.local.json` and merge the following into the existing JSON. **Do not replace the whole file** if it already has hooks or other settings — merge into the `hooks.PreToolUse` array.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "WebSearch",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /home/aikenyon/.claude/skills/claude-web-search-helper/pretooluse_require_strings.py --require \"Is this query describing a goal or naming a candidate answer? If naming an answer, what was the goal?\" --require \"Have you enumerated the categories of solutions or jumped to one?\" --require \"Is there a known authoritative domain that should be in allowed_domains?\" --require \"Would WebFetch on a known URL beat a search here?\""
          }
        ]
      }
    ]
  }
}
```

**Replace the absolute path** to the script if you installed the skill somewhere other than `~/.claude/skills/claude-web-search-helper/`.

If you also want the hook on `WebFetch`, change the `matcher` to `"WebSearch|WebFetch"`.

---

## Install (global scope — alternative, not default)

Same JSON snippet, but merged into `~/.claude/settings.json` instead of the project file. Hook will fire on every WebSearch in every project. Not recommended unless you want truly universal enforcement.

---

## What the agent must do, going forward

Before any `WebSearch` call, the agent's preceding message must contain all four required phrases verbatim (case- and punctuation-insensitive), with the agent's own answers immediately after each:

1. Is this query describing a goal or naming a candidate answer? If naming an answer, what was the goal?
2. Have you enumerated the categories of solutions or jumped to one?
3. Is there a known authoritative domain that should be in allowed_domains?
4. Would WebFetch on a known URL beat a search here?

If any phrase is missing, the hook denies the call and tells the agent which phrases are missing.

---

## Verify it works

After installing, ask the agent to perform a web search without any preceding self-check. The tool call should be blocked with a message listing all four missing phrases. Then ask the agent to retry with the questions+answers in its message — the search should go through.

If the hook does not fire at all, open `/hooks` in Claude Code once to reload the settings watcher, or restart the session.

---

## Remove

Delete the matching block from your `hooks.PreToolUse` array in whichever settings file you installed it into.
