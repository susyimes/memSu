from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

from .paths import memsu_home
from .store import MemSuStore, utc_now


SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("secret_assignment", re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
)


EXPORT_TABLES = [
    "events",
    "memories",
    "memory_candidates",
    "action_proposals",
    "policy_events",
    "memory_summaries",
    "conflict_reviews",
    "curator_runs",
    "vector_index",
]


def create_backup(store: MemSuStore, *, backup_dir: str | Path | None = None) -> dict[str, Any]:
    store.init()
    target_dir = Path(backup_dir) if backup_dir else memsu_home() / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    compact_ts = utc_now().replace(":", "").replace("+", "Z")
    backup_path = target_dir / f"memsu-{compact_ts}.db"

    source = store.connect()
    try:
        dest = sqlite3.connect(backup_path)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()

    return {"ok": True, "backup_path": str(backup_path), "bytes": backup_path.stat().st_size}


def export_json(store: MemSuStore, *, output_path: str | Path | None = None) -> dict[str, Any]:
    store.init()
    payload: dict[str, Any] = {
        "exported_at": utc_now(),
        "db_path": str(store.db_path),
        "tables": {},
    }
    with store.session() as conn:
        existing_tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        for table in EXPORT_TABLES:
            if table not in existing_tables:
                continue
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            payload["tables"][table] = [dict(row) for row in rows]

    if output_path:
        path = Path(output_path)
    else:
        export_dir = memsu_home() / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        compact_ts = utc_now().replace(":", "").replace("+", "Z")
        path = export_dir / f"memsu-{compact_ts}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "export_path": str(path), "tables": sorted(payload["tables"].keys())}


def privacy_scan(store: MemSuStore, *, limit: int = 200) -> dict[str, Any]:
    store.init()
    findings: list[dict[str, Any]] = []
    scan_targets = [
        ("events", "event_id", "content"),
        ("memories", "item_id", "content"),
        ("memory_candidates", "candidate_id", "content"),
    ]
    with store.session() as conn:
        for table, id_column, text_column in scan_targets:
            rows = conn.execute(
                f"SELECT {id_column} AS id, {text_column} AS content FROM {table} ORDER BY rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
            for row in rows:
                content = row["content"] or ""
                for kind, pattern in SENSITIVE_PATTERNS:
                    if pattern.search(content):
                        findings.append(
                            {
                                "table": table,
                                "id": row["id"],
                                "kind": kind,
                                "preview": redact_preview(content),
                            }
                        )
    return {"ok": True, "finding_count": len(findings), "findings": findings}


def service_status(*, pid_file: str | Path | None = None) -> dict[str, Any]:
    path = Path(pid_file) if pid_file else memsu_home() / "memsu.pid"
    if not path.exists():
        return {"running": False, "pid_file": str(path), "reason": "pid file missing"}
    raw_pid = path.read_text(encoding="utf-8", errors="replace").strip()
    try:
        pid = int(raw_pid)
    except ValueError:
        return {"running": False, "pid_file": str(path), "reason": "invalid pid file"}
    running = is_pid_running(pid)
    return {"running": running, "pid": pid, "pid_file": str(path)}


def service_stop(*, pid_file: str | Path | None = None) -> dict[str, Any]:
    status = service_status(pid_file=pid_file)
    if not status.get("running"):
        return status
    pid = int(status["pid"])
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {"running": True, "pid": pid, "error": result.stderr.strip() or result.stdout.strip()}
    else:
        try:
            os.kill(pid, 15)
        except Exception as exc:
            return {"running": True, "pid": pid, "error": str(exc)}
    return {"running": False, "pid": pid, "stopped": True}


def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False
        output = result.stdout.strip()
        return str(pid) in output and "No tasks" not in output
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except PermissionError:
        return True
    return True


def redact_preview(content: str, limit: int = 160) -> str:
    preview = content[:limit]
    preview = re.sub(r"(?i)(api[_-]?key|token|secret|password)(\s*[:=]\s*)\S+", r"\1\2[REDACTED]", preview)
    preview = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[EMAIL]", preview)
    return preview
