# memSu V2 Plan: Local Observe Layer

## Direction

memSu V2 turns the project from a Hermes memory provider into a local
multi-agent observation and memory layer.

The core shift:

```text
V1: session memory provider + explicit adapters
V2: scheduled local observer + high-signal daily snapshots + long-term memory
```

Hermes should not perform full-machine observation inside an active chat
session. Hermes should run memSu observe as a cron-style background task, then
use memSu interactively for recall, candidate review, and policy-gated actions.

## Product Shape

memSu V2 has three surfaces:

- memSu Observe: scheduled high-level observation of local agent activity
- memSu Memory: durable events, candidates, accepted memories, audit, forget
- memSu Jobs: CLI commands for observe, recall, review, curation, and export

The observe output belongs to memSu itself:

```text
MEMSU_HOME/
  memsu.db
  policy.yaml
  observe/
    YYYY-MM-DD.md
  backups/
  exports/
```

Without `MEMSU_HOME`, the default path is:

```text
${MEMSU_HOME:-~/.memsu}/observe/YYYY-MM-DD.md
```

## Observe Job

Primary command:

```powershell
python -m memsu observe run
```

The job resolves the current local date in `Asia/Shanghai`, creates the daily
observe file if needed, and appends a short snapshot section:

```markdown
## Snapshot HH:mm

### Current picture
- ...

### Known
- ...

### Inferred
- ...

### Unknown
- ...

### Agent usage by source
- OpenClaw: ...
- Codex: ...
- Claude: ...
- Gemini: ...
- Hermes: ...

### Support opportunity
- ...
```

The snapshot must stay short. It records high-level metadata and summaries, not
raw logs.

## Evidence Policy

V2 observe reads only allowlisted high-level sources.

Initial source families:

- OpenClaw: workspace observe files, memory summaries, agent links, task run
  metadata
- Codex: session index, history, recent session metadata, rollout summaries,
  automation memory summaries
- Claude: recent project, history, or summary files when present
- Gemini: recent session, log, or config status files when present
- Hermes: local CLI availability and scheduled job status when available

Safety rules:

- Do not read or output token, auth, credential, secret, cookie, key, or similar
  sensitive file contents.
- If a sensitive config or credential-like file is encountered, record only that
  it exists and was skipped or redacted.
- Do not copy long raw logs into observe files.
- Separate evidence-backed facts from inference.
- Prefer recent metadata, summaries, file timestamps, task names, statuses, and
  counts over message bodies.

## Data Model

Add first-class observation snapshots to SQLite:

```text
observation_snapshots
  snapshot_id
  local_date
  local_time
  timezone
  current_picture_json
  known_json
  inferred_json
  unknown_json
  agent_usage_json
  support_opportunity
  sources_json
  observe_path
  created_at
```

Each observe run also appends a compact `workflow_result` or new
`observation_snapshot` event into the existing event log. Memory extraction
remains review-first.

## Hermes Integration

Hermes should run the observe job as a background scheduled task, not as a chat
session hook.

Hermes responsibilities:

- trigger `python -m memsu observe run` on a regular schedule through cron,
  Windows Task Scheduler, Hermes automation, or another agent scheduler
- report observe failures without blocking active conversations
- use `python -m memsu recall ...` during user work
- help review pending candidates when asked or when low-noise policy allows
- ask for confirmation before any L3 action

Hermes should not:

- scan all local sources during every chat turn
- inject large observe snapshots into every session
- accept memory candidates automatically without policy and review rules
- require a long-running memSu daemon or HTTP service

## CLI Contract

The CLI is the primary integration surface. Any trusted local agent that can run
commands can use memSu without a resident service.

```powershell
python -m memsu observe run
python -m memsu observe list --date YYYY-MM-DD
python -m memsu observe show <snapshot_id>
python -m memsu observe doctor
python -m memsu recall "query" --scope project:name
python -m memsu candidate list
python -m memsu curator run
```

The HTTP service is intentionally out of the V2 core. Reintroduce it only if CLI
cold-start time, high-frequency recall, concurrency, or host integration becomes
a real bottleneck.

## Discovery Manifest

