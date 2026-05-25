# memSu Curator

The curator keeps long-term memory useful without hard-deleting data.

The MVP curator is deterministic and local. It does not call an LLM.

## What It Does

- archives exact duplicate active memories
- marks old, low-salience memories as `stale`
- rebuilds scope and topic summaries
- creates conflict review entries from pending candidates with conflict hints
- records every curator run

Duplicate and stale handling is conservative:

- duplicates are archived, not deleted
- stale memories are marked `stale`, not deleted
- conflict reviews are queued for inspection

## CLI

Run curation:

```powershell
python -m memsu curator run
```

Use a stricter stale threshold:

```powershell
python -m memsu curator run --stale-days 30 --stale-salience-threshold 0.25
```

Inspect outputs:

```powershell
python -m memsu curator summaries --scope project:memSu
python -m memsu curator conflicts
python -m memsu curator runs
```

## Integration Contract

Curator jobs are CLI-first:

```powershell
python -m memsu curator run
python -m memsu curator summaries
python -m memsu curator conflicts
python -m memsu curator runs
```

There is no resident HTTP curator API in V2. Add one back only after measuring a
real need for a long-running process.

## Hermes Tools

Hermes gets:

- `memsu_curator_run`
- `memsu_curator_status`

The memory supervisor can use these tools during maintenance windows or when the
user asks to inspect memory quality.
