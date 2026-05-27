---
name: observe-to-proposals
description: Run memSu observe and turn the newest snapshot into Chinese, policy-gated suggestions only; record the brief as a workflow adapter event when appropriate.
---

# Observe To Proposals

Use this skill when Hermes should inspect the latest memSu observation context and propose next steps without taking external or project-changing action. This is the standard “memSu observe → 仅提议” flow.

## Safety Contract

- Default output is L2 suggestions only.
- Do not accept/reject candidates, archive memories, edit files, create tasks, send messages, or change configuration unless the user explicitly asks for that specific L3 action.
- Do not inspect skipped sensitive paths. Treat skipped paths as a privacy-boundary signal.
- Use metadata and bounded summaries by default; do not read credentials, tokens, cookies, private keys, or private chat bodies.
- Separate verified facts, inferences, unknowns, and suggestions.

## Default Read-Only Workflow

Run from the memSu repository or any environment where `python -m memsu` resolves correctly.

1. Verify memSu health:

```bash
python -m memsu status
python -m memsu observe doctor
```

Confirm:

- `ok: true`
- `schema_version == expected_schema_version`
- `mode: cli-first`
- `service_required: false`

2. Create or inspect one fresh deterministic observe snapshot:

```bash
python -m memsu observe run
python -m memsu observe list --limit 3
```

3. Inspect the generated daily markdown path from the snapshot. Prioritize these sections:

- `当前图景`
- `已确认`
- `推断`
- `未知`
- `最近 Agent 会话摘要`
- `各来源 Agent 使用情况`
- `支持建议`

4. Optionally inspect review surfaces without mutating them:

```bash
python -m memsu audit --limit 30
python -m memsu candidate list --limit 20
python -m memsu observe findings --limit 10
python -m memsu policy proposals --limit 20
```

5. Convert observations into suggestions:

- Recent agent summaries → concrete “I can help with …” options.
- Duplicate/noisy memories → cleanup proposals, not automatic cleanup.
- Repeated workflows → candidate Hermes skills or memSu adapters.
- Stale or inactive sources → adapter coverage suggestions.
- Pending candidates/conflicts/proposals → review suggestions.

## Policy-Gated Actions

When a suggestion becomes an action:

- Memory archive/forget: L3, requires explicit user request.
- Candidate accept/reject: L3, requires explicit user request.
- File edits or repo changes: L3, requires explicit user request.
- External messages, task creation, cross-agent sensitive sharing: L3/L4 depending on sensitivity.
- Hard delete, credential capture, hidden monitoring, payment/permission changes: forbidden or restricted.

If the user explicitly asks for a cleanup action, prefer archive over hard delete and back up first for bulk changes:

```bash
python -m memsu backup create
python -m memsu audit --scope doctor --status active --limit 100
python -m memsu forget <item_id> --reason "archive duplicate/noisy memory after user request"
python -m memsu audit --scope doctor --status active --limit 100
```

For repeated doctor smoke-test memories, keep at most the newest active copy unless the user asks to archive all copies.

## Adapter Recording

After producing a proposal brief or completing an explicitly approved cleanup, record the outcome as a workflow event when useful:

```bash
python -m memsu adapter workflow \
  --name observe-to-proposals \
  --status completed \
  --summary "<Chinese summary of snapshot id, suggestions, and any approved actions>" \
  --sensitivity normal
```

This records that the advisory loop ran without turning suggestions into hidden actions.

## Output Brief

Return Chinese output with this structure:

```markdown
# memSu 观察后提议

## 已执行
- ...commands or surfaces inspected...

## 当前主线
- ...

## 证据
- snapshot_id=...
- observe_path=...
- candidate/proposal/finding ids when relevant

## 建议
- [L2] ...

## 待确认
- [L3] ...

## 候选记忆/清理机会
- ...

## 未知与边界
- ...
```

Keep every important claim tied to a snapshot id, run id, evidence id, finding id, event id, memory id, or CLI result.

## Verification Checklist

- [ ] `status` and `observe doctor` are healthy.
- [ ] A snapshot id and observe markdown path are available.
- [ ] Suggestions are separated from confirmed facts.
- [ ] No L3 action was executed unless explicitly requested.
- [ ] Sensitive skipped paths were not inspected.
- [ ] If a workflow event was recorded, its event id is reported.
