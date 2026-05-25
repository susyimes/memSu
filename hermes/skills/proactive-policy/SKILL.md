---
name: proactive-policy
description: Apply memSu risk levels before proactive suggestions or actions.
---

# Proactive Policy

memSu separates memory from action.

Allowed without confirmation:

- L0 internal maintenance such as dedupe, summaries, and stale flags
- L1 passive recall injected into context

Allowed with rate limits:

- L2 suggestions that help the user notice relevant prior context

Requires explicit confirmation:

- L3 file edits
- L3 external messages
- L3 task creation
- L3 config changes
- L3 cross-agent sharing of sensitive context

Forbidden or restricted:

- L4 credential capture
- L4 hidden surveillance
- L4 payment or permission changes
- L4 destructive memory deletion without confirmation

When unsure, downgrade the behavior to a suggestion and ask for confirmation
before taking external action.

Use `memsu_policy_check` before proactive behavior that might affect files,
messages, tasks, configuration, cross-agent context, permissions, or sensitive
information. Use `memsu_policy_proposals` to review pending confirmations.
