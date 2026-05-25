# memSu Production Hardening

memSu is local-first. The MVP hardening layer focuses on recoverability,
inspection, privacy review, and safe service operation.

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

## Service Supervision

Start:

```powershell
.\scripts\start_service.ps1
```

Status:

```powershell
python -m memsu service status
.\scripts\status_service.ps1
```

Stop:

```powershell
python -m memsu service stop
```

The MVP uses a PID file under `MEMSU_HOME` or `~/.memsu`.

## Structured Logs

The local HTTP service emits JSON logs to stderr for server startup and response
events. `start_service.ps1` writes stderr to `memsu.err.log`.

## Sparse Vector Backend

The optional MVP vector backend is dependency-free and sparse-token based.

```powershell
python -m memsu vector rebuild
python -m memsu vector recall "project memory"
```

This is not an embedding model. It is a deterministic local retrieval backend
that can be replaced later by a dense vector store.

## HTTP API

- `POST /backup/create`
- `POST /export/json`
- `GET /privacy/scan`
- `GET /migrate/status`
- `POST /vector/rebuild`
- `POST /vector/recall`
