# memSu Production Hardening

memSu is local-first and CLI-first. The hardening layer focuses on
recoverability, inspection, privacy review, and safe repeated execution by local
agents or schedulers.

## Migration Status

```powershell
python -m memsu migrate status
```

The store records the current schema version in `schema_migrations`.

## Backup

```powershell
python -m memsu backup create
python -m memsu backup create --backup-dir .\backups
```

Backups use SQLite's online backup API.

## Export

```powershell
python -m memsu export json
python -m memsu export json --output .\memsu-export.json
```

Exports write JSON for the core event, memory, candidate, policy, curator, and
vector tables.

## Privacy Review

```powershell
python -m memsu privacy scan
```

The scanner looks for common sensitive patterns in recent events, memories, and
candidates. It redacts previews before returning findings.

## Scheduled Execution

memSu does not require a resident service. Use Hermes cron, Codex automation,
Windows Task Scheduler, or another trusted local scheduler to run CLI jobs such
as:

```powershell
python -m memsu doctor
python -m memsu extract
python -m memsu curator run
```

V2 plans to add `python -m memsu observe run` as another scheduled CLI job.

The deferred HTTP service path should be reconsidered only if CLI cold-start
time, high-frequency recall, concurrency, or host integration becomes a real
bottleneck.

## Sparse Vector Backend

The optional MVP vector backend is dependency-free and sparse-token based.

```powershell
python -m memsu vector rebuild
python -m memsu vector recall "project memory"
```

This is not an embedding model. It is a deterministic local retrieval backend
that can be replaced later by a dense vector store.

## Deferred Service Path

Earlier V1 experiments include local HTTP service code. It is no longer the
default hardening target. Treat it as compatibility code until the project has a
measured need for a resident process.
