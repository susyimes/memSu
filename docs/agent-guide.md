# memSu Agent Guide

`python -m memsu init` creates a local agent onboarding file:

```text
${MEMSU_HOME:-~/.memsu}/AGENTS.md
```

This file is intentionally user-local. It tells any agent how to use the current
memSu home without first reading the project repository.

## Commands

```powershell
python -m memsu guide init
python -m memsu guide init --force
python -m memsu guide path
python -m memsu guide show
```

`guide init` creates the file if it is missing. `--force` refreshes it from the
built-in template and should be used carefully because the file is user-editable.

## What The Guide Covers

- read order for `AGENTS.md`, `status`, `inspire`, `inbox`, `tasks`, `advance`
  and observe evidence
- the difference between user cold-start context and project documentation
- how to promote messy inbox notes into structured tasks
- how to claim and release tasks without inventing an `in_progress` status
- when a task executes and when it does not
- how to record shell/workflow evidence
- low-risk actions, confirmation-required actions, and forbidden sensitive reads

## Agent Behavior

Agents should treat `AGENTS.md` as the first local contract. Project docs explain
memSu as a product; `AGENTS.md` explains how to operate this specific user's
local memSu home.

The guide is not a replacement for model judgment. It gives the agent enough
orientation to choose the next safe step, then memSu relies on evidence, task
state, audit records, and risk boundaries instead of rigid checklists.
