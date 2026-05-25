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
python -m memsu status
python -m memsu doctor
python -m memsu observe run
python -m memsu extract
python -m memsu curator run
```

The deferred HTTP service path should be reconsidered only if CLI cold-start
time, high-frequency recall, concurrency, or host integration becomes a real
bottleneck.

Install a user-level Windows Scheduled Task for daily observe:

```powershell
.\scripts\install_windows_task.ps1 -DailyAt 09:00
# preview only:
.\scripts\install_windows_task.ps1 -WhatIf
```

Remove it:

```powershell
.\scripts\uninstall_windows_task.ps1
```

## Sparse Vector Backend

The optional MVP vector backend is dependency-free and sparse-token based.

```powershell
python -m memsu vector rebuild
python -m memsu vector recall "project memory"
```

This is not an embedding model. It is a deterministic local retrieval backend
that can be replaced later by a dense vector store.

## Deferred Service Path

The V1 local HTTP service path has been removed from the default project. Add a
resident process again only after measuring a real need for high-frequency
recall, concurrency control, caching, or host integration.
