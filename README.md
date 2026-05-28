# memSu

memSu is a local memory and observation store for Hermes and other desktop
agents.

The goal is not to clone memU as a library. The goal is to make a dedicated
Hermes agent, Codex automation, Windows scheduled task, or any other local agent
able to run memSu CLI jobs that observe local agents, workflows, command
history, project activity, and task outcomes, then turn reliable observations
into scoped, auditable long-term memory.

memSu does not need to run as a daemon. The default integration model is
CLI-first: any trusted local agent can execute `python -m memsu ...` and read or
write the same local SQLite store.

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
memSu CLI jobs + SQLite store
        |
        v
Any local agent / scheduler
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

### Memory Core

The memory core extracts durable memory from events.

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

### Agent Bridge

memSu should be usable by Hermes and other local agents through the CLI. The
CLI is the required integration contract; a long-running HTTP service is not
part of the default design.

Agent-facing operations should include:

- scoped recall before work starts
- explicit post-work event ingestion
- observation snapshot generation
- memory tools for recall, retain, audit, patch, forget, and review
- policy checks before proactive or external actions

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
Hermes skills + CLI job config
        |
        v
doctor verification
```

The prompt is responsible for orchestration. Scripts are responsible for file
operations, configuration updates, CLI verification, and validation.

The planned repository layout is:

```text
scripts/
  install_hermes.ps1
  doctor.ps1
  install_windows_task.ps1
  uninstall_windows_task.ps1
hermes/
  skills/memory-capture/
  skills/memory-audit/
  skills/proactive-policy/
  prompts/bootstrap-hermes-memsu.md
```

The bootstrap prompt should instruct Hermes to:

1. locate the memSu repository
2. inspect the installer and doctor scripts before running them
3. resolve `HERMES_HOME`, defaulting to `~/.hermes`
4. install memSu skills and CLI job helpers through scripts
5. verify Hermes can execute `python -m memsu ...`
6. run a doctor check and synthetic recall test
7. report installed paths, config changes, CLI status, and remaining user actions

The installer should:

- copy memSu skills into the Hermes skills directory
- initialize the local memSu data directory and SQLite database
- write the default policy file
- avoid Hermes config mutation unless the user explicitly requests it
- keep proactive external actions disabled by default

The doctor script should verify:

- Python/runtime availability
- database read/write access
- Hermes skill installation
- memSu CLI command execution
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

### Autonomous Advancement Agent

The next layer is an advancement agent that uses memSu's existing observations,
findings, memories, pending candidates, and policy engine to keep local work
moving without taking unsafe control of the machine.

The design is skill/adapter-controlled. Adapters produce structured events,
evidence, and findings from stable signal sources. Skills orchestrate repeatable
workflows such as "observe -> proposals". The auto kernel should only choose
which skill or adapter to call, rank evidence-backed opportunities, run policy
checks, and record outcomes.

The first reference skill is `observe-to-proposals`: run or read memSu observe,
summarize active work lines, produce L2 suggestions, and create L3 action
proposals without editing files, sending messages, or accepting memory.
Observation answers "what can be seen"; advancement answers "what should happen
next, within policy"; skills and adapters answer "how this capability is safely
performed".

See [PLAN_AUTO.md](PLAN_AUTO.md).

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

Initialization creates the SQLite store, policy file, observe directory,
discovery manifests, and a user-editable V3 inspire file at
`${MEMSU_HOME:-~/.memsu}/inspire.md`.

Run a smoke test:

```powershell
python -m memsu doctor
python -m memsu status
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

Optional OpenAI-compatible LLM extraction:

```powershell
$env:MEMSU_LLM_ENDPOINT = "http://127.0.0.1:11434/v1/chat/completions"
$env:MEMSU_LLM_MODEL = "local-model"
python -m memsu extract --method llm
```

Record local agent and workflow observations:

```powershell
python -m memsu adapter codex .\codex-session.md --workspace memSu --repo susyimes/memSu
python -m memsu adapter transcript --agent gemini .\gemini-session.md --workspace memSu --repo susyimes/memSu
python -m memsu adapter git --repo-path . --workspace memSu
python -m memsu adapter shell --command "python -m unittest discover -s tests" --exit-code 0 --workspace memSu --repo susyimes/memSu
python -m memsu adapter workflow --name tests --status passed --summary "unit tests passed" --workspace memSu --repo susyimes/memSu
```

See [docs/adapters.md](docs/adapters.md) for adapter details.

Run a local observe snapshot:

