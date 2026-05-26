# memSu Observe

memSu observe is a CLI-first local snapshot job. It does not require a resident
service and does not bind itself to an active Hermes chat session.

## Commands

Run a snapshot:

```powershell
python -m memsu observe run
```

Create a V3 agent-led observe plan without executing local probes:

```powershell
python -m memsu observe agent --dry-run-plan
```

Add `--show-prompt` only when you explicitly want the generated prompt printed;
by default the prompt is recorded by hash so user-owned `inspire.md` content does
not spill into routine logs.

Run the V3 agent planning path with an OpenAI-compatible model endpoint:

```powershell
$env:MEMSU_LLM_ENDPOINT = "http://127.0.0.1:11434/v1/chat/completions"
python -m memsu observe agent --since 24h --authorization metadata
```

The model prompt includes `inspire.md`, so point `MEMSU_LLM_ENDPOINT` only at a
local or otherwise trusted endpoint.

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

Inspect V3 observation audit records:

```powershell
python -m memsu observe runs
python -m memsu observe evidence --run-id <run_id>
python -m memsu observe findings --run-id <run_id>
```

Inspect or initialize the user-editable V3 inspire file:

```powershell
python -m memsu inspire path
python -m memsu inspire show
python -m memsu inspire init
```

## Output

Snapshots are appended to:

```text
${MEMSU_HOME:-~/.memsu}/observe/YYYY-MM-DD.md
```

Each run also writes one row to `observation_snapshots` and one compact
`observation_snapshot` event to the event log.

V3 agent-led observe planning records rows in `observation_runs`,
`evidence_refs`, and `observation_findings`. Long-term memory still goes through
review-first candidates.

The V3 inspire file is user-owned:

```text
${MEMSU_HOME:-~/.memsu}/inspire.md
```

Users can edit it directly to name important project directories, tools,
privacy preferences, and observation priorities. memSu creates a starter
template during `init` and never overwrites it unless `memsu inspire init
--force` is used.

memSu also creates a sibling directory for split inspire notes:

```text
${MEMSU_HOME:-~/.memsu}/inspire.d/
```

Use `inspire.d` when the main file starts to become crowded. For example:

- `inspire.d/projects.md` for important project roots and work areas
- `inspire.d/agents.md` for local agent/tool install state and naming hints
- `inspire.d/privacy.md` for extra boundaries or low-value paths to skip

During V3 agent-led planning, memSu reads `inspire.md` first, then top-level
`inspire.d/*.md` files sorted by file name. Files in this directory are still
user-owned hints, not strict allowlists; the model may inspect other safe local
metadata when there is a good reason and the authorization level allows it.

V4 inspire notes should describe observation directions instead of hard-coded
absolute paths. The default split notes include a local signal surface checklist:

- file modification times in common work roots, project roots, downloads,
  desktop items, and build output areas
- Git records such as recent log, status, and commit stats
- Windows Recent `.lnk` metadata
- PowerShell command history
- current processes and window titles
- local agent session indexes, titles, update times, and summaries
- build/release artifacts such as APKs, zips, protected outputs, market
  packages, and downloaded assets

The agent should discover concrete paths at run time from local evidence.

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
