# memSu Implementation Plan

## Current MVP Status

Implemented:

- repository foundation
- SQLite-backed event log
- basic memory item store
- CLI for init, doctor, event append/list, retain, recall, audit, and forget
- local HTTP service
- Hermes memory provider skeleton
- Hermes skills and bootstrap prompt
- PowerShell install, doctor, and service startup scripts

Not yet implemented:

- automatic LLM memory extraction
- Codex and other agent adapters
- proactive policy engine beyond documented rules and default policy file
- curator jobs
- vector retrieval
- production service supervision

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

## Phase 2: Hermes Memory Provider

Goal: make memSu usable from Hermes.

Deliverables:

- `plugins/memory/memsu` Hermes provider
- `prefetch(query)` for scoped recall
- `sync_turn(...)` for post-turn ingestion
- `on_session_end(...)` summary hook
- tool schemas for recall, retain, audit, forget, and reflect
- config docs for `memory.provider = memsu`

Success check:

- Hermes can recall memSu memory before a turn and sync conversation events after a turn

## Phase 2.5: Hermes Bootstrap Installer

Goal: let Hermes initialize memSu safely through a prompt-orchestrated,
script-backed workflow.

Deliverables:

- `scripts/install_hermes.ps1`
- `scripts/doctor.ps1`
- `scripts/start_service.ps1`
- `hermes/prompts/bootstrap-hermes-memsu.md`
- installer support for resolving `HERMES_HOME`
- config backup before mutation
- provider and skill copy/install logic
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
4. verify provider and skill installation
5. ensure Hermes config uses `memory.provider = memsu`
6. start or verify the local memSu service
7. run doctor
8. report exact installed paths, config changes, service status, and test results

Success check:

- a Hermes agent can bootstrap memSu from a cloned repository without manually copying files
- the installer is repeatable and does not enable autonomous external actions by default

## Phase 3: Memory Extraction

Goal: convert observations into durable memory candidates.

Deliverables:

- memory item schema
- candidate extraction pipeline
- confidence, salience, scope, and source tracking
- explicit rejection and correction flow
- conflict detection for incompatible facts

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

- Codex adapter
- shell/git adapter
- generic workflow log adapter
- adapter documentation
- minimal local API: `/events`, `/recall`, `/audit`, `/forget`

Success check:

- at least Hermes, Codex, and shell/git activity can feed the same memory service

## Phase 5: Proactive Policy

Goal: allow useful proactive behavior without unsafe autonomy.

Deliverables:

- policy configuration
- risk levels L0 to L4
- rate limits and quiet hours
- confirmation-required action proposals
- policy event log

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

- dedupe and merge jobs
- stale memory detection
- topic summaries
- project-level summaries
- conflict review queue
- archive instead of hard delete by default

Success check:

- memory quality improves over time instead of becoming an unbounded log dump

## Phase 7: Production Hardening

Goal: make memSu reliable as a long-running local service.

Deliverables:

- service supervision
- backups and export
- migration system
- structured logs
- privacy review tools
- optional vector backend
- test suite for provider, storage, policy, and extraction

Success check:

- memSu can run continuously and recover from crashes without corrupting memory

## First MVP Cut

The smallest useful build is:

1. SQLite event log
2. Hermes memory provider
3. manual `retain`, `recall`, `audit`, and `forget`
4. post-turn event sync
5. simple keyword plus scope-based recall

Do not start with full autonomy, screen observation, or multi-agent policy
complexity. Build the trustworthy memory loop first.
