# memSu Observe

memSu observe is a CLI-first local snapshot job. It does not require a resident
service and does not bind itself to an active Hermes chat session.

## Commands

Run a snapshot:

```powershell
python -m memsu observe run
```

List snapshots:

```powershell
python -m memsu observe list
python -m memsu observe list --date 2026-05-25
```

Show one snapshot:

```powershell
python -m memsu observe show <snapshot_id>
```

Check readiness:

```powershell
python -m memsu observe doctor
```

## Output

Snapshots are appended to:

```text
${MEMSU_HOME:-~/.memsu}/observe/YYYY-MM-DD.md
```

Each run also writes one row to `observation_snapshots` and one compact
`observation_snapshot` event to the event log.

## Evidence Policy

The observer reads high-level metadata only:

- source root existence
- recent non-sensitive file counts
- file timestamps and sizes
- OpenClaw task database table count when readable
- Hermes config existence without reading config content

It does not copy raw logs or credentials. Paths whose names look like auth,
credential, cookie, password, secret, token, API key, private key, or key files
are skipped and counted as skipped sensitive paths.

## Agent Usage

Any trusted scheduler or agent can run observe:

```powershell
python -m memsu observe run
python -m memsu extract
python -m memsu curator run
```

Hermes, Codex automations, Windows Task Scheduler, or another local runner can
use the same CLI contract.
