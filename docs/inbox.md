# memSu Human Inbox

`tasks.md` is the structured board that agents use for agenda generation. It is
not the place where humans should be forced to write perfectly shaped tasks.

Use the inbox for messy user input:

```text
${MEMSU_HOME:-~/.memsu}/inbox/
${MEMSU_HOME:-~/.memsu}/inbox/archive/
```

Agents should first read `${MEMSU_HOME:-~/.memsu}/AGENTS.md`. The guide tells
them how to inspect inbox files, promote concrete work, claim tasks, and record
evidence.

Humans can drop Markdown or text files into `inbox/`: future work, rough notes,
links, pasted context, unclear tasks, or half-formed plans. Agents read these
files, decide what should become a real task, promote structured tasks into
`${MEMSU_HOME:-~/.memsu}/tasks.md`, and move the original source file into
`inbox/archive/`.

## Commands

Create the inbox:

```powershell
python -m memsu inbox init
```

Inspect paths and unprocessed files:

```powershell
python -m memsu inbox path
python -m memsu inbox list
```

Capture a quick note:

```powershell
python -m memsu inbox add --title "Future R5 idea" --content "advance run should be model-led, not checklist-led"
```

Promote one messy file into `tasks.md` and archive the source:

```powershell
python -m memsu inbox promote future-r5.md `
  --title "Implement model-led R5 advance run" `
  --scope "project:memSu" `
  --priority P2 `
  --acceptance "model receives context, task board, evidence, history, and capabilities" `
  --acceptance "low-risk result is written back with audit evidence"
```

Preview without writing or moving:

```powershell
python -m memsu inbox promote future-r5.md --title "Implement model-led R5 advance run" --dry-run
```

## Agent Behavior

The inbox is intentionally loose. The agent should:

- read unprocessed inbox files as user-owned raw material
- classify each file as task, context, reference, duplicate, or not actionable
- only promote concrete work into `tasks.md`
- keep vague principles or preferences in `inspire.md` / `inspire.d`
- move promoted source files into `inbox/archive/`
- preserve archive paths in the promoted task `source:` field

`advance agenda` surfaces unprocessed inbox files as an `organize_inbox`
suggestion so the agent can notice when the user has dropped new messy material.

Promotion does not execute the task. After promotion, an agent should claim the
task with `python -m memsu task claim <task_id> --agent <name>` before doing
work, then update status or release the claim when done.
