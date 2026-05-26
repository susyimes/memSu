# memSu V3 Plan: Agent-Led Observation

## Direction

memSu V3 moves observation from a fixed source-reader framework to an
agent-led local investigation loop.

The core shift:

```text
V2: scheduled observe job + fixed high-level source readers
V3: model-led observation agent + safe local toolbelt + evidence ledger
```

V2 proved the trustworthy local memory loop: read safe metadata, write an
observe snapshot, store an event, extract review-first memory candidates.

V3 should keep that trust boundary but give the model more room to reason. The
observation agent should not be trapped inside a hardcoded list of sources such
as Codex, Claude, Gemini, or Hermes. It should be able to notice that the user
installed GLM, stopped using Claude Desktop, started using Kimi, created a new
workflow, or moved work to an unexpected directory by combining local evidence
the way a careful human investigator would.

## Product Shape

V3 has four surfaces:

- Agent-led observe: a model-driven local investigation run.
- Safe toolbelt: narrow read-only tools for local metadata, Git, shell history,
  installed apps, process/window state, and safe text excerpts.
- Evidence ledger: durable records of what was checked, what was skipped, and
  which evidence supports each conclusion.
- Memory pipeline: review-first memory candidates, summaries, and curator jobs
  built from the agent's findings.

The goal is not to build a bigger set of static readers. The goal is to let a
capable model decide what to inspect next while memSu enforces safety,
auditability, and candidate review.

## Core Principle

Frameworks should not decide what is interesting. The model should.

memSu should provide:

- authorization context
- inspiration notes
- safe local tools
- evidence recording
- policy checks
- candidate memory storage
- audit and forget operations

The observation agent should decide:

- which local signals matter this run
- which tools to call next
- which sources look newly installed, uninstalled, active, inactive, or stale
- which project or workflow lines are worth summarizing
- which facts are strong evidence, weak evidence, inference, or unknown
- which candidate memories deserve user review
- what to pay attention to next time

## Inspire, Not Checklist

V3 should replace rigid "focus tables" with lightweight inspiration files. They
should guide the model without boxing it in.

Planned files:

```text
${MEMSU_HOME:-~/.memsu}/inspire.md
${MEMSU_HOME:-~/.memsu}/inspire.d/
  agents.md
  projects.md
  workflows.md
  privacy.md
```

`inspire.md` is user-owned. memSu may create a default template, show the path,
and propose edits, but it should not silently overwrite the user's notes. Users
should be able to open this file directly and describe important directories,
projects, tools, and privacy preferences in their own words.

Example `inspire.md`:

```markdown
# memSu Observation Inspire

When observing local work, pay attention to:

- what project lines the user has been working on recently
- newly installed, removed, active, or abandoned local agents and AI tools
- repeated workflows that may deserve a skill or automation
- project rules, user preferences, decisions, and corrections that may deserve
  long-term memory
- contradictions between old memory and current local evidence

Important local places:

- C:\Users\me\Documents\Playground is usually experimental agent/project work.
- C:\Users\me\AndroidStudioProjects contains Android production projects.
- D:\Research contains research references; prefer metadata unless asked.
- D:\PrivateArchive is not useful for routine observation.

Do not read credentials, cookies, tokens, private keys, account secrets, or
private chat bodies unless the user explicitly grants that scope.

Separate facts, inferences, and unknowns. Attach evidence to important claims.
```

This file is not a source list. It is a briefing for the observation agent. The
agent can still decide to inspect a source not mentioned in the inspire file if
local evidence makes it relevant and policy allows it.

Directory notes in `inspire.md` are hints, not hard allowlists. The model can use
them to prioritize likely work roots, avoid low-value private archives, and
explain why it inspected or skipped a location. Sensitive-path policy still wins
over user notes.

Possible helper commands:

```powershell
python -m memsu inspire path
python -m memsu inspire show
python -m memsu inspire init
```

These commands should expose the editable file location and create a starter
template if missing. Editing can remain a normal user file operation.

## Agent-Led Observe Command

Primary future command:

```powershell
python -m memsu observe agent --since 24h
```

Possible options:

