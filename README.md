# memSu

memSu is a local memory supervisor for Hermes and other desktop agents.

The goal is not to clone memU as a library. The goal is to make a dedicated
Hermes agent act as a long-running memory supervisor that observes local agents,
workflows, command history, project activity, and task outcomes, then turns
reliable observations into scoped, auditable long-term memory.

## Core Idea

Most agent memory systems only remember one conversation inside one runtime.
memSu is designed around a different assumption:

> The useful memory boundary is the user's local work environment, not a single
> chat session or a single agent.

memSu should be able to observe and support:

- Hermes conversations and memory hooks
- Codex sessions and coding workflows
- Gemini, Kimi, Claude, or other CLI agents
- shell commands and workflow runs
- git commits, diffs, branches, and project decisions
- generated artifacts, logs, and task outcomes

Observation is explicit in the MVP: adapters record structured events from
local tools and workflows without hidden monitoring.

## Architecture

```text
Local agents / workflows / CLI / git / files
        |
        v
Observation adapters
        |
        v
Append-only event log
        |
        v
Memory service
        |
        v
Hermes memory-supervisor agent
        |
        v
Recall / audit / proactive suggestions / policy gates
```

## Main Components

### Observation Adapters

Adapters convert local activity into structured events.

Initial targets:

- Hermes adapter
- Codex adapter
- shell/git adapter
- workflow log adapter

The system should prefer structured logs and explicit hooks over screen scraping
or private app inspection.

### Event Log

All observations first enter an append-only log. They are not immediately treated
as long-term memory.

Each event should include:

- source agent or tool
- workspace, repository, and current directory
- thread or task identifier
- actor and event type
- content reference or artifact reference
- timestamp
- sensitivity level
- source hash

### Memory Service

The memory service extracts durable memory from events.

It stores:

- user preferences
- project rules
- architecture decisions
- workflow lessons
- repeated failure patterns
- tool usage patterns
- skill candidates

Every memory item must have scope, source references, confidence, status, and
last-used metadata.

### Hermes Memory Provider

memSu integrates with Hermes as an external `MemoryProvider`.

The provider should implement:

- `prefetch` for scoped recall before a Hermes turn
- `sync_turn` for post-turn ingestion
- `on_session_end` for session summaries
- `on_pre_compress` for compression-aware memory extraction
- memory tools for recall, retain, audit, patch, forget, and reflect

### Hermes Bootstrap

Hermes should not be expected to assemble memSu from prompt instructions alone.
The reliable bootstrap model is:

```text
Hermes bootstrap prompt
        |
        v
deterministic installer scripts
        |
        v
Hermes memory provider + skills + config
        |
        v
doctor verification
```

The prompt is responsible for orchestration. Scripts are responsible for file
operations, configuration updates, service startup, and validation.

The planned repository layout is:

```text
scripts/
  install_hermes.ps1
  doctor.ps1
  start_service.ps1
hermes/
  plugins/memory/memsu/
  skills/memory-capture/
  skills/memory-audit/
  skills/proactive-policy/
  prompts/bootstrap-hermes-memsu.md
```

The bootstrap prompt should instruct Hermes to:

1. locate the memSu repository
2. inspect the installer and doctor scripts before running them
3. resolve `HERMES_HOME`, defaulting to `~/.hermes`
4. install the memory provider and skills through scripts
5. configure Hermes to use `memory.provider = memsu`
6. start or verify the local memSu service
7. run a doctor check and synthetic recall test
8. report installed paths, config changes, service status, and remaining user actions

The installer should:

- copy the Hermes memory provider into the Hermes plugin directory
- copy memSu skills into the Hermes skills directory
- initialize the local memSu data directory and SQLite database
- write the default policy file
- patch Hermes config only after backing it up
- keep proactive external actions disabled by default

The doctor script should verify:

- Python/runtime availability
- local service import and startup
- database read/write access
- Hermes plugin and skill installation
- Hermes config points to `memsu`
- provider import smoke test
- event append and recall smoke test

### Memory Supervisor Agent

