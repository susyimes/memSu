# memSu Implementation Plan

## Current MVP Status

V2 observe-layer planning is tracked in [PLAN_V2.md](PLAN_V2.md).
V3 agent-led observation planning is tracked in [PLAN_V3.md](PLAN_V3.md).
V4 inspire-driven observation planning is tracked in [PLAN_V4.md](PLAN_V4.md).
Autonomous advancement planning is tracked in [PLAN_AUTO.md](PLAN_AUTO.md).

Implemented:

- repository foundation
- SQLite-backed event log
- basic memory item store
- CLI-first status and machine-independent discovery manifests
- observe snapshot storage and `${MEMSU_HOME:-~/.memsu}/observe/YYYY-MM-DD.md` output
- V4 user-editable `${MEMSU_HOME:-~/.memsu}/inspire.md` and `inspire.d/*.md` initialization
- V3 observation run, evidence reference, and observation finding storage
- initial `observe agent` planning entrypoint and prompt/toolbelt contract
- skill/adapter-controlled autonomous advancement design for agenda generation and policy-gated next steps
- initial `advance agenda` and `advance run --skill observe-to-proposals` MVP
- rule-based candidate extraction pipeline
- optional OpenAI-compatible LLM candidate extraction pipeline
- candidate accept and reject flow
- possible conflict hints for similar same-scope memories
- explicit shell, git, Codex transcript, generic transcript, and workflow adapters
- L0-L4 proactive policy engine with action proposals, configurable defaults, and policy event log
- curator jobs for dedupe, stale detection, summaries, and conflict review queue
- production hardening tools for migration status, backup, export, privacy review, and sparse vector recall
- CLI for init, status, doctor, observe, event append/list, extract, candidate review, retain, recall, audit, and forget
- Hermes skills and bootstrap prompt
- PowerShell install, doctor, and observe scheduled task scripts

Known limitations:

- LLM extraction requires an explicitly configured OpenAI-compatible endpoint, skips sensitive events, and still creates review-first candidates.
- Agent observation is explicit transcript/workflow ingestion, not hidden desktop surveillance.
- Policy configuration currently supports simple local defaults, not a full rule DSL.
- The HTTP service/provider path has been removed and should only be reintroduced if CLI latency, concurrency, or integration needs justify it.

## Phase 0: Repository Foundation

Goal: establish the project shape and working assumptions.

Deliverables:

- README with architecture and non-goals
- implementation plan
- initial package layout
- local development instructions
- basic configuration format
- Hermes bootstrap prompt design
- script-based installation contract

Success check:

- a new contributor can understand what memSu is and what it is not

## Phase 1: Local Event Log

Goal: create the durable observation substrate.

Deliverables:

- SQLite-backed append-only event log
- event schema and validation
- simple CLI for appending and listing events
- source hashing for dedupe
- sensitivity and scope fields

Initial event types:

- conversation_turn
- tool_call
- command_run
- git_event
- workflow_result
- artifact_created

Success check:

- local tools can write structured events without needing Hermes

## Phase 2: Agent CLI Bridge

Goal: make memSu usable from Hermes and any other local agent without requiring
a resident service.

Deliverables:

- CLI JSON contract for recall, retain, audit, forget, policy, and candidate review
- Hermes skills that call `python -m memsu ...`
- explicit event ingestion commands for post-work summaries
- future service/provider compatibility only if a later bottleneck requires it

Success check:

- Hermes, Codex, or another local agent can recall and write memSu memory by
  executing CLI commands

## Phase 2.5: Hermes Bootstrap Installer

Goal: let Hermes initialize memSu safely through a prompt-orchestrated,
script-backed workflow.

Deliverables:

- `scripts/install_hermes.ps1`
- `scripts/doctor.ps1`
- `scripts/install_windows_task.ps1` for scheduled observe
- `hermes/prompts/bootstrap-hermes-memsu.md`
- installer support for resolving `HERMES_HOME`
- no Hermes config mutation unless explicitly requested
- skill copy/install logic
- local data directory and SQLite initialization
- default policy file with high-risk actions disabled
- synthetic event and recall smoke test

Bootstrap principle:

- the prompt orchestrates
- scripts mutate the filesystem
- doctor verifies the result

The bootstrap prompt should tell Hermes to:

1. inspect installer scripts before executing them
2. resolve the memSu repo path and Hermes home
3. run the installer
4. verify skill installation
5. verify Hermes can execute `python -m memsu ...`
6. avoid starting a resident memSu service
7. run doctor
8. report exact installed paths, config changes, CLI status, and test results

Success check:

- a Hermes agent can bootstrap memSu from a cloned repository without manually copying files
- the installer is repeatable and does not enable autonomous external actions by default

## Phase 3: Memory Extraction

Goal: convert observations into durable memory candidates.

Deliverables:

- memory item schema
- candidate extraction pipeline (rule-based MVP implemented)
- confidence, salience, scope, and source tracking (implemented)
- explicit rejection and correction flow (candidate accept/reject implemented)
- conflict detection for incompatible facts (basic same-scope similarity hints implemented)

Memory types:

- preference
- project_rule
- fact
- decision
- workflow_lesson
- failure_pattern
- skill_candidate

Success check:

- repeated local activity produces scoped, auditable memory items with source references

## Phase 4: Agent Adapters

Goal: observe local agents and workflows beyond Hermes.

Deliverables:

- Codex adapter (transcript ingestion implemented)
- generic agent transcript adapter (implemented)
- shell/git adapter (implemented)
- generic workflow log adapter (implemented)
- adapter documentation (implemented)
- minimal local API: `/events`, `/recall`, `/audit`, `/forget` plus adapter endpoints

Success check:

- at least Hermes, Codex, and shell/git activity can feed the same local memory store

## Phase 5: Proactive Policy

Goal: allow useful proactive behavior without unsafe autonomy.

Deliverables:

- policy configuration (default policy file implemented)
- risk levels L0 to L4 (implemented)
- rate limits and quiet hours (configurable L2 defer behavior implemented)
- confirmation-required action proposals (implemented)
- policy event log (implemented)

Default behavior:

- automatic maintenance is allowed
- passive recall is allowed
- suggestions are allowed with rate limits
- external actions require confirmation
- sensitive cross-agent sharing is denied unless explicitly allowed

Success check:

- memSu can suggest useful actions while preserving user control

## Phase 6: Memory Curator

Goal: keep long-term memory useful over time.

Deliverables:

- dedupe and merge jobs (exact duplicate archive implemented)
- stale memory detection (implemented)
- topic summaries (implemented)
- project-level summaries (implemented)
- conflict review queue (implemented)
- archive instead of hard delete by default (implemented)

Success check:

- memory quality improves over time instead of becoming an unbounded log dump

## Phase 7: Production Hardening

Goal: make memSu reliable as a local CLI-first memory store.

Deliverables:

- backups and export (implemented)
- migration system (schema version table/status implemented)
- privacy review tools (implemented)
- optional vector backend (sparse vector backend implemented)
- test suite for bridge/storage compatibility, storage, policy, and extraction (implemented)

Success check:

- memSu can be called repeatedly by schedulers or agents without corrupting memory

## First MVP Cut

The smallest useful build is:

1. SQLite event log
2. CLI recall/retain/audit/forget
3. manual `retain`, `recall`, `audit`, and `forget`
4. explicit event ingestion
5. simple keyword plus scope-based recall

Do not start with full autonomy, screen observation, or multi-agent policy
complexity. Build the trustworthy memory loop first.
