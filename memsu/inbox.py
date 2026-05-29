from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import default_inbox_archive_dir, default_inbox_dir, default_tasks_path, memsu_home
from .store import stable_hash, utc_now
from .tasks import TASK_STATUSES, ensure_task_board, parse_task_board, normalize_status


INBOX_README = """# memSu Inbox

Drop messy notes, future work, task fragments, links, and raw context here.

Humans do not need to follow the task board format in this folder. Agents should
read these files, promote real tasks into `../tasks.md`, and then move the
source file into `archive/`.
"""

TEXT_SUFFIXES = {".md", ".txt", ".text"}
RESERVED_NAMES = {"README.md"}


@dataclass(frozen=True)
class InboxFile:
    path: Path
    relative_path: str
    size: int
    modified_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "relative_path": self.relative_path,
            "size": self.size,
            "modified_at": self.modified_at,
        }


def ensure_inbox() -> dict[str, Any]:
    inbox_dir = default_inbox_dir()
    archive_dir = default_inbox_archive_dir()
    inbox_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
    readme = inbox_dir / "README.md"
    created_readme = False
    if not readme.exists():
        readme.write_text(INBOX_README, encoding="utf-8")
        created_readme = True
    files = list_inbox_files()
    return {
        "inbox_dir": str(inbox_dir),
        "archive_dir": str(archive_dir),
        "created_readme": created_readme,
        "user_editable": True,
        "file_count": len(files),
    }


def inbox_status() -> dict[str, Any]:
    inbox_dir = default_inbox_dir()
    archive_dir = default_inbox_archive_dir()
    files = list_inbox_files() if inbox_dir.exists() else []
    return {
        "inbox_dir": str(inbox_dir),
        "archive_dir": str(archive_dir),
        "exists": inbox_dir.exists(),
        "archive_exists": archive_dir.exists(),
        "user_editable": True,
        "file_count": len(files),
    }


def read_inbox() -> dict[str, Any]:
    status = inbox_status()
    files = list_inbox_files() if Path(status["inbox_dir"]).exists() else []
    return {
        **status,
        "files": [item.to_dict() for item in files],
    }


def capture_inbox_note(
    *,
    title: str,
    content: str,
    now: str | None = None,
) -> dict[str, Any]:
    ensure_inbox()
    timestamp = now or utc_now()
    name = f"{compact_timestamp(timestamp)}-{slugify(title) or 'note'}.md"
    path = unique_path(default_inbox_dir() / name)
    body = content.rstrip() + "\n" if content.strip() else ""
    text = f"# {one_line(title) or 'Inbox note'}\n\n{body}"
    path.write_text(text, encoding="utf-8")
    return {
        "ok": True,
        "status": "captured",
        "path": str(path),
        "relative_path": inbox_relative_path(path),
    }


def promote_inbox_file(
    file_ref: str,
    *,
    title: str = "",
    status: str = "todo",
    priority: str = "P2",
    scope: str = "",
    context: str = "",
    blocked: str = "",
    acceptance: list[str] | None = None,
    note: str = "",
    dry_run: bool = False,
    now: str | None = None,
) -> dict[str, Any]:
    ensure_inbox()
    source = resolve_inbox_file(file_ref)
    if not source.exists():
        return {"ok": False, "status": "not_found", "path": str(source)}
    if source.is_dir():
        return {"ok": False, "status": "not_file", "path": str(source)}
    if source.suffix.lower() not in TEXT_SUFFIXES:
        return {
            "ok": False,
            "status": "unsupported_file_type",
            "path": str(source),
            "supported_suffixes": sorted(TEXT_SUFFIXES),
        }

    source_text = source.read_text(encoding="utf-8")
    task_title = one_line(title) or infer_title(source_text, source)
    task_status = normalize_status(status or "todo")
    if task_status not in TASK_STATUSES:
        return {
            "ok": False,
            "status": "invalid_status",
            "allowed_statuses": sorted(TASK_STATUSES),
        }
    task_context = context.strip() or compact_text(source_text, 500)
    task_acceptance = acceptance or []
    timestamp = now or utc_now()
    archive_path = planned_archive_path(source, timestamp=timestamp)
    archive_ref = inbox_relative_path(archive_path)
    task_markdown = render_task_markdown(
        title=task_title,
        status=task_status,
        priority=priority,
        scope=scope,
        context=task_context,
        blocked=blocked,
        acceptance=task_acceptance,
        source=archive_ref,
        source_name=inbox_relative_path(source),
        note=note,
    )
    if dry_run:
        return {
            "ok": True,
            "status": "planned",
            "source_path": str(source),
            "archive_path": str(archive_path),
            "task_markdown": task_markdown,
        }

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path = unique_path(archive_path)
    shutil.move(str(source), str(archive_path))
    archive_ref = inbox_relative_path(archive_path)
    task_markdown = render_task_markdown(
        title=task_title,
        status=task_status,
        priority=priority,
        scope=scope,
        context=task_context,
        blocked=blocked,
        acceptance=task_acceptance,
        source=archive_ref,
        source_name=inbox_relative_path(source),
        note=note,
    )
    append_task_markdown(task_markdown)
    task = find_latest_task(title=task_title, scope=scope)
    return {
        "ok": True,
        "status": "promoted",
        "source_path": str(source),
        "archive_path": str(archive_path),
        "archive_relative_path": archive_ref,
        "tasks_path": str(default_tasks_path()),
        "task": task,
    }