```powershell
python -m memsu observe agent --since 24h --authorization metadata
python -m memsu observe agent --since 24h --authorization local-summary
python -m memsu observe agent --since 7d --inspire project:memSu
python -m memsu observe agent --dry-run-plan
```

The existing deterministic command remains useful:

```powershell
python -m memsu observe run
```

It should continue to provide a cheap, conservative baseline. V3 does not need a
separate `collect` product surface. "Collect" becomes what an agent-led observe
run does when it has enough authorization and a reason to dig deeper.

## Investigation Loop

The run should look like this:

```text
load policy + inspire + recent memories + last observations
  -> create an investigation plan
  -> call safe local tools
  -> inspect returned metadata and evidence
  -> revise the plan
  -> call more tools only when justified
  -> produce observation brief
  -> store evidence refs and findings
  -> propose memory candidates
  -> propose next-run attention notes
```

The loop must be bounded by budget, time, authorization, and safety policy. The
model should be free to choose tools, but not free to ignore safety rules.

## Safe Toolbelt

The toolbelt should be generic. It should expose local information shapes rather
than product-specific readers.

Initial tool families:

- `local_time_context`: current local time, timezone, since/cutoff window.
- `list_roots`: safe top-level directories and drive summaries.
- `list_recent_paths`: recent files/directories by metadata only, with excludes.
- `find_git_repos`: discover Git repositories under likely work roots.
- `summarize_git_repo`: branch, status, recent commits, reflog, and stats.
- `list_windows_recent`: recent shortcut names and timestamps.
- `list_visible_processes`: visible windows, process names, start times.
- `list_process_commands`: sanitized command lines for allowlisted dev tools.
- `query_installed_apps`: Windows uninstall registry and app package metadata.
- `check_common_app_paths`: existence and timestamps for likely app directories.
- `tail_shell_history_safely`: filtered shell history tail and command counts.
- `read_safe_text_excerpt`: bounded excerpt from non-sensitive text files.
- `record_evidence`: persist evidence refs with source hashes.
- `propose_memory_candidate`: create pending memory candidates only.
- `update_inspire_proposal`: propose changes to future attention notes.

Product-specific helpers can still exist, but they should be optional tools the
model may discover and call, not the spine of the observation system.

## Example: Installing GLM or Uninstalling Claude

V2 can miss this because it only knows the source readers that were implemented
ahead of time.

V3 should let the model combine generic signals:

```text
GLM possible install:
- command history mentions glm, zai, or bigmodel commands
- a new ~/.glm-like directory exists
- a GLM shortcut appears on Desktop or Start Menu
- installed app registry contains GLM/Zhipu/BigModel-like publisher strings
- recent process or prefetch entries mention GLM

Claude possible uninstall:
- old observation said Claude Desktop path or shortcut existed
- current installed app registry no longer has Claude Desktop
- common Claude Desktop directories are missing
- ~/.claude still exists, suggesting CLI/config residue remains
- command history has Claude Code commands but no desktop launch
```

The model should report this as facts and inference, not as certainty:

```text
Fact: Claude Code registry entry still exists.
Fact: common Claude Desktop directories were not found.
Inference: Claude Desktop may have been uninstalled while Claude Code/config
remains.
Unknown: no direct uninstall event was found in the checked evidence.
```

## Evidence Model

V3 should add first-class evidence records.

Planned tables:

```text
observation_runs
  run_id
  mode
  since
  authorization_level
  started_at
  finished_at
  status
  model
  prompt_hash
  tool_call_count
  result_ref
  metadata

evidence_refs
  evidence_id
  run_id
  source_type
  source_ref
  source_hash
  observed_at
  sensitivity
  summary
  metadata

observation_findings
  finding_id
  run_id
  kind
  scope
  claim
  confidence
  evidence_ids
  status
  metadata
```

The existing `events`, `memory_candidates`, `memories`, `memory_summaries`, and
curator tables remain the long-term memory substrate.

Observation findings are not automatically memories. They are evidence-backed
claims that can generate memory candidates.

## Observation Brief

Each agent-led observe run should produce a compact brief:

```markdown
# Observation Brief

## Current Picture
- ...

## Strong Facts
- ...

## Inferences
- ...

## Unknowns
- ...

## Tool / Agent Changes
- ...

## Work Timeline
- ...

## Candidate Memories
- ...

## Suggested Next Attention
- ...

## Skipped / Redacted
- ...
```

