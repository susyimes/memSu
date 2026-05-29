from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .paths import default_tasks_path
from .store import stable_hash, utc_now


TASK_STATUSES = {
    "todo",
    "active",
    "blocked",
    "verifying",
    "done",
    "dropped",
}


TASK_TEMPLATE = """# memSu Tasks

## [todo][P1] Stabilize observe-to-assistance loop

scope: project:memSu
context: Describe why this task matters and what local context should be considered.
claimed_by:
claimed_at:
claim_until:
blocked:

acceptance:
- advance agenda reads this task board.
- suggestions can cite both observe evidence and task ids.

notes:
- Humans can drop messy notes into inbox/ first. Agents promote structured tasks here and archive the source.
- memSu may update status, but should leave history.
"""


HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
TOKEN_RE = re.compile(r"^\[([^\]]+)\]\s*")
FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$")


@dataclass(frozen=True)
class ParsedTask:
    task_id: str
    title: str
    status: str
    priority: str
    scope: str
    context: str
    source: str
    claimed_by: str
    claimed_at: str
    claim_until: str
    blocked: str
    acceptance: list[str]
    notes: str
    line_start: int
    line_end: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "scope": self.scope,
            "context": self.context,
            "source": self.source,
            "claimed_by": self.claimed_by,
            "claimed_at": self.claimed_at,
            "claim_until": self.claim_until,
            "blocked": self.blocked,
            "acceptance": self.acceptance,
            "notes": self.notes,
            "line_start": self.line_start,
            "line_end": self.line_end,
        }


def ensure_task_board(*, overwrite: bool = False) -> dict[str, Any]:
    path = default_tasks_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    if overwrite or not path.exists():
        path.write_text(TASK_TEMPLATE, encoding="utf-8")
        created = True
    tasks = parse_task_board(path.read_text(encoding="utf-8") if path.exists() else "")
    return {
        "tasks_path": str(path),
        "created": created,
        "user_editable": True,
        "task_count": len(tasks),
    }


def task_board_status() -> dict[str, Any]:
    path = default_tasks_path()
    tasks = parse_task_board(path.read_text(encoding="utf-8")) if path.exists() else []
    return {
        "tasks_path": str(path),
        "exists": path.exists(),
        "user_editable": True,
        "task_count": len(tasks),
    }


def read_task_board() -> dict[str, Any]:
    status = task_board_status()
    path = Path(status["tasks_path"])
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    tasks = parse_task_board(content)
    return {
        **status,
        "content": content,
        "tasks": [task.to_dict() for task in tasks],
    }


def get_task(task_id: str) -> dict[str, Any] | None:
    for task in read_task_board()["tasks"]:
        if task["task_id"] == task_id:
            return task
    return None


def update_task_status(
    task_id: str,
    *,
    status: str,
    note: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    normalized_status = normalize_status(status)
    if normalized_status not in TASK_STATUSES:
        return {
            "ok": False,
            "status": "invalid_status",
            "allowed_statuses": sorted(TASK_STATUSES),
        }

    path = default_tasks_path()
    if not path.exists():
        return {"ok": False, "status": "task_board_missing", "tasks_path": str(path)}

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tasks = parse_task_board(text)
    matched = next((task for task in tasks if task.task_id == task_id), None)
    if matched is None:
        return {"ok": False, "status": "not_found", "task_id": task_id}

    old_status = matched.status
    heading_index = matched.line_start - 1
    lines[heading_index] = update_heading_status(lines[heading_index], normalized_status)
    timestamp = now or utc_now()
    bullet = f"- {timestamp} status {old_status} -> {normalized_status}"
    if note:
        bullet += f"; note: {note}"
    insert_history(lines, matched.line_end, bullet)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    updated = get_task(task_id)
    return {
        "ok": True,
        "status": "updated",
        "task_id": task_id,
        "old_status": old_status,
        "new_status": normalized_status,
        "tasks_path": str(path),
        "task": updated,
    }


def claim_task(
    task_id: str,
    *,
    agent: str,
    lease: str = "2h",
    note: str = "",
    force: bool = False,
    now: str | None = None,
) -> dict[str, Any]:
    agent_name = agent.strip()
    if not agent_name:
        return {"ok": False, "status": "missing_agent"}
    duration = parse_lease_duration(lease)
    if duration is None:
        return {"ok": False, "status": "invalid_lease", "expected": "examples: 30m, 2h, 1d"}

    path = default_tasks_path()
    if not path.exists():
        return {"ok": False, "status": "task_board_missing", "tasks_path": str(path)}

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    matched = find_task(text, task_id)
    if matched is None:
        return {"ok": False, "status": "not_found", "task_id": task_id}
    if matched.claimed_by and matched.claimed_by != agent_name and not force:
        return {
            "ok": False,
            "status": "already_claimed",
            "task_id": task_id,
            "claimed_by": matched.claimed_by,
            "claim_until": matched.claim_until,
        }

    timestamp = now or utc_now()
    claim_until = (parse_iso_timestamp(timestamp) + duration).isoformat(timespec="seconds")
    for key, value in {
        "claimed_by": agent_name,
        "claimed_at": timestamp,
        "claim_until": claim_until,
    }.items():
        upsert_task_field(lines, matched, key, value)
        refreshed = find_task("\n".join(lines), task_id)
        if refreshed is None:
            return {"ok": False, "status": "not_found_after_update", "task_id": task_id}
        matched = refreshed
    updated_match = matched
    if updated_match is None:
        return {"ok": False, "status": "not_found_after_update", "task_id": task_id}
    bullet = f"- {timestamp} claimed by {agent_name}; lease_until: {claim_until}"
    if matched.claimed_by and matched.claimed_by != agent_name:
        bullet += f"; previous: {matched.claimed_by}"
    if note:
        bullet += f"; note: {note}"
    insert_history(lines, updated_match.line_end, bullet)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "status": "claimed",
        "task_id": task_id,
        "agent": agent_name,
        "claim_until": claim_until,
        "tasks_path": str(path),
        "task": get_task(task_id),
    }


