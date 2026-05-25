from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .store import MemSuStore


MAX_CAPTURE_CHARS = 8000


def truncate(value: str, limit: int = MAX_CAPTURE_CHARS) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n...[truncated {len(value) - limit} chars]"


def record_shell_command(
    store: MemSuStore,
    *,
    command: str,
    cwd: str = "",
    exit_code: int = 0,
    stdout: str = "",
    stderr: str = "",
    duration_ms: int | None = None,
    workspace: str = "",
    repo: str = "",
    task_id: str = "",
    sensitivity: str = "normal",
) -> dict[str, Any]:
    content_parts = [f"$ {command}", f"exit_code: {exit_code}"]
    if stdout:
        content_parts.append("stdout:\n" + truncate(stdout))
    if stderr:
        content_parts.append("stderr:\n" + truncate(stderr))

    return store.append_event(
        source_agent="shell",
        source_type="command",
        actor="user",
        event_type="command_run",
        content="\n".join(content_parts),
        workspace=workspace,
        repo=repo,
        cwd=cwd,
        task_id=task_id,
        sensitivity=sensitivity,
        metadata={
            "command": command,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
        },
    )


def snapshot_git_repo(
    store: MemSuStore,
    *,
    repo_path: str,
    workspace: str = "",
    sensitivity: str = "normal",
) -> dict[str, Any]:
    path = Path(repo_path).expanduser().resolve()
    branch = run_git(path, ["branch", "--show-current"])
    head = run_git(path, ["rev-parse", "--short", "HEAD"])
    status = run_git(path, ["status", "--short"])
    remote = run_git(path, ["remote", "get-url", "origin"], allow_failure=True)
    recent = run_git(path, ["log", "-1", "--pretty=%h %s"], allow_failure=True)
    repo_name = remote_to_repo_name(remote) or path.name

    content = "\n".join(
        [
            f"repo: {repo_name}",
            f"path: {path}",
            f"branch: {branch}",
            f"head: {head}",
            f"latest: {recent}",
            "status:",
            status or "clean",
        ]
    )

    return store.append_event(
        source_agent="git",
        source_type="repository",
        actor="system",
        event_type="git_event",
        content=content,
        workspace=workspace or path.name,
        repo=repo_name,
        cwd=str(path),
        sensitivity=sensitivity,
        metadata={
            "branch": branch,
            "head": head,
            "remote": remote,
            "status_short": status,
            "latest_commit": recent,
        },
    )


def ingest_codex_transcript(
    store: MemSuStore,
    *,
    path: str,
    workspace: str = "",
    repo: str = "",
    thread_id: str = "",
    sensitivity: str = "normal",
) -> dict[str, Any]:
    transcript_path = Path(path).expanduser().resolve()
    text = transcript_path.read_text(encoding="utf-8", errors="replace")
    events = parse_codex_transcript(text)
    if not events:
        events = [{"role": "unknown", "content": truncate(text)}]

    appended: list[dict[str, Any]] = []
    for index, event in enumerate(events, start=1):
        role = event.get("role") or "unknown"
        content = event.get("content") or ""
        appended.append(
            store.append_event(
                source_agent="codex",
                source_type="transcript",
                actor=role,
                event_type="conversation_turn",
                content=truncate(content),
                workspace=workspace,
                repo=repo,
                thread_id=thread_id,
                content_ref=str(transcript_path),
                sensitivity=sensitivity,
                metadata={"entry_index": index, "role": role},
            )
        )

    return {"count": len(appended), "events": appended}


def ingest_agent_transcript(
    store: MemSuStore,
    *,
    agent: str,
    path: str,
    workspace: str = "",
    repo: str = "",
    thread_id: str = "",
    sensitivity: str = "normal",
) -> dict[str, Any]:
    transcript_path = Path(path).expanduser().resolve()
    text = transcript_path.read_text(encoding="utf-8", errors="replace")
    events = parse_codex_transcript(text)
    if not events:
        events = [{"role": "unknown", "content": truncate(text)}]

    appended: list[dict[str, Any]] = []
    for index, event in enumerate(events, start=1):
        role = event.get("role") or "unknown"
        appended.append(
            store.append_event(
                source_agent=agent,
                source_type="transcript",
                actor=role,
                event_type="conversation_turn",
                content=truncate(event.get("content") or ""),
                workspace=workspace,
                repo=repo,
                thread_id=thread_id,
                content_ref=str(transcript_path),
                sensitivity=sensitivity,
                metadata={"entry_index": index, "role": role, "adapter": "generic_transcript"},
            )
        )
    return {"count": len(appended), "events": appended}


def record_workflow_result(
    store: MemSuStore,
    *,
    name: str,
    status: str,
    summary: str,
    workspace: str = "",
    repo: str = "",
    cwd: str = "",
    task_id: str = "",
    artifact_refs: list[str] | None = None,
    sensitivity: str = "normal",
) -> dict[str, Any]:
    content = f"workflow: {name}\nstatus: {status}\nsummary:\n{truncate(summary)}"
    return store.append_event(
        source_agent="workflow",
        source_type=name,
        actor="system",
        event_type="workflow_result",
        content=content,
        workspace=workspace,
        repo=repo,
        cwd=cwd,
        task_id=task_id,
        artifact_refs=artifact_refs or [],
        sensitivity=sensitivity,
        metadata={"workflow": name, "status": status},
    )


def parse_codex_transcript(text: str) -> list[dict[str, str]]:
    stripped = text.strip()
    if not stripped:
        return []

    ndjson_events = parse_ndjson_transcript(stripped)
    if ndjson_events:
        return ndjson_events

    markdown_events: list[dict[str, str]] = []
    current_role = ""
    current_lines: list[str] = []
    for raw_line in stripped.splitlines():
        line = raw_line.strip()
        lowered = line.lower().strip("# ")
        if lowered in {"user", "assistant", "system", "tool", "codex"}:
            if current_role and current_lines:
                markdown_events.append(
                    {"role": current_role, "content": "\n".join(current_lines).strip()}
                )
            current_role = lowered
            current_lines = []
        else:
            current_lines.append(raw_line)

    if current_role and current_lines:
        markdown_events.append(
            {"role": current_role, "content": "\n".join(current_lines).strip()}
        )

    return [event for event in markdown_events if event["content"]]


def parse_ndjson_transcript(text: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, dict):
            continue
        role = str(payload.get("role") or payload.get("actor") or payload.get("type") or "unknown")
        content = payload.get("content") or payload.get("message") or payload.get("text") or ""
        if isinstance(content, list):
            content = "\n".join(str(part) for part in content)
        if content:
            events.append({"role": role, "content": str(content)})
    return events


def run_git(repo_path: Path, args: list[str], *, allow_failure: bool = False) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0 and not allow_failure:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return (result.stdout or result.stderr).strip()


def remote_to_repo_name(remote: str) -> str:
    if not remote:
        return ""
    cleaned = remote.strip()
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    if cleaned.startswith("git@") and ":" in cleaned:
        return cleaned.split(":", 1)[1]
    marker = "github.com/"
    if marker in cleaned:
        return cleaned.split(marker, 1)[1]
    return ""
