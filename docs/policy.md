# memSu Proactive Policy

memSu separates memory from action.

The MVP policy engine is intentionally conservative. It records proposed actions,
classifies them into risk levels, and persists a policy event log.

## Risk Levels

- L0: automatic internal maintenance
- L1: passive recall or context injection
- L2: proactive suggestions
- L3: actions requiring explicit confirmation
- L4: forbidden or restricted actions

## Examples

Allowed and recorded:

```powershell
python -m memsu policy evaluate --action-type maintenance --description "dedupe memory candidates"
python -m memsu policy evaluate --action-type recall --description "inject scoped context"
```

Suggestion-level:

```powershell
python -m memsu policy evaluate --action-type suggestion --description "suggest creating a skill from a repeated workflow"
```

Suggestion controls:

- L2 suggestions are rate-limited by action type.
- L2 suggestions can be deferred during quiet hours.
- Proposal metadata can override quiet-hour state for a single evaluation.

Defaults are read from `MEMSU_HOME\policy.yaml` or `~\.memsu\policy.yaml`:

```yaml
defaults:
  proactive_external_actions: false
  cross_agent_sensitive_sharing: false
  hard_delete_without_confirmation: false
  suggestion_cooldown_seconds: 300
  quiet_hours_active: false
```

Per-proposal quiet-hour override:

```powershell
python -m memsu policy evaluate --action-type suggestion --description "suggest a reminder" --metadata "{""quiet_hours_active"":true}"
```

Requires confirmation:

```powershell
python -m memsu policy evaluate --action-type send_message --description "send a summary to a chat"
python -m memsu policy proposals --status pending_confirmation
python -m memsu policy decide <proposal_id> --decision approve --reason "user confirmed"
```

Denied by default:

```powershell
python -m memsu policy evaluate --action-type credential_capture --description "capture secrets from terminal output"
```

## Integration Contract

Policy checks are CLI-first:

```powershell
python -m memsu policy evaluate --action-type suggestion --description "..."
python -m memsu policy proposals
python -m memsu policy decide <proposal_id> --decision approve
python -m memsu policy events
```

There is no resident HTTP policy API in V2. Add one back only if CLI latency,
concurrency, or host integration requires it.

## Hermes Tools

Hermes gets:

- `memsu_policy_check`
- `memsu_policy_proposals`

The memory supervisor should call `memsu_policy_check` before proactive actions.
L3 actions must not execute until the user confirms them. L4 actions should be
refused or downgraded to safe alternatives.
