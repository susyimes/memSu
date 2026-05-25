---
name: memory-audit
description: Inspect, correct, archive, or explain memSu memory items.
---

# Memory Audit

Use this skill when the user asks what is remembered, wants memory corrected, or
wants something forgotten.

Workflow:

1. Use `memsu_audit` for broad review or `memsu_recall` for targeted review.
2. Explain memory items with their ids, scopes, and types.
3. If the user corrects a memory, archive the old item with `memsu_forget`.
4. Add the corrected item with `memsu_retain`.
5. Never hide that a memory was archived instead of hard-deleted.

Hard deletion is not part of the default MVP. Archive first; implement hard
delete only behind explicit confirmation and policy support.

