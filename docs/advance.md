# memSu Advance

`advance` is the thin skill/adapter-controlled advancement layer.

It does not make memSu an unrestricted executor. It reads existing memSu
observations and memory-maintenance state, then produces worklines and
policy-gated suggestions. It also reads the human inbox at
`${MEMSU_HOME:-~/.memsu}/inbox/` and the user-owned Markdown task board at
`${MEMSU_HOME:-~/.memsu}/tasks.md`. Inbox files become `organize_inbox`
suggestions; open tasks become first-class worklines. Claimed tasks remain
worklines, with `claimed_by` and `claim_until` shown as coordination evidence.

Agents should read `${MEMSU_HOME:-~/.memsu}/AGENTS.md` before using `advance`;
the guide explains the local read order, task claim flow, evidence recording,
and risk boundaries.

The R5 direction is model-led rather than checklist-led: `advance run` should
eventually hand the model the current context, task board, evidence, agenda,
history, and capability registry, then let it choose the next low-risk action.
The hard constraints are risk level, evidence, audit record, and rollback
description, not a fixed order of steps.

## Commands

Show the current advancement agenda:

```powershell
python -m memsu advance agenda
python -m memsu advance agenda --rank-method llm
```

Plan a stable skill call without running it:

```powershell
python -m memsu advance run --dry-run
python -m memsu advance run --dry-run --rank-method llm
python -m memsu advance run --skill observe-to-proposals --dry-run
```

List registered auto-callable skills and adapters:

```powershell
python -m memsu advance capabilities
python -m memsu advance capabilities --kind skill
python -m memsu advance capabilities --kind adapter
```

Run the first supported advancement skill:

```powershell
python -m memsu advance run --skill observe-to-proposals
```

Use a bounded evidence home for tests or controlled probes:

```powershell
python -m memsu advance run --skill observe-to-proposals --evidence-home .\fixtures\home
```

Skip creating a fresh observe snapshot and use existing memSu records:

```powershell
python -m memsu advance run --skill observe-to-proposals --skip-observe
```

Run the first supported advancement adapter:

```powershell
python -m memsu advance run --adapter git-activity --repo-path .
```

Inspect recorded advancement history:

```powershell
python -m memsu advance runs
python -m memsu advance worklines
python -m memsu advance opportunities
```

## What `observe-to-proposals` Does

- optionally runs `observe run`
- reads recent snapshots, inbox files, task board items, findings, candidates,
  conflicts, summaries, and events
- derives active worklines
- creates L2 suggestions
- evaluates those suggestions through policy
- records the final proposal brief as a `workflow_result` event

It does not:

- edit files
- send messages
- accept or reject memory candidates
- change configuration
- execute L3 actions

## Capability Registry

`advance` only runs registered capabilities. The current registry contains:

- `observe-to-proposals`: an L2 skill that produces policy-gated suggestions.
- `git-activity`: an L1 adapter that records a read-only Git repository
  activity snapshot through the existing git adapter.

Unknown skills or adapters are rejected by default.

## Current Limits

The current implementation records advancement history and uses deterministic
ranking by default. If `--rank-method llm` is passed and `MEMSU_LLM_ENDPOINT` is
configured, memSu asks an OpenAI-compatible endpoint to rank suggestions. If the
endpoint is missing or fails, ranking falls back to the deterministic rule path.

Today's `advance run` still needs the caller to choose the capability and carry
out any verification/state update loop around it. It does not yet perform a
single model-led execution turn that autonomously selects a low-risk action and
writes the result back.

Task board items with `done` or `dropped` status are ignored by the active
agenda. Other tasks can become `manual_task_board` worklines, and task-derived
suggestions cite the task id as evidence.

`advance` does not claim tasks by itself. An agent that decides to work on a
task should call `python -m memsu task claim <task_id> --agent <name>` first,
then record workflow evidence and update status when appropriate.

Unprocessed inbox files are surfaced separately as `human_inbox` worklines and
`organize_inbox` suggestions. The agent should inspect those files, promote
concrete tasks with `inbox promote`, and let promotion archive the source file.

## History Tables

The current implementation records advancement history in:

- `advancement_runs`
- `worklines`
- `advancement_opportunities`

`advance run --dry-run`, `advance run --skill ...`, and `advance run --adapter
...` all write an advancement run. Skill runs also persist derived worklines and
opportunities.

Repeated active worklines are surfaced as `create_skill_candidate`
opportunities when they cross the configured recurrence threshold.
