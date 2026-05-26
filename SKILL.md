---
name: claude-web-search-helper
description: Guidelines AND an optional PreToolUse hook for web searches. Use when searching the web, googling, looking something up, researching a topic, or finding documentation. Also use when setting up the install-web-search-hook so WebSearch calls require self-check answers in the preceding message.
user-invocable: false
---

## Search process (apply on every web search)

1. Come up with the simplest possible search variations. Examples:
   - `c++ c wrapper`
   - `cpp c wrapper`
   - `cpp to c function`

2. Search the simplest ones first.

3. If results don't meet requirements, determine what's specifically missing and change or expand accordingly. Do NOT just throw more terms in without cause.

4. Do NOT add years (2025, 2026) unless results are clearly outdated. Adding years excludes older authoritative resources and is likely harmful.

5. Do NOT add filler like "best practices", "modern", "comprehensive", "advanced". These narrow results to blog posts and miss official docs, Stack Overflow, and reference implementations.

## Optional hook: require self-check answers before any WebSearch

This skill ships with `pretooluse_require_strings.py`, a tool-agnostic PreToolUse hook that gates a tool call on the presence of required phrases in the most recent assistant message. Wired against `WebSearch`, it forces the agent to type a short self-check (and its answers) immediately before the call — disrupting the common failure mode where the agent searches to confirm its own hypothesis instead of to discover the answer.

To install the hook in a project (recommended) or globally, follow: [install-web-search-hook.md](./install-web-search-hook.md)