```powershell
python -m memsu observe run
python -m memsu observe list
```

Observe writes to `${MEMSU_HOME:-~/.memsu}/observe/YYYY-MM-DD.md` and records a
snapshot row in SQLite. See [docs/observe.md](docs/observe.md).

Run the skill/adapter-controlled advancement kernel:

```powershell
python -m memsu advance agenda
python -m memsu advance agenda --rank-method llm
python -m memsu advance capabilities
python -m memsu advance run --dry-run
python -m memsu advance run --skill observe-to-proposals --dry-run
python -m memsu advance run --skill observe-to-proposals
python -m memsu advance run --adapter git-activity --repo-path .
python -m memsu advance runs
python -m memsu advance worklines
python -m memsu advance opportunities
```

Advance reads existing observations, findings, candidates, conflicts, summaries,
and events, then produces policy-gated suggestions. See
[docs/advance.md](docs/advance.md).

V3 planning explores an agent-led observe mode where the model chooses safe
local read-only probes, records evidence, and proposes memory candidates instead
of relying on a fixed source-reader checklist. V3 also introduces user-editable
inspire notes so the user can describe important local directories, tools, and
observation preferences:

```text
${MEMSU_HOME:-~/.memsu}/inspire.md
${MEMSU_HOME:-~/.memsu}/inspire.d/*.md
```

Use `inspire.md` for the main high-signal notes. Use `inspire.d` for split
topic files such as `projects.md`, `agents.md`, or `privacy.md` when the main
file gets crowded. During V3 agent-led planning, memSu reads the main file first
and then top-level markdown files in `inspire.d` sorted by file name. These
notes are hints, not strict allowlists. See [PLAN_V3.md](PLAN_V3.md).

V4 starts by making inspire notes more actionable without hard-coding personal
absolute paths. The starter `inspire.d` files describe local signal surfaces the
agent should consider at run time: file modification times, Git log/status/stat
signals, Windows Recent shortcuts, PowerShell history, current processes and
window titles, local agent session metadata, and build/release artifacts. The
agent should discover concrete paths from the machine state and evidence rather
than relying on a brittle path list.

V3 helper commands:

```powershell
python -m memsu inspire path
python -m memsu inspire show
python -m memsu observe agent --dry-run-plan
```

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

Run hardening tools:

```powershell
python -m memsu migrate status
python -m memsu backup create
python -m memsu export json
python -m memsu privacy scan
python -m memsu vector rebuild
```

See [docs/hardening.md](docs/hardening.md) for hardening details.

Install into Hermes:

```powershell
.\scripts\install_hermes.ps1
.\scripts\doctor.ps1
```

Hermes should then call memSu through CLI jobs and skills.

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
- CLI-first status and discovery manifests
- observe snapshots written to `${MEMSU_HOME:-~/.memsu}/observe/YYYY-MM-DD.md`
- V3 user-editable `${MEMSU_HOME:-~/.memsu}/inspire.md` and `inspire.d/*.md`
- V3 observation run, evidence reference, and finding tables
- initial `observe agent` planning entrypoint
- skill/adapter-controlled `advance` kernel with capability registry, agenda generation, skill/adapter invocation, advancement history, repeated-workline detection, and optional LLM ranking
- rule-based and optional OpenAI-compatible LLM candidate extraction from events
- candidate accept and reject flow
- possible conflict hints for similar same-scope memories
- explicit shell, git, Codex transcript, generic transcript, and workflow adapters
- L0-L4 proactive policy engine with action proposals, configurable rate limits, quiet-hour deferral, and policy event log
- curator jobs for dedupe, stale detection, summaries, and conflict review queue
- production hardening tools for migration status, backup, export, privacy review, and sparse vector recall
- CLI commands for init, status, doctor, observe, event append/list, extract, candidate review, retain, recall, audit, and forget
- Hermes memory skills
- bootstrap prompt
- PowerShell installer and doctor scripts

The current implementation proves the first core loop:

1. Observe Hermes, local coding agents, shell/git activity, and workflows.
2. Store structured events locally.
3. Extract scoped memory with review-first candidate approval.
4. Return recall to any local agent through CLI-first commands.
5. Provide audit and forget operations.

Current limitations: observation is explicit adapter ingestion rather than hidden
monitoring; LLM extraction is optional, skips sensitive events, and still
creates review-first candidates; the policy parser supports a small local
defaults file instead of a full policy language; the HTTP service/provider path
has been removed from the default project and should only be reintroduced if
CLI latency, concurrency, or integration needs justify it.
