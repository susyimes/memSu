# memSu Advance

`observe` answers what can be seen. `advance` answers what should be done next,
within policy.

The first implementation is intentionally small: no new schema, no shell
execution, no automatic file edits, and no automatic memory acceptance. It reads
existing memSu state, produces a compact agenda, policy-classifies each
opportunity, writes a markdown brief, and records the result as a
`workflow_result` event.

## MVP Command

```powershell
python -m memsu advance agenda
```

Optional controls:

```powershell
python -m memsu advance agenda --limit 5
python -m memsu advance agenda --no-record
```

## Inputs

The agenda reads only existing state:

- latest `observation_snapshots`
- recent `observation_findings`
- pending `memory_candidates`
- open `conflict_reviews`
- recent `memory_summaries`
- recent events, especially Codex and Git events

This keeps Auto 0.1 compatible with the current database and lets later
versions introduce dedicated advancement tables only when history, ranking, or
UI review need them.

## Deterministic Workline Detector

Worklines are active threads of work inferred from evidence, not raw paths.

The first detector ranks one to five worklines from:

- Codex session summaries in observe snapshots
- Git events and repository metadata
- observe support opportunities and active agent usage
- pending candidates and conflict reviews
- curator summaries

Each workline should include:

- `title`
- `scope`
- `confidence`
- `summary`
- `facts`
- `unknowns`
- `evidence`

The detector must keep facts and inference separate. Weak evidence can create a
low-confidence workline; it cannot become a fact.

## Opportunity Generator

The first generator emits these kinds:

- `review_candidates`: ask the user to accept or reject pending memories.
- `run_maintenance`: suggest the safe maintenance loop.
- `continue_workline`: suggest the smallest useful next step for the strongest
  active workline.
- `create_skill_candidate`: suggest a skill or adapter when repeated work
  appears.
- `resolve_conflict`: surface open memory conflicts.

Each opportunity calls the existing policy engine before it is returned.

Policy behavior:

- L0 and L1 may be recorded as allowed maintenance/context opportunities, but
  `agenda` does not execute them.
- L2 is returned as a suggestion only.
- L3 is persisted as an action proposal and waits for user confirmation.
- L4 is denied or downgraded to a safe alternative.

## Brief Output

`advance agenda` writes a markdown brief to:

```text
${MEMSU_HOME:-~/.memsu}/advance/YYYY-MM-DD.md
```

The brief shape is:

```markdown
# memSu 推进简报

## 当前主线
- ...

## 证据
- ...

## 建议下一步
- ...

## 自动维护
- ...

## 待确认动作
- ...

## 未知
- ...
```

The command also prints JSON so Hermes, Codex, or another local agent can
consume it directly.

## Event Recording

By default, the agenda records one `workflow_result` event with:

- `source_agent`: `advance`
- `source_type`: `agenda`
- `event_type`: `workflow_result`
- `content_ref`: brief path
- metadata containing worklines, opportunities, policy summary, and input
  counts

Use `--no-record` for inspection without adding the agenda workflow event.
Policy evaluation still records proposals because L2/L3 behavior is part of the
policy audit trail.

## Relationship To Agent-Led Observe

Auto 0.1 does not implement the V3/V4 safe toolbelt execution loop. That remains
the next major step after the deterministic agenda is useful.

The intended sequence is:

1. `advance agenda`: deterministic worklines and suggestions from existing
   state.
2. `advance run --mode maintain`: policy-limited L0/L1 maintenance.
3. `observe agent`: bounded read-only probe execution with evidence refs.
4. model-assisted ranking, still evidence-bound and policy-gated.

## Deferred Toolbelt Execution Tasks

The real `observe agent` execution layer should land after `advance agenda`
proves useful. The work should be split into narrow, reviewable pieces:

- implement read-only probe functions for local time, roots, recent paths, Git
  repos, Windows Recent entries, visible processes, sanitized process commands,
  installed apps, common app paths, shell history summaries, and safe text
  excerpts
- reject credential-like paths before reads and record skipped evidence counts
- persist every important probe result as an `evidence_ref`
- convert supported claims into `observation_findings`
- propose memory candidates only through the review-first candidate table
- render an observe brief that separates facts, inferences, unknowns,
  suggestions, and skipped/redacted evidence
- keep model output advisory: it can choose tools and rank findings, but it
  cannot directly mutate files, accept memory, or execute external actions
