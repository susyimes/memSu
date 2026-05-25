---
name: memory-audit
description: Inspect, correct, archive, or explain memSu memory items.
---

# Memory Audit

Use this skill when the user asks what is remembered, wants memory corrected, or
wants something forgotten.

Workflow:

1. Use `memsu_audit` for broad review or `memsu_recall` for targeted review.
2. Use `memsu_candidates` when reviewing extracted pending memory candidates.
3. Accept a candidate only when it is durable, scoped, and supported by source context.
4. Reject noisy or unsafe candidates with `memsu_reject_candidate`.
5. Explain memory items with their ids, scopes, and types.
6. If the user corrects a memory, archive the old item with `memsu_forget`.
7. Add the corrected item with `memsu_retain`.
8. Never hide that a memory was archived instead of hard-deleted.

Hard deletion is not part of the default MVP. Archive first; implement hard
delete only behind explicit confirmation and policy support.
