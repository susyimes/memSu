# memSu Task Board

memSu task board is a user-owned Markdown file:

```text
${MEMSU_HOME:-~/.memsu}/tasks.md
```

It is intentionally lightweight. Users can edit it by hand, while memSu parses
the stable parts needed for agenda generation.

Agents should first read `${MEMSU_HOME:-~/.memsu}/AGENTS.md` for the local
operating guide, then use this task board as the structured work surface.

Humans do not need to write this file directly for messy ideas. Put rough notes,
future work, and half-formed tasks in the human inbox first:

```text
${MEMSU_HOME:-~/.memsu}/inbox/
```

Agents can promote concrete items into `tasks.md` and archive the original
source under `${MEMSU_HOME:-~/.memsu}/inbox/archive/`. See
[docs/inbox.md](inbox.md).

## Commands

Create the default template:

```powershell
python -m memsu task init
python -m memsu task init --force
```

Inspect the path:

```powershell
python -m memsu task path
```

List tasks:

```powershell
python -m memsu task list
python -m memsu task list --status active
python -m memsu task list --scope project:memSu
```

Show or update one task:

```powershell
python -m memsu task show <task_id>
python -m memsu task update <task_id> --status verifying --note "tests started"
```

`task update` rewrites the heading status token and appends a `history:` entry
inside the task block. It does not require SQLite schema changes.

Claim or release one task:

```powershell
python -m memsu task claim <task_id> --agent codex --lease 2h --note "working on this"
python -m memsu task release <task_id> --agent codex --note "handoff"
```

`status` and `claim` are separate. Status describes the task lifecycle:
`todo`, `active`, `blocked`, `verifying`, `done`, or `dropped`. Claim describes
which agent has taken temporary responsibility:

```markdown
claimed_by: codex
claimed_at: 2026-05-29T01:00:00+00:00
claim_until: 2026-05-29T03:00:00+00:00
```

Do not use `in_progress` as a status. An agent claim is represented by
`claimed_by` plus a lease, while the task can remain `todo` or `active`.

## Markdown Shape

The parser treats each level-2 heading as a task:

```markdown
## [todo][P1] Stabilize observe-to-assistance loop

scope: project:memSu
context: Roadmap says manual Markdown tasks are first-class input.
blocked:
claimed_by:
claimed_at:
claim_until:

acceptance:
- advance agenda reads task board.
- suggestions cite task ids.
```

Parsed fields:

- leading status token: `todo`, `active`, `blocked`, `verifying`, `done`, `dropped`
- leading priority token: `P0`, `P1`, `P2`, `P3`, or a word priority
- `id:` optional stable task id
- `scope:`
- `context:`
- `source:` optional inbox archive path or other provenance
- `claimed_by:` optional agent name
- `claimed_at:` optional ISO timestamp
- `claim_until:` optional ISO timestamp for claim lease expiry
- `blocked:`
- `acceptance:` bullet list

If `id:` is missing, memSu generates a stable id from title, scope, and
occurrence order.

## Advance Integration

`python -m memsu advance agenda` reads open task board items as first-class
worklines. Tasks with `done` or `dropped` status are ignored by the active
agenda. Task-derived suggestions cite the task id as evidence.

Unprocessed inbox files appear separately as an `organize_inbox` suggestion.
They should be interpreted before they become task-board worklines.

## Execution Model

memSu does not execute tasks by itself. It is CLI-first and has no default
background worker. Tasks run only when an agent or scheduler chooses to act:

- Manual: the user asks Codex, Claude, Hermes, or another agent to claim and do a task.
- Agenda: an agent reads `advance agenda`, chooses a task, claims it, and works.
- Scheduled: a cron, Codex automation, or Hermes workflow periodically runs agenda and delegates work.

The expected agent flow is:

1. Read `python -m memsu advance agenda` or `python -m memsu task list`.
2. Claim the chosen task with `python -m memsu task claim <task_id> --agent <name>`.
3. Do the low-risk work or ask for confirmation for high-risk work.
4. Record workflow evidence with `adapter workflow` or related adapters.
5. Update status with `task update`, usually to `verifying`, `done`, or `blocked`.
6. Release the claim if handing off or abandoning the task.
