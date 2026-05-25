from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
PENDING_CANDIDATE_STATUS = "pending"
SUGGESTION_COOLDOWN_SECONDS = 300


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def utc_ago(seconds: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat(timespec="seconds")


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

                CREATE TABLE IF NOT EXISTS memory_candidates (
                    candidate_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    type TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.7,
                    salience REAL NOT NULL DEFAULT 0.5,
                    source_event_ids TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'pending',
                    candidate_hash TEXT NOT NULL,
                    accepted_item_id TEXT NOT NULL DEFAULT '',
                    reason TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_candidates_hash
                    ON memory_candidates(candidate_hash);
                CREATE INDEX IF NOT EXISTS idx_candidates_status
                    ON memory_candidates(status, updated_at);

                CREATE TABLE IF NOT EXISTS action_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    action_type TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    risk_level TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requires_confirmation INTEGER NOT NULL DEFAULT 0,
                    sensitivity TEXT NOT NULL DEFAULT 'normal',
                    reason TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_action_proposals_status
                    ON action_proposals(status, updated_at);

                CREATE TABLE IF NOT EXISTS policy_events (
                    policy_event_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL DEFAULT '',
                    event_type TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    timestamp TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_policy_events_timestamp
                    ON policy_events(timestamp);

                CREATE TABLE IF NOT EXISTS memory_summaries (
                    summary_id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    item_ids TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_memory_summaries_scope
                    ON memory_summaries(scope, kind);

                CREATE TABLE IF NOT EXISTS conflict_reviews (
                    review_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    reason TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_conflict_reviews_status
                    ON conflict_reviews(status, updated_at);

                CREATE TABLE IF NOT EXISTS curator_runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    result TEXT NOT NULL DEFAULT '{}',
                    metadata TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_curator_runs_finished
                    ON curator_runs(finished_at);
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
                       content_ref, artifact_refs, sensitivity, timestamp, metadata
                FROM events
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._event_row_to_dict(row) for row in rows]

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        self.init()
        with self.session() as conn:
            row = conn.execute(
                """
                SELECT event_id, source_agent, source_type, actor, event_type,
                       workspace, repo, cwd, thread_id, task_id, content,
                       content_ref, artifact_refs, sensitivity, timestamp, metadata
                FROM events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()
        return self._event_row_to_dict(row) if row else None

    def extract_candidates(
        self,
        *,
        event_id: str = "",
        limit: int = 50,
        auto_accept: bool = False,
    ) -> dict[str, Any]:
        from .extractor import extract_candidates_from_event

        self.init()
        if event_id:
            event = self.get_event(event_id)
            events = [event] if event else []
        else:
            events = self.list_events(limit=limit)

        created: list[dict[str, Any]] = []
        accepted: list[dict[str, Any]] = []
        skipped = 0
        for event in events:
            if not event:
                continue
            drafts = extract_candidates_from_event(event)
            if not drafts:
                skipped += 1
                continue
            for draft in drafts:
                candidate = self.propose_candidate(
                    draft.content,
                    type=draft.type,
                    scope=draft.scope,
                    confidence=draft.confidence,
                    salience=draft.salience,
                    source_event_ids=[event["event_id"]],
                    metadata={
                        **draft.metadata,
                        "source_agent": event.get("source_agent", ""),
                        "source_type": event.get("source_type", ""),
                    },
                )
                if candidate.get("duplicate"):
                    continue
                created.append(candidate)
                if auto_accept:
                    accepted.append(self.accept_candidate(candidate["candidate_id"]))

        return {
            "created_count": len(created),
            "accepted_count": len(accepted),
            "skipped_event_count": skipped,
            "candidates": created,
            "accepted": accepted,
        }

    def propose_candidate(
        self,
        content: str,
        *,
        type: str,
        scope: str,
        confidence: float = 0.7,
        salience: float = 0.5,
        source_event_ids: Iterable[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.init()
        if not content.strip():
            raise ValueError("candidate content cannot be empty")
        if type not in MEMORY_TYPES:
            raise ValueError(f"unsupported memory type: {type}")

        source_ids = list(source_event_ids or [])
        candidate_hash = stable_hash(content.strip().lower(), type, scope, json_dumps(source_ids))
        candidate_id = f"cand_{uuid.uuid4().hex}"
        now = utc_now()
        with self.session() as conn:
            candidate_metadata = dict(metadata or {})
            conflicts = self._find_possible_conflicts(
                conn, content=content.strip(), type=type, scope=scope
            )
            if conflicts:
                candidate_metadata["possible_conflict_item_ids"] = conflicts
            try:
                conn.execute(
                    """
                    INSERT INTO memory_candidates (
                        candidate_id, content, type, scope, confidence, salience,
                        source_event_ids, status, candidate_hash, created_at,
                        updated_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        candidate_id,
                        content.strip(),
                        type,
                        scope,
                        float(confidence),
                        float(salience),
                        json_dumps(source_ids),
                        PENDING_CANDIDATE_STATUS,
                        candidate_hash,
                        now,
                        now,
                        json_dumps(candidate_metadata),
                    ),
                )
                duplicate = False
            except sqlite3.IntegrityError:
                row = conn.execute(
                    "SELECT * FROM memory_candidates WHERE candidate_hash = ?",
                    (candidate_hash,),
                ).fetchone()
                duplicate = True
                candidate_id = row["candidate_id"]

        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            raise RuntimeError("failed to read candidate after insert")
        candidate["duplicate"] = duplicate
        return candidate

    def list_candidates(
        self,
        *,
        status: str = PENDING_CANDIDATE_STATUS,
        scope: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.init()
        with self.session() as conn:
            if scope:
                rows = conn.execute(
                    """
                    SELECT * FROM memory_candidates
                    WHERE status = ? AND scope = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (status, scope, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM memory_candidates
                    WHERE status = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (status, limit),
                ).fetchall()
        return [self._candidate_row_to_dict(row) for row in rows]

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        self.init()
        with self.session() as conn:
            row = conn.execute(
                "SELECT * FROM memory_candidates WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
        return self._candidate_row_to_dict(row) if row else None

    def accept_candidate(self, candidate_id: str) -> dict[str, Any]:
        candidate = self.get_candidate(candidate_id)
        if not candidate:
            return {"candidate_id": candidate_id, "status": "not_found"}
        if candidate["status"] == "accepted":
            return {
                "candidate_id": candidate_id,
                "status": "accepted",
                "item_id": candidate.get("accepted_item_id", ""),
            }
        if candidate["status"] != PENDING_CANDIDATE_STATUS:
            return {"candidate_id": candidate_id, "status": candidate["status"]}

        retained = self.retain_memory(
            candidate["content"],
            type=candidate["type"],
            scope=candidate["scope"],
            confidence=float(candidate["confidence"]),
            salience=float(candidate["salience"]),
            source_event_ids=candidate["source_event_ids"],
            metadata={
                **candidate["metadata"],
                "candidate_id": candidate_id,
                "accepted_from_candidate": True,
            },
        )
        now = utc_now()
        with self.session() as conn:
            conn.execute(
                """
                UPDATE memory_candidates
                SET status = 'accepted', accepted_item_id = ?, updated_at = ?
                WHERE candidate_id = ?
                """,
                (retained["item_id"], now, candidate_id),
            )
        return {
            "candidate_id": candidate_id,
            "status": "accepted",
            "item_id": retained["item_id"],
        }

    def reject_candidate(self, candidate_id: str, *, reason: str = "") -> dict[str, Any]:
        self.init()
        now = utc_now()
        with self.session() as conn:
            row = conn.execute(
                "SELECT status FROM memory_candidates WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            if not row:
                return {"candidate_id": candidate_id, "status": "not_found"}
            conn.execute(
                """
                UPDATE memory_candidates
                SET status = 'rejected', reason = ?, updated_at = ?
                WHERE candidate_id = ?
                """,
                (reason, now, candidate_id),
            )
        return {"candidate_id": candidate_id, "status": "rejected"}

    def evaluate_policy(
        self,
        *,
        action_type: str,
        description: str = "",
        sensitivity: str = "normal",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from .policy import evaluate_action

        self.init()
        decision = evaluate_action(
            action_type,
            description=description,
            sensitivity=sensitivity,
            metadata=metadata,
        )
        now = utc_now()
        proposal_id = f"act_{uuid.uuid4().hex}"
        with self.session() as conn:
            risk_level = decision.risk_level
            proposal_decision = decision.decision
            status = decision.status
            reason = decision.reason
            requires_confirmation = decision.requires_confirmation
            if decision.risk_level == "L2":
                if (metadata or {}).get("quiet_hours_active") is True:
                    proposal_decision = "defer"
                    status = "deferred"
                    reason = "Quiet hours are active; suggestion is deferred."
                elif self._has_recent_policy_proposal(
                    conn,
                    action_type=decision.action_type,
                    since=utc_ago(SUGGESTION_COOLDOWN_SECONDS),
                ):
                    proposal_decision = "defer"
                    status = "deferred"
                    reason = "Rate limit: similar suggestion was recently recorded."

            conn.execute(
                """
                INSERT INTO action_proposals (
                    proposal_id, action_type, description, risk_level, decision,
                    status, requires_confirmation, sensitivity, reason, created_at,
                    updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    decision.action_type,
                    description,
                    risk_level,
                    proposal_decision,
                    status,
                    1 if requires_confirmation else 0,
                    sensitivity,
                    reason,
                    now,
                    now,
                    json_dumps(metadata),
                ),
            )
            self._insert_policy_event(
                conn,
                proposal_id=proposal_id,
                event_type="evaluated",
                action_type=decision.action_type,
                risk_level=risk_level,
                decision=proposal_decision,
                reason=reason,
                metadata=metadata,
            )
        proposal = self.get_action_proposal(proposal_id)
        if proposal is None:
            raise RuntimeError("failed to read action proposal after insert")
        return proposal

    def list_action_proposals(
        self,
        *,
        status: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.init()
        with self.session() as conn:
            if status:
                rows = conn.execute(
                    """
                    SELECT * FROM action_proposals
                    WHERE status = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM action_proposals
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [self._proposal_row_to_dict(row) for row in rows]

    def get_action_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        self.init()
        with self.session() as conn:
            row = conn.execute(
                "SELECT * FROM action_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        return self._proposal_row_to_dict(row) if row else None

    def decide_action_proposal(
        self,
        proposal_id: str,
        *,
        decision: str,
        reason: str = "",
    ) -> dict[str, Any]:
        normalized = decision.strip().lower()
        if normalized not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject")

        current = self.get_action_proposal(proposal_id)
        if not current:
            return {"proposal_id": proposal_id, "status": "not_found"}
        if current["status"] != "pending_confirmation":
            return {"proposal_id": proposal_id, "status": current["status"]}

        new_status = "approved" if normalized == "approve" else "rejected"
        now = utc_now()
        with self.session() as conn:
            conn.execute(
                """
                UPDATE action_proposals
                SET status = ?, decision = ?, reason = ?, updated_at = ?
                WHERE proposal_id = ?
                """,
                (new_status, normalized, reason or current["reason"], now, proposal_id),
            )
            self._insert_policy_event(
                conn,
                proposal_id=proposal_id,
                event_type=new_status,
                action_type=current["action_type"],
                risk_level=current["risk_level"],
                decision=normalized,
                reason=reason,
                metadata=current["metadata"],
            )
        return self.get_action_proposal(proposal_id) or {
            "proposal_id": proposal_id,
            "status": new_status,
        }

    def list_policy_events(self, *, limit: int = 50) -> list[dict[str, Any]]:
        self.init()
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM policy_events
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._policy_event_row_to_dict(row) for row in rows]

    def run_curator(
        self,
        *,
        stale_days: int = 90,
        stale_salience_threshold: float = 0.3,
    ) -> dict[str, Any]:
        from .curator import run_curator

        self.init()
        with self.session() as conn:
            return run_curator(
                conn,
                stale_days=stale_days,
                stale_salience_threshold=stale_salience_threshold,
            )

    def list_memory_summaries(
        self,
        *,
        scope: str = "",
        kind: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.init()
        with self.session() as conn:
            clauses = []
            params: list[Any] = []
            if scope:
                clauses.append("scope = ?")
                params.append(scope)
            if kind:
                clauses.append("kind = ?")
                params.append(kind)
            where = "WHERE " + " AND ".join(clauses) if clauses else ""
            rows = conn.execute(
                f"""
                SELECT *
                FROM memory_summaries
                {where}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [self._summary_row_to_dict(row) for row in rows]

    def list_conflict_reviews(
        self,
        *,
        status: str = "open",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.init()
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM conflict_reviews
                WHERE status = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (status, limit),
            ).fetchall()
        return [self._conflict_row_to_dict(row) for row in rows]

    def list_curator_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        self.init()
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM curator_runs
                ORDER BY finished_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._curator_run_row_to_dict(row) for row in rows]

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
            pending_candidate_count = conn.execute(
                "SELECT COUNT(*) FROM memory_candidates WHERE status = ?",
                (PENDING_CANDIDATE_STATUS,),
            ).fetchone()[0]
            pending_action_count = conn.execute(
                "SELECT COUNT(*) FROM action_proposals WHERE status = ?",
                ("pending_confirmation",),
            ).fetchone()[0]
            open_conflict_count = conn.execute(
                "SELECT COUNT(*) FROM conflict_reviews WHERE status = ?",
                ("open",),
            ).fetchone()[0]
        return {
            "ok": True,
            "db_path": str(self.db_path),
            "event_count": event_count,
            "active_memory_count": memory_count,
            "pending_candidate_count": pending_candidate_count,
            "pending_action_count": pending_action_count,
            "open_conflict_count": open_conflict_count,
        }

    def _event_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "event_id": row["event_id"],
            "source_agent": row["source_agent"],
            "source_type": row["source_type"],
            "actor": row["actor"],
            "event_type": row["event_type"],
            "workspace": row["workspace"],
            "repo": row["repo"],
            "cwd": row["cwd"],
            "thread_id": row["thread_id"],
            "task_id": row["task_id"],
            "content": row["content"],
            "content_ref": row["content_ref"],
            "artifact_refs": json_loads(row["artifact_refs"], []),
            "sensitivity": row["sensitivity"],
            "timestamp": row["timestamp"],
            "metadata": json_loads(row["metadata"], {}),
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

    def _candidate_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "candidate_id": row["candidate_id"],
            "content": row["content"],
            "type": row["type"],
            "scope": row["scope"],
            "confidence": row["confidence"],
            "salience": row["salience"],
            "source_event_ids": json_loads(row["source_event_ids"], []),
            "status": row["status"],
            "candidate_hash": row["candidate_hash"],
            "accepted_item_id": row["accepted_item_id"],
            "reason": row["reason"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "metadata": json_loads(row["metadata"], {}),
        }

    def _find_possible_conflicts(
        self,
        conn: sqlite3.Connection,
        *,
        content: str,
        type: str,
        scope: str,
    ) -> list[str]:
        candidate_terms = tokenize(content)
        if len(candidate_terms) < 3:
            return []

        rows = conn.execute(
            """
            SELECT item_id, content
            FROM memories
            WHERE status = ? AND type = ? AND scope = ?
            ORDER BY updated_at DESC
            LIMIT 50
            """,
            (ACTIVE_STATUS, type, scope),
        ).fetchall()

        conflicts: list[str] = []
        normalized_content = content.strip().lower()
        for row in rows:
            existing_content = row["content"].strip().lower()
            if existing_content == normalized_content:
                continue
            existing_terms = tokenize(existing_content)
            if not existing_terms:
                continue
            overlap = len(candidate_terms & existing_terms)
            denominator = max(1, min(len(candidate_terms), len(existing_terms)))
            if overlap >= 3 and overlap / denominator >= 0.5:
                conflicts.append(row["item_id"])

        return conflicts

    def _insert_policy_event(
        self,
        conn: sqlite3.Connection,
        *,
        proposal_id: str,
        event_type: str,
        action_type: str,
        risk_level: str,
        decision: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO policy_events (
                policy_event_id, proposal_id, event_type, action_type,
                risk_level, decision, reason, timestamp, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"pol_{uuid.uuid4().hex}",
                proposal_id,
                event_type,
                action_type,
                risk_level,
                decision,
                reason,
                utc_now(),
                json_dumps(metadata),
            ),
        )

    def _has_recent_policy_proposal(
        self,
        conn: sqlite3.Connection,
        *,
        action_type: str,
        since: str,
    ) -> bool:
        row = conn.execute(
            """
            SELECT 1
            FROM action_proposals
            WHERE action_type = ? AND created_at >= ?
            LIMIT 1
            """,
            (action_type, since),
        ).fetchone()
        return row is not None

    def _proposal_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "proposal_id": row["proposal_id"],
            "action_type": row["action_type"],
            "description": row["description"],
            "risk_level": row["risk_level"],
            "decision": row["decision"],
            "status": row["status"],
            "requires_confirmation": bool(row["requires_confirmation"]),
            "sensitivity": row["sensitivity"],
            "reason": row["reason"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "metadata": json_loads(row["metadata"], {}),
        }

    def _policy_event_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "policy_event_id": row["policy_event_id"],
            "proposal_id": row["proposal_id"],
            "event_type": row["event_type"],
            "action_type": row["action_type"],
            "risk_level": row["risk_level"],
            "decision": row["decision"],
            "reason": row["reason"],
            "timestamp": row["timestamp"],
            "metadata": json_loads(row["metadata"], {}),
        }

    def _summary_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "summary_id": row["summary_id"],
            "scope": row["scope"],
            "topic": row["topic"],
            "kind": row["kind"],
            "summary": row["summary"],
            "item_ids": json_loads(row["item_ids"], []),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "metadata": json_loads(row["metadata"], {}),
        }

    def _conflict_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "review_id": row["review_id"],
            "candidate_id": row["candidate_id"],
            "item_id": row["item_id"],
            "status": row["status"],
            "reason": row["reason"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "metadata": json_loads(row["metadata"], {}),
        }

    def _curator_run_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "run_id": row["run_id"],
            "status": row["status"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "result": json_loads(row["result"], {}),
            "metadata": json_loads(row["metadata"], {}),
        }