V2 should support one-time initialization followed by lightweight discovery.
Agents should not need to read the full repository plan or repeat bootstrap when
memSu is already initialized.

Planned files:

```text
${MEMSU_HOME:-~/.memsu}/install.json
${MEMSU_HOME:-~/.memsu}/capabilities.json
```

Manifest templates must stay machine-independent. They should use environment
placeholders instead of host-specific absolute paths:

```json
{
  "initialized": true,
  "mode": "cli-first",
  "service_required": false,
  "home_env": "MEMSU_HOME",
  "entrypoint": "python -m memsu",
  "paths": {
    "home": "${MEMSU_HOME:-~/.memsu}",
    "db": "${MEMSU_HOME:-~/.memsu}/memsu.db",
    "observe_dir": "${MEMSU_HOME:-~/.memsu}/observe",
    "policy": "${MEMSU_HOME:-~/.memsu}/policy.yaml",
    "capabilities": "${MEMSU_HOME:-~/.memsu}/capabilities.json",
    "install_marker": "${MEMSU_HOME:-~/.memsu}/install.json"
  }
}
```

Resolved absolute paths belong in command output, not protocol templates:

```powershell
python -m memsu status
```

The status command may return machine-specific `resolved_paths`, but those
values are runtime facts, not portable configuration.

## Memory Flow

```text
scheduled observe run
  -> allowlisted source readers
  -> redaction and summarization
  -> observe/YYYY-MM-DD.md
  -> observation_snapshots table
  -> compact event log entry
  -> candidate extraction
  -> review
  -> accepted scoped memory
```

The daily observe file is a human-readable operational journal. SQLite remains
the durable query and audit substrate.

## V2 Milestones

### V2.0 Observe Foundation

- add `observe/` path helpers (implemented)
- add machine-independent install and capabilities manifest templates (implemented)
- add observe markdown writer (implemented)
- add `observation_snapshots` table and migrations (implemented)
- add `python -m memsu observe run` (implemented)
- add `python -m memsu status` (implemented)
- implement empty-source safe snapshot generation (implemented)
- document `docs/observe.md` (implemented)

Success check:

- running observe creates or appends `${MEMSU_HOME:-~/.memsu}/observe/YYYY-MM-DD.md`
  and records one snapshot row.
- `python -m memsu status` reports initialized state and resolved runtime paths
  without requiring another bootstrap.

### V2.1 Source Readers

- implement Codex high-level reader (initial metadata reader implemented)
- implement OpenClaw high-level reader (initial metadata reader implemented)
- implement Claude/Gemini presence and recent-file readers (initial readers implemented)
- implement Hermes status reader (initial local status reader implemented)
- enforce denylist and redaction policy (implemented for sensitive-looking paths)

Success check:

- observe summarizes local agent activity without copying raw logs or sensitive
  content.

### V2.2 Hermes Cron Package

- add Hermes cron prompt/template for observe
- add install/doctor checks for observe schedule readiness
- add Windows Scheduled Task compatibility notes for CLI observe jobs (initial script implemented)
- add failure reporting guidance

Success check:

- Hermes can run memSu observe on a schedule without tying it to a chat session.

### V2.3 Review Experience

- expose pending candidates generated from snapshots
- add low-noise reminder policy for pending candidates
- add Hermes review prompt for accepting/rejecting candidates
- connect support opportunity to policy-gated suggestions

Success check:

- observe output can become durable memory through a controlled review flow.

## Open Questions

- What should the default production schedule be once real usage data exists:
  hourly, every few hours, or daily?
- Which scheduler should be documented first: Hermes cron, Codex automation, or
  Windows Task Scheduler?
- Should support opportunity be generated deterministically first, with LLM
  summarization optional later?
- What is the minimal useful Claude/Gemini reader that avoids over-reading local
  histories?
- Should `observe/YYYY-MM-DD.md` be append-only, or should a small "latest
  current picture" block be refreshed at the top?

## Non-goals

- hidden monitoring
- keylogging
- credential capture
- network interception
- full raw transcript warehousing
- replacing user review with automatic memory acceptance
- making Hermes sessions responsible for full-machine observation
- requiring memSu to run as a service before agents can use it
