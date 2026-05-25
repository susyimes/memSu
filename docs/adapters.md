# memSu Adapters

Adapters are explicit observation entrypoints. They convert local work into
structured events without hidden monitoring.

The MVP includes:

- shell command result adapter
- git repository snapshot adapter
- Codex transcript adapter
- generic agent transcript adapter
- generic workflow result adapter

Adapters do not automatically accept memory. They append events to the event log.
The extraction pipeline can then create pending memory candidates for review.

## Shell

Record an already-run command:

```powershell
python -m memsu adapter shell `
  --command "python -m unittest discover -s tests" `
  --exit-code 0 `
  --cwd . `
  --workspace memSu `
  --repo susyimes/memSu `
  --stdout "OK"
```

The shell adapter records command, exit code, stdout, stderr, duration, scope
fields, and sensitivity. It does not execute the command.

## Git

Record a repository snapshot:

```powershell
python -m memsu adapter git --repo-path . --workspace memSu
```

This captures branch, HEAD, latest commit, remote, and `git status --short`.

## Codex

Ingest an exported transcript:

```powershell
python -m memsu adapter codex .\codex-session.md --workspace memSu --repo susyimes/memSu
```

Supported formats:

- NDJSON with `role`/`content`, `actor`/`message`, or `type`/`text`
- simple Markdown sections headed by `# User`, `# Assistant`, `# System`,
  `# Tool`, or `# Codex`
- fallback to one transcript event if no structured format is recognized

## Generic Agent Transcript

For Gemini, Kimi, Claude, or another local agent transcript:

```powershell
python -m memsu adapter transcript --agent gemini .\gemini-session.md --workspace memSu --repo susyimes/memSu
```

The parser accepts the same NDJSON and Markdown formats as the Codex adapter,
but records the configured `source_agent`.

## Workflow

Record a workflow result:

```powershell
python -m memsu adapter workflow `
  --name test `
  --status passed `
  --summary "unit tests passed" `
  --workspace memSu `
  --repo susyimes/memSu
```

## Integration Contract

Adapters are CLI-first. Any trusted local agent can call these commands and
write to the same local SQLite store. There is no resident HTTP adapter API in
V2; add one back only after a measured need for high-frequency, low-latency
access appears.
