# memSu Auto Plan: Autonomous Advancement Agent

## Goal

Build a conservative autonomous advancement layer on top of memSu's existing
observe, memory, candidate, curator, and policy systems.

The goal is not to let memSu freely act on the user's machine. The goal is to
help local agents keep momentum by repeatedly answering:

- What work lines are currently active?
- What evidence supports that conclusion?
- What is the smallest useful next step?
- Which steps are safe to run automatically, which should be suggested, and
  which require explicit confirmation?

## Core Idea

memSu already knows how to observe local activity and preserve memory with an
evidence trail. The autonomous layer should turn that substrate into a bounded
agenda loop:

```text
observe snapshots / observation findings / memories / pending candidates
        |
        v
workline detection
        |
        v
opportunity generation
        |
        v
policy classification
        |
        v
L0/L1 automatic maintenance or recall
L2 proactive suggestions
L3 confirmation-required action proposals
L4 refusal or safe downgrade
        |
        v
outcome event + future memory candidates
```

The agent should feel proactive, but its authority should remain narrow and
auditable.

## Product Surface

Suggested commands:

```powershell
python -m memsu advance agenda
python -m memsu advance run --since 24h --dry-run
python -m memsu advance run --since 24h --mode suggest
python -m memsu advance run --since 24h --mode maintain
```

Command meanings:

- `advance agenda`: show the latest inferred work lines and next-step
  suggestions without running maintenance.
- `advance run --dry-run`: create and persist an advancement plan without
  running side-effectful work.
- `advance run --mode maintain`: run only L0/L1 tasks such as observe, extract,
  curator, vector rebuild, and scoped recall brief generation.
- `advance run --mode suggest`: produce L2 suggestions and L3 action proposals,
  but do not execute L3 actions.

## Data Model

Initial tables can be added after the design proves useful:

```text
advancement_runs
  run_id
  since
  mode
  started_at
  finished_at
  status
  policy_summary_json
  metadata

worklines
  workline_id
  run_id
  title
  scope
  status
  confidence
  evidence_ids_json
  source_snapshot_ids_json
  summary
  metadata

advancement_opportunities
  opportunity_id
  run_id
  workline_id
  kind
  title
  description
  risk_level
  policy_decision
  status
  evidence_ids_json
  proposal_id
  metadata
```

The first MVP can avoid schema changes by rendering the agenda as an
`observation_finding` plus a `workflow_result` event. Dedicated tables become
useful once the agenda needs history, ranking, and UI review.

## Workline Detection

Worklines are active threads of user intent inferred from evidence, not raw
file paths.

Inputs:

- latest observe snapshot
- recent `observation_findings`
- recent events and workflow results
- pending memory candidates
- open conflict reviews
- curator summaries
- active memories for relevant scopes
- optional current process and Git metadata from V4 probe execution

Examples:

- `project:jinsehua-android` permission and authorization flow debugging
- `project:memSu` V4 inspire-driven observe implementation
- `agent:Hermes` local multi-agent memory supervisor setup
- `workflow:android-release` APK build, signing, and vendor permission checks

Each workline should separate facts from inference:

- facts: directly supported by snapshot rows, evidence refs, commands, tests, or
  summaries
- inference: plausible connection across multiple weak signals
- unknown: missing evidence that would materially change the conclusion

## Opportunity Types

Initial opportunity kinds:

- `review_candidates`: ask the user to accept or reject pending memories.
- `run_maintenance`: run observe, extract, curator, vector rebuild, or backup.
- `inject_context`: prepare scoped recall for a likely next agent session.
- `continue_workline`: suggest the next local task based on the strongest
  active workline.
- `create_skill_candidate`: suggest a skill or adapter when a workflow repeats.
- `resolve_conflict`: surface stale or conflicting memory.
- `request_authorization`: ask for deeper observation or an L3 action only when
  it would materially improve progress.

## Policy Mapping

The advancement agent must call the existing policy engine before any proactive
behavior.

- L0: internal maintenance, dedupe, stale marking, candidate extraction.
- L1: passive recall and context brief generation.
- L2: suggestions, reminders, workflow recommendations, skill recommendations.
- L3: file edits, external messages, task creation, configuration changes,
  cross-agent sharing, hard deletes.
- L4: credential capture, hidden monitoring, keylogging, network interception,
  payment, permission changes.

The default implementation should execute only L0/L1 actions. L2 should be
recorded and shown as suggestions. L3 should create `action_proposals` and wait
for user confirmation. L4 should be denied or downgraded to a safe alternative.

## Agenda Brief

Each run should produce a compact Chinese brief:

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

The brief can be appended to the existing observe markdown file or stored under:

```text
${MEMSU_HOME:-~/.memsu}/advance/YYYY-MM-DD.md
```

## Relationship To Observe

`observe` answers "what can be seen?".

`advance` answers "what should be done next, within policy?".

The two loops should remain separate:

- observe records evidence and findings
- advance ranks worklines and opportunities
- policy gates action
- memory candidates stay review-first

This prevents the observation agent from becoming an unbounded executor.

## MVP Sequence

### Auto 0.1: Agenda Without New Schema

- add `memsu advance agenda`
- read latest snapshots, findings, candidates, conflicts, and summaries
- produce a ranked agenda JSON plus markdown brief
- record one `workflow_result` event for the generated agenda
- do not execute maintenance automatically

### Auto 0.2: L0/L1 Maintenance Mode

- add `advance run --mode maintain`
- run `observe run`, `extract`, `curator run`, and optional `vector rebuild`
- record each maintenance action as an event
- return a brief of what changed

### Auto 0.3: Policy-Gated Suggestions

- add L2 suggestion generation
- call `evaluate_policy` for each suggestion
- respect cooldown and quiet-hour settings
- create L3 action proposals instead of executing L3 actions

### Auto 0.4: Workline History

- introduce dedicated advancement tables
- track workline continuity across runs
- detect repeated workflows and stale worklines
- support agenda review by local agents

### Auto 0.5: Model-Assisted Ranking

- optionally let a trusted OpenAI-compatible endpoint rank opportunities
- keep deterministic fallback ranking
- require evidence ids and policy labels in model output
- never let model output directly execute an action

## Non-Goals

- unrestricted shell execution
- hidden monitoring
- automatic project file edits
- automatic external messages
- automatic acceptance of long-term memory
- reading private chats or credentials
- replacing evidence with model confidence

## Design Bias

The most useful autonomous agent for memSu is not a dramatic executor. It is a
steady local chief of staff: it notices active work, remembers why it matters,
keeps the agenda tidy, runs harmless maintenance, and asks before crossing any
boundary.