def list_inbox_files() -> list[InboxFile]:
    inbox_dir = default_inbox_dir()
    if not inbox_dir.exists():
        return []
    archive_dir = default_inbox_archive_dir()
    files: list[InboxFile] = []
    for path in inbox_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.name in RESERVED_NAMES:
            continue
        if is_relative_to(path.resolve(), archive_dir.resolve()):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        stat = path.stat()
        files.append(
            InboxFile(
                path=path.resolve(),
                relative_path=inbox_relative_path(path),
                size=stat.st_size,
                modified_at=utc_from_timestamp(stat.st_mtime),
            )
        )
    return sorted(files, key=lambda item: item.modified_at, reverse=True)


def append_task_markdown(task_markdown: str) -> None:
    ensure_task_board()
    path = default_tasks_path()
    existing = path.read_text(encoding="utf-8") if path.exists() else "# memSu Tasks\n"
    separator = "\n\n" if existing.rstrip() else ""
    path.write_text(existing.rstrip() + separator + task_markdown.rstrip() + "\n", encoding="utf-8")


def find_latest_task(*, title: str, scope: str) -> dict[str, Any]:
    path = default_tasks_path()
    tasks = parse_task_board(path.read_text(encoding="utf-8") if path.exists() else "")
    matches = [task for task in tasks if task.title == title and task.scope == scope]
    return matches[-1].to_dict() if matches else {}


def render_task_markdown(
    *,
    title: str,
    status: str,
    priority: str,
    scope: str,
    context: str,
    blocked: str,
    acceptance: list[str],
    source: str,
    source_name: str,
    note: str,
) -> str:
    lines = [
        f"## [{status}][{priority or 'P2'}] {title}",
        "",
        f"scope: {scope}",
        f"context: {one_line(context)}",
        f"source: {source}",
        "claimed_by:",
        "claimed_at:",
        "claim_until:",
        f"blocked: {one_line(blocked)}",
        "",
        "acceptance:",
    ]
    if acceptance:
        lines.extend(f"- {one_line(item)}" for item in acceptance)
    else:
        lines.append("- Agent should refine acceptance after reading the archived inbox source.")
    lines.extend(
        [
            "",
            "notes:",
            f"- Promoted from inbox file `{source_name}`.",
        ]
    )
    if note:
        lines.append(f"- {one_line(note)}")
    return "\n".join(lines)


def resolve_inbox_file(file_ref: str) -> Path:
    inbox_dir = default_inbox_dir().resolve()
    path = Path(file_ref).expanduser()
    if not path.is_absolute():
        path = inbox_dir / path
    resolved = path.resolve()
    if not is_relative_to(resolved, inbox_dir):
        raise ValueError(f"inbox file must be inside {inbox_dir}")
    if is_relative_to(resolved, default_inbox_archive_dir().resolve()):
        raise ValueError("archived inbox files cannot be promoted again")
    return resolved


def planned_archive_path(source: Path, *, timestamp: str) -> Path:
    date = timestamp[:10] if len(timestamp) >= 10 else "unknown-date"
    name = f"{compact_timestamp(timestamp)}-{source.name}"
    return default_inbox_archive_dir() / date / name


def inbox_relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(default_inbox_dir().resolve()).as_posix()
    except ValueError:
        return str(path)


def infer_title(content: str, source: Path) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        stripped = stripped.lstrip("#").strip()
        if stripped:
            return compact_text(stripped, 80)
    return source.stem.replace("_", " ").replace("-", " ").strip() or "Inbox task"


def compact_text(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip()


def one_line(value: str) -> str:
    return compact_text(value, 240)


def slugify(value: str) -> str:
    lowered = value.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if slug:
        return slug[:60]
    return stable_hash(value)[:12]


def compact_timestamp(value: str) -> str:
    return (
        value.replace("-", "")
        .replace(":", "")
        .replace("+0000", "Z")
        .replace("+00:00", "Z")
        .replace(".", "")
    )


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for index in range(2, 1000):
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not find unique path for {path}")


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def utc_from_timestamp(value: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(value, tz=timezone.utc).replace(microsecond=0).isoformat()