A dedicated Hermes agent acts as the memory supervisor.

It should:

- review recent observations
- propose memory candidates
- detect conflicts and stale facts
- maintain project-level summaries
- recommend new skills when repeated workflows appear
- generate proactive suggestions only within policy limits

## Policy Model

memSu should separate memory from action.

Default levels:

- L0: automatic internal maintenance
- L1: automatic passive recall
- L2: proactive suggestions
- L3: actions requiring user confirmation
- L4: forbidden or highly restricted actions

High-risk operations such as deleting memory, sending external messages, editing
files, changing permissions, or sharing sensitive information across agents must
require explicit confirmation.

## MVP Usage

memSu currently ships a standard-library-first local MVP.

Initialize storage:

```powershell
python -m memsu init
```

Run a smoke test:

```powershell
python -m memsu doctor
```

Start the local service:

```powershell
.\scripts\start_service.ps1
```

Add and recall memory:

```powershell
python -m memsu retain "memSu uses SQLite for the first MVP" --type decision --scope project:memsu
python -m memsu recall "SQLite MVP" --scope project:memsu
```

Extract pending candidates from events:

```powershell
python -m memsu event append --source-agent codex --event-type conversation_turn --content "Decision: memSu reviews extracted candidates before accepting them." --repo susyimes/memSu
python -m memsu extract
python -m memsu candidate list --scope project:memSu
python -m memsu candidate accept <candidate_id>
```

Record local agent and workflow observations:

```powershell
python -m memsu adapter git --repo-path . --workspace memSu
python -m memsu adapter shell --command "python -m unittest discover -s tests" --exit-code 0 --workspace memSu --repo susyimes/memSu
python -m memsu adapter workflow --name tests --status passed --summary "unit tests passed" --workspace memSu --repo susyimes/memSu
```

See [docs/adapters.md](docs/adapters.md) for adapter details.

Evaluate proactive policy:

```powershell
python -m memsu policy evaluate --action-type suggestion --description "suggest creating a skill from repeated workflow"
python -m memsu policy evaluate --action-type send_message --description "send a summary to a chat"
python -m memsu policy proposals --status pending_confirmation
```

See [docs/policy.md](docs/policy.md) for policy details.

Run memory curation:

```powershell
python -m memsu curator run
python -m memsu curator summaries --scope project:memSu
python -m memsu curator conflicts
```

See [docs/curator.md](docs/curator.md) for curator details.

Install into Hermes:

```powershell
.\scripts\install_hermes.ps1 -PatchConfig
.\scripts\doctor.ps1
```

Hermes should then use:

```yaml
memory:
  enabled: true
  provider: memsu
```

## Non-goals

- Global keylogging
- Network traffic interception
- Blind screen OCR as the primary observation method
- Unscoped memory shared across all agents
- Autonomous high-risk external actions
- A prompt-only memory system with no durable event model
- Prompt-only installation without deterministic scripts and verification

## Current Status

MVP implementation stage.

Implemented:

- SQLite event log
- scoped memory items
- rule-based candidate extraction from events
- candidate accept and reject flow
- possible conflict hints for similar same-scope memories
- explicit shell, git, Codex transcript, and workflow adapters
- L0-L4 proactive policy engine with action proposals, rate limits, quiet-hour deferral, and policy event log
- curator jobs for dedupe, stale detection, summaries, and conflict review queue
- CLI commands for init, doctor, event append/list, extract, candidate review, retain, recall, audit, and forget
- local HTTP service for Hermes integration
- Hermes external memory provider skeleton
- Hermes memory skills
- bootstrap prompt
- PowerShell installer, doctor, and service startup scripts

The current implementation proves the first core loop:

1. Observe Hermes and one coding agent.
2. Store structured events locally.
3. Extract scoped memory.
4. Serve recall back to Hermes through a memory provider.
5. Provide audit and forget operations.

Candidate extraction is rule-based and review-first in the MVP. LLM-based
extraction, curator jobs, richer policy enforcement, and multi-agent adapters
belong to later phases.