The brief is written to:

```text
${MEMSU_HOME:-~/.memsu}/observe/YYYY-MM-DD.md
```

The structured version is stored in SQLite and can be exported as JSON.

## Authorization Levels

V3 should keep authorization simple and explicit:

```text
metadata
  Read file names, paths, sizes, timestamps, process names, installed app
  metadata, Git metadata, and sanitized command summaries.

local-summary
  May read bounded excerpts from non-sensitive project docs, Git commit text,
  safe logs, and agent summaries.

content-with-approval
  May read selected transcript or private-workflow content only after explicit
  user approval for the run or source.
```

Credentials, tokens, cookies, private keys, secret files, and account material
are always forbidden and should be skipped or redacted.

## Policy Rules

Hard rules:

- Do not read credential-like files.
- Do not record secrets.
- Do not mutate user files during observation.
- Do not treat an inference as a fact.
- Do not automatically accept long-term memory.
- Do not silently expand into private chat bodies or private app logs.
- Do not hide skipped or redacted evidence.

Soft rules:

- Prefer recent, corroborated evidence.
- Prefer metadata before content.
- Prefer multiple weak signals over one ambiguous signal.
- Stop when enough evidence exists for the requested observation.
- Ask for authorization when a deeper source would materially improve the
  answer.

## Relationship to V2 Observe

V2 observe remains a deterministic baseline:

```text
python -m memsu observe run
```

It is cheap, conservative, scheduler-friendly, and testable.

V3 observe is the adaptive path:

```text
python -m memsu observe agent
```

It is more useful when the environment changes, when new agents appear, when
old tools disappear, or when the user asks for a broader understanding of local
work.

The two should share:

- redaction policy
- evidence hashing
- observe output path
- SQLite storage
- candidate extraction and review flow

They should not share a rigid source list.

## Milestones

### V3.0 Design and Prompt Contract

- document agent-led observe plan
- define default user-editable `inspire.md`
- expose `inspire.md` path through CLI/status
- define observation-agent system prompt
- define toolbelt contracts and JSON result schemas
- define authorization levels

Success check:

- a local agent can understand how to run observation without a static source
  checklist.

### V3.1 Evidence Ledger

- add `observation_runs`
- add `evidence_refs`
- add `observation_findings`
- record source hashes and skipped sensitive sources
- export one run as JSON

Success check:

- every important observation claim can point to evidence ids.

### V3.2 Safe Toolbelt

- implement generic read-only local probes
- add safety filters and bounded output
- add tests for sensitive path rejection
- add tests that tools do not mutate inspected sources

Success check:

- the model can inspect local activity without product-specific readers.

### V3.3 Agent-Led Observe Loop

- add `python -m memsu observe agent`
- load inspire, recent memories, and prior observations
- let the model plan and call tools iteratively
- persist the observation brief and structured findings

Success check:

- the agent can infer recent work lines and tool/source changes from generic
  local evidence.

### V3.4 Candidate and Inspire Review

- convert selected findings into pending memory candidates
- propose edits to `inspire.md` or `inspire.d/*.md`
- require user review before accepting memory or changing persistent
  inspiration notes

Success check:

- useful observations become reviewable memory without automatic lock-in.

### V3.5 Scheduler Integration

- allow scheduled low-cost V2 observe
- allow policy-gated V3 agent observe on demand or low frequency
- summarize runs for Hermes, Codex, or Windows Task Scheduler

Success check:

- memSu can run routinely without surprising the user, while still supporting
  richer investigation when authorized.

## Open Questions

- Which local model or hosted model should power `observe agent` by default?
- Should V3 agent runs require explicit per-run user authorization, or can
  `metadata` runs be scheduled?
- How should tool-call budgets be represented in policy?
- Should `inspire.md` edits be accepted through candidate-style review?
- What is the right default set of likely work roots on Windows without baking
  in one user's machine layout?

## Non-goals

- hidden surveillance
- keylogging
- network interception
- credential capture
- unrestricted shell execution
- direct mutation of user files during observation
- automatic reading of private chats
- automatic acceptance of long-term memory
- replacing auditability with model confidence
