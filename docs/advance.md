# memSu Advance

`advance` is the thin skill/adapter-controlled advancement layer.

It does not make memSu an unrestricted executor. It reads existing memSu
observations and memory-maintenance state, then produces worklines and
policy-gated suggestions.

## Commands

Show the current advancement agenda:

```powershell
python -m memsu advance agenda
```

Plan a stable skill call without running it:

```powershell
python -m memsu advance run --skill observe-to-proposals --dry-run
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

## Current Limits

The first MVP intentionally avoids new schema. It records capability output as
ordinary events and uses existing observation, policy, candidate, and curator
tables.

Dedicated advancement tables can be added later when agenda history, ranking
analytics, or UI review need first-class storage.
