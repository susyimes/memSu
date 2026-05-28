# memSu Auto Plan: Skill/Adapter-Controlled Advancement

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

The design direction is skill/adapter-controlled: auto mode should not grow a
large private toolbox. It should coordinate stable skills and adapters that have
clear inputs, outputs, safety boundaries, and audit trails.

## Core Idea

memSu already knows how to observe local activity and preserve memory with an
evidence trail. The autonomous layer should act as a small scheduling kernel
over reusable capability units:

```text
adapters
  produce structured facts, events, evidence refs, and findings

skills
  run repeatable local workflows such as observe -> proposals

auto kernel
  selects which skill/adapter to call, ranks outputs, checks policy, records outcomes
```

The bounded agenda loop becomes:

```text
observe snapshots / adapter events / skill outputs / memories / pending candidates
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

## Control Model

Auto mode has three responsibilities:

- Select: decide which stable skill or adapter is relevant to the current
  evidence.
- Gate: evaluate each proposed action through the policy engine.
- Record: persist agenda, suggestions, action proposals, and outcomes.

Auto mode should not directly implement source-specific probing, project repair,
message sending, memory acceptance, or file mutation. Those capabilities must
live behind skills or adapters with explicit contracts.

Capability boundaries:

- Adapters convert an external or local signal into memSu events, evidence, or
  findings. They should be deterministic where possible.
- Skills orchestrate multi-step workflows for Hermes or another agent. They may
  call several memSu CLI commands, but must obey policy and output a structured
  proposal brief.
- The auto kernel treats skills/adapters as units of work. It can call
  low-risk units, rank their outputs, and ask for confirmation when a unit would
  cross into L3 behavior.

## Skill And Adapter Contracts

Every auto-callable skill or adapter should declare:

- name and version
- purpose
- inputs
- outputs
- allowed risk level
- forbidden actions
- required memSu commands
- evidence requirements
- idempotency expectations
- review behavior

Suggested output shape:

```json
{
  "ok": true,
  "capability": "observe-to-proposals",
  "risk_level": "L2",
  "worklines": [],
  "suggestions": [],
  "action_proposals": [],
  "evidence": [],
  "skipped": []
}
```

Adapters should write structured events through `python -m memsu adapter ...`
or dedicated future adapter commands. Skills should return a brief that can be
recorded as a `workflow_result` event.

## Reference Skill: Observe To Proposals

The first stable auto-callable skill should be `observe-to-proposals`.

Purpose:

- run or read the latest memSu observation
- summarize active worklines
- produce only L2 suggestions and L3 action proposals
- never edit files, send messages, accept memory, or execute project changes

Default workflow:

```text
observe run
  -> candidate list
  -> curator conflicts
  -> recent findings / snapshots
  -> policy evaluate for each suggestion
  -> proposal brief
```

Allowed automatic behavior:

- L0 internal maintenance such as observe snapshot creation
- L1 passive recall and context brief generation
- L2 suggestion recording within rate limits

Disallowed behavior:

- accepting or rejecting memory candidates
- modifying project files
- sending external messages
- changing tool configuration
- reading private content beyond the observe authorization level

This skill gives the auto kernel a safe first move: "look at what memSu can see,
then propose next steps." It is intentionally less powerful than a repair or
coding agent.

## Product Surface

Suggested auto-kernel commands:

```powershell
python -m memsu advance agenda
python -m memsu advance run --since 24h --dry-run
python -m memsu advance run --since 24h --skill observe-to-proposals
python -m memsu advance run --since 24h --adapter git-activity
```

Command meanings:

- `advance agenda`: show the latest inferred work lines and next-step
  suggestions without calling new capabilities.
- `advance run --dry-run`: choose candidate skills/adapters and persist the plan
  without calling them.
- `advance run --skill observe-to-proposals`: call a stable workflow skill and
  record its proposal brief.
- `advance run --adapter git-activity`: call a stable signal adapter and record
  the resulting events/findings.

The command surface can also support presets later, such as `--preset daily`,
but presets should expand into explicit skill/adapter calls rather than hidden
agent behavior.

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
  capability_calls_json
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
  capability_name
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
- recent skill output briefs
- pending memory candidates
- open conflict reviews
- curator summaries
- active memories for relevant scopes
- adapter output from V4 probe execution

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
- `run_skill`: call a stable workflow skill such as `observe-to-proposals`.
- `run_adapter`: call a stable signal adapter such as Git activity or shell
  history summarization.
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

The default implementation should automatically call only capabilities whose
declared maximum risk is L0/L1. L2 skill outputs should be recorded and shown as
suggestions. L3 outputs should create `action_proposals` and wait for user
confirmation. L4 should be denied or downgraded to a safe alternative.

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

`skill/adapter` answers "how is this repeatable capability safely performed?".

The two loops should remain separate:

- observe records evidence and findings
- adapters create structured events and facts
- skills orchestrate bounded workflows
- advance ranks worklines and chooses capability calls
- policy gates action
- memory candidates stay review-first

This prevents the observation agent from becoming an unbounded executor.

## MVP Sequence

### Auto 0.1: Observe-To-Proposals Skill

- add a Hermes `observe-to-proposals` skill
- define its inputs, outputs, policy boundary, and forbidden actions
- use existing memSu CLI commands to produce a proposal brief
- record the brief as a `workflow_result` event when invoked by an agent

### Auto 0.2: Agenda Without New Schema

- add `memsu advance agenda`
- read latest snapshots, findings, skill briefs, candidates, conflicts, and
  summaries
- produce a ranked agenda JSON plus markdown brief
- do not call capabilities automatically

### Auto 0.3: Skill/Adapter Invocation

- add `advance run --skill <name>` and `advance run --adapter <name>`
- maintain a local registry of auto-callable capabilities (implemented for
  `observe-to-proposals` and `git-activity`)
- reject unknown capabilities unless explicitly allowed by the user
- record every call and output as an event

### Auto 0.4: Policy-Gated Suggestions

- call `evaluate_policy` for each skill or adapter output
- respect cooldown and quiet-hour settings
- create L3 action proposals instead of executing L3 actions

### Auto 0.5: Workline History

- introduce dedicated advancement tables (implemented)
- track workline continuity across runs (implemented)
- detect repeated workflows and stale worklines (implemented with deterministic
  suggestions)
- support agenda review by local agents (implemented through `advance runs`,
  `advance worklines`, and `advance opportunities`)

### Auto 0.6: Model-Assisted Ranking

- optionally let a trusted OpenAI-compatible endpoint rank opportunities
  (implemented behind `--rank-method llm`)
- keep deterministic fallback ranking (implemented)
- require evidence ids and policy labels in model output (implemented)
- never let model output directly execute an action (implemented)

## Non-Goals

- unrestricted shell execution
- hidden monitoring
- automatic project file edits
- automatic external messages
- automatic acceptance of long-term memory
- direct source-specific probing inside the auto kernel
- reading private chats or credentials
- replacing evidence with model confidence

## Design Bias

The most useful autonomous agent for memSu is a small kernel surrounded by
trustworthy skills and adapters. It notices active work, remembers why it
matters, calls bounded capabilities, keeps the agenda tidy, and asks before
crossing any boundary.
