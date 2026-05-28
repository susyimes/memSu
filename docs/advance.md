# memSu Advance

`advance` is the thin skill/adapter-controlled advancement layer.

It does not make memSu an unrestricted executor. It reads existing memSu
observations and memory-maintenance state, then produces worklines and
policy-gated suggestions.

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
- reads recent snapshots, findings, candidates, conflicts, summaries, and events
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
