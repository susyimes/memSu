---
name: memory-capture
description: Capture durable user, project, workflow, and agent memory into memSu.
---

# Memory Capture

Use this skill when a conversation reveals durable information worth preserving
across sessions or agents.

Capture:

- stable user preferences
- explicit project rules
- architecture or product decisions
- repeated workflow lessons
- recurring failure patterns
- candidates for reusable skills

Do not capture:

- temporary task progress
- sensitive information without clear need
- secrets, tokens, credentials, or private messages
- guesses that lack evidence
- one-off implementation details with no future value

Use `memsu_retain` with a specific `type`, `scope`, `confidence`, and `salience`.
Prefer project or agent scopes over global memory unless the memory is truly
global to the user.

