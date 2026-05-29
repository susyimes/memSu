from __future__ import annotations

from typing import Any

from .paths import default_agent_guide_path


AGENT_GUIDE = """# memSu Agent Guide

This file is the first thing an agent should read inside `${MEMSU_HOME:-~/.memsu}`.
It explains how to use this local memSu home without needing project docs.

## What memSu Is

memSu is a CLI-first local memory, observation, task, and audit layer. It is not
a background executor by default. Agents use it to understand the user's local
context, organize messy input, claim tasks, record evidence, and update state.

User alignment, personal operating principles, work preferences, and cold-start
context belong in this memSu home (`inspire.md`, `inspire.d/`, or inbox notes).
Do not copy private user alignment files into a project repository unless the
user explicitly asks for that.

Default entrypoint:

```powershell
python -m memsu ...
```

## Read Order

1. Read this `AGENTS.md`.
2. Run `python -m memsu status` to confirm paths and capabilities.
3. Read `inspire.md` and top-level `inspire.d/*.md` for user preferences,
   privacy boundaries, observation hints, and long-running context.
4. Run `python -m memsu inbox list` and inspect unprocessed inbox files before
   assuming the task board is complete.
5. Run `python -m memsu task list` and inspect relevant task details.
6. Run `python -m memsu advance agenda` for current worklines and suggestions.
7. Use latest observe evidence from `observe/` or `python -m memsu observe list`
   when deciding what is real, inferred, unknown, or stale.
8. Prefer concise Chinese when reporting back to this user unless they ask for
   another language.

## Core Paths

```text
AGENTS.md          agent operating guide
inspire.md         user preferences, principles, privacy boundaries
inspire.d/         split user context files
inbox/             messy human notes, future work, raw material
inbox/archive/     promoted source notes
tasks.md           structured task board
observe/           dated observation reports
memsu.db           local SQLite event/memory/audit store
policy.yaml        risk policy defaults
capabilities.json  machine-readable CLI capability manifest
```

## Human Inbox Flow

Humans may write messy Markdown or TXT files in `inbox/`. Do not force humans to
write perfect `tasks.md` entries.

Agent flow:

```powershell
python -m memsu inbox list
python -m memsu inbox promote <file> --title "..." --scope "..." --acceptance "..."
```

Promotion appends a structured task to `tasks.md`, moves the source file into
`inbox/archive/`, and records the archive path in the task `source:` field.

Only promote concrete work. Keep preferences and principles in `inspire.md` or
`inspire.d/`.

## Task Board Flow

Valid task statuses:

```text
todo / active / blocked / verifying / done / dropped
```

Do not invent `in_progress`. Agent ownership is a separate claim lease:

```powershell
python -m memsu task claim <task_id> --agent <agent_name> --lease 2h
python -m memsu task release <task_id> --agent <agent_name>
python -m memsu task update <task_id> --status verifying --note "tests running"
```

Claim fields in `tasks.md`:

```text
claimed_by:
claimed_at:
claim_until:
```

Tasks are not executed automatically just because they exist. Execution happens
only when a user asks an agent, an agent chooses work from `advance agenda`, or
a configured scheduler/Hermes workflow delegates it.

## Agent Work Loop

1. Build context: `status`, `inspire show`, `inbox list`, `task list`,
   `advance agenda`, and recent observe reports.
2. If inbox has files, classify them as task, context, reference, duplicate, or
   not actionable. Promote only concrete tasks.
3. Choose work using model judgment, evidence, user intent, and risk.
4. Claim the task before doing non-trivial work.
5. For low-risk work, run bounded local checks, tests, doctor commands, dry-runs,
   or read-only probes.
6. For high-risk work, ask for confirmation or create a proposal. Do not send
   messages, change permissions, delete data, publish, pay, or read secrets
   without explicit authorization.
7. Record evidence:

```powershell
python -m memsu adapter shell --command "..." --exit-code 0 --workspace "..." --repo "..." --task-id <task_id>
python -m memsu adapter workflow --name "..." --status passed --summary "..." --task-id <task_id>
```

8. Update task state to `verifying`, `done`, or `blocked` with a clear note.
9. Release the claim when handing off or stopping.

## Risk Boundaries

Automatic or low-friction:

- Read this memSu home and non-sensitive metadata.
- Read `inspire`, `inbox`, `tasks`, `observe`, and memSu CLI outputs.
- Run status, doctor, list, agenda, dry-run, tests, lint, and other bounded
  low-risk local checks.
- Record workflow evidence and update memSu task state.

Requires confirmation:

- External messages, uploads, publishing, payment, permission changes, account
  configuration, cross-agent sensitive sharing, broad file edits, or any
  irreversible action.

Forbidden or skip by default:

- Credentials, tokens, cookies, private keys, browser sessions, private chat
  bodies, hidden monitoring, keylogging, network capture, or bypassing
  authorization.

## Useful Commands

```powershell
python -m memsu status
python -m memsu doctor
python -m memsu inspire show
python -m memsu inbox list
python -m memsu task list
python -m memsu advance agenda
python -m memsu observe run
python -m memsu observe list
python -m memsu candidate list
python -m memsu policy proposals
```

Default output should be concise Chinese for this user unless the user asks for
another language.
"""


def ensure_agent_guide(*, overwrite: bool = False) -> dict[str, Any]:
    path = default_agent_guide_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    if overwrite or not path.exists():
        path.write_text(AGENT_GUIDE, encoding="utf-8")
        created = True
    return {
        "agent_guide_path": str(path),
        "created": created,
        "user_editable": True,
    }


def agent_guide_status() -> dict[str, Any]:
    path = default_agent_guide_path()
    return {
        "agent_guide_path": str(path),
        "exists": path.exists(),
        "user_editable": True,
    }


def read_agent_guide() -> dict[str, Any]:
    status = agent_guide_status()
    path = default_agent_guide_path()
    return {
        **status,
        "content": path.read_text(encoding="utf-8") if path.exists() else "",
    }