def release_task(
    task_id: str,
    *,
    agent: str = "",
    note: str = "",
    force: bool = False,
    now: str | None = None,
) -> dict[str, Any]:
    agent_name = agent.strip()
    path = default_tasks_path()
    if not path.exists():
        return {"ok": False, "status": "task_board_missing", "tasks_path": str(path)}

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    matched = find_task(text, task_id)
    if matched is None:
        return {"ok": False, "status": "not_found", "task_id": task_id}
    if agent_name and matched.claimed_by and matched.claimed_by != agent_name and not force:
        return {
            "ok": False,
            "status": "claimed_by_mismatch",
            "task_id": task_id,
            "claimed_by": matched.claimed_by,
        }

    timestamp = now or utc_now()
    previous = matched.claimed_by
    remove_task_fields(lines, matched, {"claimed_by", "claimed_at", "claim_until"})
    updated_match = find_task("\n".join(lines), task_id)
    if updated_match is None:
        return {"ok": False, "status": "not_found_after_update", "task_id": task_id}
    bullet = f"- {timestamp} claim released"
    if previous:
        bullet += f"; previous: {previous}"
    if agent_name:
        bullet += f"; by: {agent_name}"
    if note:
        bullet += f"; note: {note}"
    insert_history(lines, updated_match.line_end, bullet)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "status": "released",
        "task_id": task_id,
        "previous_claimed_by": previous,
        "tasks_path": str(path),
        "task": get_task(task_id),
    }


def find_task(text: str, task_id: str) -> ParsedTask | None:
    return next((task for task in parse_task_board(text) if task.task_id == task_id), None)


