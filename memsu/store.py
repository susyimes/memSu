from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .paths import default_db_path


EVENT_TYPES = {
    "conversation_turn",
    "tool_call",
    "command_run",
    "git_event",
    "workflow_result",
    "artifact_created",
    "memory_write",
    "delegation_result",
    "session_summary",
}

MEMORY_TYPES = {
    "preference",
    "project_rule",
    "fact",
    "decision",
    "workflow_lesson",
    "failure_pattern",
    "skill_candidate",
    "note",
}

ACTIVE_STATUS = "active"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_hash(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update((part or "").encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[A-Za-z0-9_]+", text.lower()) if len(t) > 1}


@dataclass(frozen=True)
class EventRecord:
    event_id: str
    source_agent: str
    source_type: str
    actor: str
    event_type: str
    content: str
    timestamp: str


@dataclass(frozen=True)
class MemoryRecord:
    item_id: str
    content: str
    type: str
    scope: str
    confidence: float
    salience: float
    status: str
    created_at: str
    updated_at: str
    last_used_at: str | None


class MemSuStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else default_db_path()

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def session(self):
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> None:
        with self.session() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    source_agent TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    workspace TEXT NOT NULL DEFAULT '',
                    repo TEXT NOT NULL DEFAULT '',
                    cwd TEXT NOT NULL DEFAULT '',
                    thread_id TEXT NOT NULL DEFAULT '',
                    task_id TEXT NOT NULL DEFAULT '',
                    event_type TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    content_ref TEXT NOT NULL DEFAULT '',
                    artifact_refs TEXT NOT NULL DEFAULT '[]',
                    sensitivity TEXT NOT NULL DEFAULT 'normal',
                    source_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_events_source_hash
                    ON events(source_hash);
                CREATE INDEX IF NOT EXISTS idx_events_scope
                    ON events(source_agent, workspace, repo, thread_id);
                CREATE INDEX IF NOT EXISTS idx_events_timestamp
                    ON events(timestamp);

                CREATE TABLE IF NOT EXISTS memories (
                    item_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    type TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.7,
                    salience REAL NOT NULL DEFAULT 0.5,
                    source_event_ids TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_used_at TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_memories_scope
                    ON memories(scope, status);
                CREATE INDEX IF NOT EXISTS idx_memories_type
                    ON memories(type, status);
                """
            )

    def append_event(
        self,
        *,
        source_agent: str,
        source_type: str,
        actor: str,
        event_type: str,
        content: str = "",
        workspace: str = "",
        repo: str = "",
        cwd: str = "",
        thread_id: str = "",
        task_id: str = "",
        content_ref: str = "",
        artifact_refs: Iterable[str] | None = None,
        sensitivity: str = "normal",
        metadata: dict[str, Any] | None = None,
        timestamp: str | None = None,
        source_hash: str | None = None,
    ) -> dict[str, Any]:
        self.init()
        event_type = event_type or "conversation_turn"
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported event_type: {event_type}")

        timestamp = timestamp or utc_now()
        artifact_refs_list = list(artifact_refs or [])
        source_hash = source_hash or stable_hash(
            source_agent,
            source_type,
            actor,
            event_type,
            workspace,
            repo,
            cwd,
            thread_id,
            task_id,
            content,
            json_dumps(artifact_refs_list),
        )
        event_id = f"evt_{uuid.uuid4().hex}"

        with self.session() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO events (
                        event_id, source_agent, source_type, actor, workspace, repo,
                        cwd, thread_id, task_id, event_type, content, content_ref,
                        artifact_refs, sensitivity, source_hash, timestamp, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        source_agent,
                        source_type,
                        actor,
                        workspace,
                        repo,
                        cwd,
                        thread_id,
                        task_id,
                        event_type,
                        content,
                        content_ref,
                        json_dumps(artifact_refs_list),
                        sensitivity,
                        source_hash,
                        timestamp,
                        json_dumps(metadata),
                    ),
                )
                duplicate = False
            except sqlite3.IntegrityError:
                row = conn.execute(
                    "SELECT * FROM events WHERE source_hash = ?", (source_hash,)
                ).fetchone()
                duplicate = True
                event_id = row["event_id"]

        return {"event_id": event_id, "source_hash": source_hash, "duplicate": duplicate}

    def list_events(self, limit: int = 20) -> list[dict[str, Any]]:
        self.init()
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT event_id, source_agent, source_type, actor, event_type,
                       workspace, repo, cwd, thread_id, task_id, content,
                       sensitivity, timestamp, metadata
                FROM events
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def retain_memory(
        self,
        content: str,
        *,
        type: str = "note",
        scope: str = "global_user",
        confidence: float = 0.7,
        salience: float = 0.5,
        source_event_ids: Iterable[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.init()
        if not content.strip():
            raise ValueError("memory content cannot be empty")
        if type not in MEMORY_TYPES:
            raise ValueError(f"unsupported memory type: {type}")
        now = utc_now()
        item_id = f"mem_{uuid.uuid4().hex}"
        with self.session() as conn:
            conn.execute(
                """
                INSERT INTO memories (
                    item_id, content, type, scope, confidence, salience,
                    source_event_ids, status, created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    content.strip(),
                    type,
                    scope,
                    float(confidence),
                    float(salience),
                    json_dumps(list(source_event_ids or [])),
                    ACTIVE_STATUS,
                    now,
                    now,
                    json_dumps(metadata),
                ),
            )
        return {"item_id": item_id, "status": ACTIVE_STATUS}

    def recall(self, query: str, *, scope: str = "", limit: int = 5) -> list[dict[str, Any]]:
        self.init()
        query_terms = tokenize(query)
        if not query_terms:
            return []

        with self.session() as conn:
            if scope:
                rows = conn.execute(
                    """
                    SELECT * FROM memories
                    WHERE status = ? AND (scope = ? OR scope = 'global_user')
                    ORDER BY salience DESC, updated_at DESC
                    LIMIT 200
                    """,
                    (ACTIVE_STATUS, scope),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM memories
                    WHERE status = ?
                    ORDER BY salience DESC, updated_at DESC
                    LIMIT 200
                    """,
                    (ACTIVE_STATUS,),
                ).fetchall()

            scored: list[tuple[float, sqlite3.Row]] = []
            for row in rows:
                text = f"{row['content']} {row['type']} {row['scope']}"
                terms = tokenize(text)
                overlap = len(query_terms & terms)
                if overlap == 0:
                    continue
                score = overlap + float(row["salience"]) + float(row["confidence"])
                scored.append((score, row))

            scored.sort(key=lambda item: item[0], reverse=True)
            selected = scored[:limit]
            now = utc_now()
            for _, row in selected:
                conn.execute(
                    "UPDATE memories SET last_used_at = ? WHERE item_id = ?",
                    (now, row["item_id"]),
                )

        return [self._memory_row_to_dict(row, score=score) for score, row in selected]

    def audit(
        self,
        *,
        scope: str = "",
        status: str = ACTIVE_STATUS,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.init()
        with self.session() as conn:
            if scope:
                rows = conn.execute(
                    """
                    SELECT * FROM memories
                    WHERE status = ? AND scope = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (status, scope, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM memories
                    WHERE status = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (status, limit),
                ).fetchall()
        return [self._memory_row_to_dict(row) for row in rows]

    def forget(self, item_id: str, *, reason: str = "") -> dict[str, Any]:
        self.init()
        now = utc_now()
        with self.session() as conn:
            row = conn.execute(
                "SELECT metadata FROM memories WHERE item_id = ?", (item_id,)
            ).fetchone()
            if not row:
                return {"item_id": item_id, "status": "not_found"}
            metadata = json_loads(row["metadata"], {})
            if reason:
                metadata["forget_reason"] = reason
            conn.execute(
                """
                UPDATE memories
                SET status = 'archived', updated_at = ?, metadata = ?
                WHERE item_id = ?
                """,
                (now, json_dumps(metadata), item_id),
            )
        return {"item_id": item_id, "status": "archived"}

    def health(self) -> dict[str, Any]:
        self.init()
        with self.session() as conn:
            event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            memory_count = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE status = ?", (ACTIVE_STATUS,)
            ).fetchone()[0]
        return {
            "ok": True,
            "db_path": str(self.db_path),
            "event_count": event_count,
            "active_memory_count": memory_count,
        }

    def _memory_row_to_dict(
        self, row: sqlite3.Row, *, score: float | None = None
    ) -> dict[str, Any]:
        result = {
            "item_id": row["item_id"],
            "content": row["content"],
            "type": row["type"],
            "scope": row["scope"],
            "confidence": row["confidence"],
            "salience": row["salience"],
            "source_event_ids": json_loads(row["source_event_ids"], []),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_used_at": row["last_used_at"],
            "metadata": json_loads(row["metadata"], {}),
        }
        if score is not None:
            result["score"] = score
        return result
