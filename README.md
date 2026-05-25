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

## Non-goals

- Global keylogging
- Network traffic interception
- Blind screen OCR as the primary observation method
- Unscoped memory shared across all agents
- Autonomous high-risk external actions
- A prompt-only memory system with no durable event model

## Current Status

Design stage.

The first implementation should prove the core loop:

1. Observe Hermes and one coding agent.
2. Store structured events locally.
3. Extract scoped memory.
4. Serve recall back to Hermes through a memory provider.
5. Provide audit and forget operations.