def parse_lease_duration(value: str) -> timedelta | None:
    text = (value or "2h").strip().lower()
    match = re.fullmatch(r"([1-9][0-9]*)([smhd])", text)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "s":
        return timedelta(seconds=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    return None


def parse_iso_timestamp(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def upsert_task_field(lines: list[str], task: ParsedTask, field_name: str, value: str) -> None:
    start = task.line_start
    end = min(task.line_end, len(lines))
    for index in range(start, end):
        match = FIELD_RE.match(lines[index].strip())
        if match and match.group(1).strip().lower() == field_name.lower():
            lines[index] = f"{field_name}: {value}"
            return
    insert_at = task_field_insert_index(lines, start=start, end=end)
    lines.insert(insert_at, f"{field_name}: {value}")


def remove_task_fields(lines: list[str], task: ParsedTask, field_names: set[str]) -> None:
    start = task.line_start
    end = min(task.line_end, len(lines))
    lowered = {item.lower() for item in field_names}
    kept: list[str] = []
    for index, line in enumerate(lines):
        if start <= index < end:
            match = FIELD_RE.match(line.strip())
            if match and match.group(1).strip().lower() in lowered:
                continue
        kept.append(line)
    lines[:] = kept


def task_field_insert_index(lines: list[str], *, start: int, end: int) -> int:
    for anchor in ["blocked", "acceptance", "notes", "history"]:
        for index in range(start, end):
            match = FIELD_RE.match(lines[index].strip())
            if match and match.group(1).strip().lower() == anchor:
                return index
    return end


def parse_task_board(text: str) -> list[ParsedTask]:
    lines = text.splitlines()
    heading_indexes = [
        index for index, line in enumerate(lines)
        if HEADING_RE.match(line)
    ]
    tasks: list[ParsedTask] = []
    seen_keys: dict[str, int] = {}
    for position, start_index in enumerate(heading_indexes):
        end_index = heading_indexes[position + 1] if position + 1 < len(heading_indexes) else len(lines)
        heading = lines[start_index]
        raw_title = HEADING_RE.match(heading).group(1)  # type: ignore[union-attr]
        heading_data = parse_heading(raw_title)
        block_lines = lines[start_index + 1:end_index]
        fields = parse_fields(block_lines)
        title = heading_data["title"]
        status = normalize_status(fields.get("status") or heading_data["status"] or "todo")
        priority = fields.get("priority") or heading_data["priority"]
        scope = fields.get("scope", "")
        key = f"{title}\0{scope}"
        seen_keys[key] = seen_keys.get(key, 0) + 1
        explicit_id = fields.get("id", "")
        task_id = explicit_id or generated_task_id(title=title, scope=scope, occurrence=seen_keys[key])
        tasks.append(
            ParsedTask(
                task_id=task_id,
                title=title,
                status=status,
                priority=priority,
                scope=scope,
                context=fields.get("context", ""),
                source=fields.get("source", ""),
                claimed_by=fields.get("claimed_by", ""),
                claimed_at=fields.get("claimed_at", ""),
                claim_until=fields.get("claim_until", ""),
                blocked=fields.get("blocked", ""),
                acceptance=parse_list_field(block_lines, "acceptance"),
                notes=fields.get("notes", ""),
                line_start=start_index + 1,
                line_end=end_index,
            )
        )
    return tasks


def parse_heading(raw_title: str) -> dict[str, str]:
    text = raw_title.strip()
    status = ""
    priority = ""
    while True:
        match = TOKEN_RE.match(text)
        if not match:
            break
        token = match.group(1).strip()
        normalized = normalize_status(token)
        if normalized in TASK_STATUSES and not status:
            status = normalized
        elif is_priority(token) and not priority:
            priority = token.upper()
        text = text[match.end():].strip()
    return {"title": text, "status": status, "priority": priority}


def parse_fields(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in lines:
        match = FIELD_RE.match(line.strip())
        if not match:
            continue
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        fields[key] = value
    return fields


def parse_list_field(lines: list[str], field_name: str) -> list[str]:
    items: list[str] = []
    in_field = False
    target = f"{field_name.lower()}:"
    for line in lines:
        stripped = line.strip()
        if not in_field:
            if stripped.lower() == target:
                in_field = True
            continue
        if not stripped:
            if items:
                break
            continue
        if FIELD_RE.match(stripped) and not stripped.startswith("-"):
            break
        if stripped.startswith("-"):
            items.append(stripped[1:].strip())
    return items


def normalize_status(value: str) -> str:
    return (value or "").strip().lower().replace("_", "-")


def is_priority(value: str) -> bool:
    return bool(re.fullmatch(r"(?i)p[0-9]+|low|medium|high", value.strip()))


def generated_task_id(*, title: str, scope: str, occurrence: int) -> str:
    suffix = "" if occurrence <= 1 else f":{occurrence}"
    return f"task_{stable_hash(title.strip().lower(), scope.strip().lower(), suffix)[:12]}"


def update_heading_status(heading: str, status: str) -> str:
    match = HEADING_RE.match(heading)
    if not match:
        return heading
    title = match.group(1).strip()
    tokens: list[str] = []
    remainder = title
    replaced = False
    while True:
        token_match = TOKEN_RE.match(remainder)
        if not token_match:
            break
        token = token_match.group(1).strip()
        if normalize_status(token) in TASK_STATUSES and not replaced:
            tokens.append(status)
            replaced = True
        else:
            tokens.append(token)
        remainder = remainder[token_match.end():].strip()
    if not replaced:
        tokens.insert(0, status)
    token_text = "".join(f"[{token}]" for token in tokens)
    return f"## {token_text} {remainder}".rstrip()


def insert_history(lines: list[str], task_end_index: int, bullet: str) -> None:
    insert_at = task_end_index
    task_start = 0
    for index in range(insert_at - 1, -1, -1):
        if HEADING_RE.match(lines[index]):
            task_start = index
            break
    block = lines[task_start:insert_at]
    has_history = any(line.strip().lower() == "history:" for line in block)
    additions: list[str] = []
    if lines and insert_at > 0 and lines[insert_at - 1].strip():
        additions.append("")
    if not has_history:
        additions.append("history:")
    additions.append(bullet)
    lines[insert_at:insert_at] = additions
