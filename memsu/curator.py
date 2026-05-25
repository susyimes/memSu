from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from .store import ACTIVE_STATUS, json_dumps, json_loads, stable_hash, tokenize, utc_now


def run_curator(
    conn: sqlite3.Connection,
    *,
    stale_days: int = 90,
    stale_salience_threshold: float = 0.3,
) -> dict[str, Any]:
    archived_duplicates = archive_duplicate_memories(conn)
    stale_marked = mark_stale_memories(
        conn,
        stale_days=stale_days,
        salience_threshold=stale_salience_threshold,
    )
    summaries = rebuild_memory_summaries(conn)
    conflicts = rebuild_conflict_queue(conn)

    result = {
        "archived_duplicates": archived_duplicates,
        "stale_marked": stale_marked,
        "summaries_written": summaries,
        "conflicts_opened": conflicts,
    }
    record_curator_run(conn, result)
    return result


def archive_duplicate_memories(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT *
        FROM memories
        WHERE status = ?
        ORDER BY scope, type, salience DESC, confidence DESC, updated_at DESC
        """,
        (ACTIVE_STATUS,),
    ).fetchall()

    groups: dict[tuple[str, str, str], list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        key = (row["scope"], row["type"], normalize_memory(row["content"]))
        groups[key].append(row)

    archived = 0
    now = utc_now()
    for duplicates in groups.values():
        if len(duplicates) <= 1:
            continue
        keep = duplicates[0]
        for row in duplicates[1:]:
            metadata = json_loads(row["metadata"], {})
            metadata.update(
                {
                    "archived_by": "curator",
                    "archive_reason": "duplicate",
                    "duplicate_of": keep["item_id"],
                }
            )
            conn.execute(
                """
                UPDATE memories
                SET status = 'archived', updated_at = ?, metadata = ?
                WHERE item_id = ?
                """,
                (now, json_dumps(metadata), row["item_id"]),
            )
            archived += 1
    return archived


def mark_stale_memories(
    conn: sqlite3.Connection,
    *,
    stale_days: int,
    salience_threshold: float,
) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=stale_days)).isoformat(timespec="seconds")
    rows = conn.execute(
        """
        SELECT *
        FROM memories
        WHERE status = ?
          AND salience <= ?
          AND COALESCE(last_used_at, updated_at) < ?
        """,
        (ACTIVE_STATUS, salience_threshold, cutoff),
    ).fetchall()

    now = utc_now()
    marked = 0
    for row in rows:
        metadata = json_loads(row["metadata"], {})
        metadata.update({"stale_by": "curator", "stale_cutoff": cutoff})
        conn.execute(
            """
            UPDATE memories
            SET status = 'stale', updated_at = ?, metadata = ?
            WHERE item_id = ?
            """,
            (now, json_dumps(metadata), row["item_id"]),
        )
        marked += 1
    return marked


def rebuild_memory_summaries(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM memory_summaries")
    rows = conn.execute(
        """
        SELECT *
        FROM memories
        WHERE status = ?
        ORDER BY scope, type, salience DESC, updated_at DESC
        """,
        (ACTIVE_STATUS,),
    ).fetchall()

    by_scope: dict[str, list[sqlite3.Row]] = defaultdict(list)
    by_scope_type: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        by_scope[row["scope"]].append(row)
        by_scope_type[(row["scope"], row["type"])].append(row)

    written = 0
    for scope, scoped_rows in by_scope.items():
        write_summary(
            conn,
            scope=scope,
            topic="project" if scope.startswith("project:") else "scope",
            kind="project" if scope.startswith("project:") else "scope",
            rows=scoped_rows,
        )
        written += 1

    for (scope, memory_type), typed_rows in by_scope_type.items():
        write_summary(
            conn,
            scope=scope,
            topic=memory_type,
            kind="topic",
            rows=typed_rows,
        )
        written += 1

    return written


def write_summary(
    conn: sqlite3.Connection,
    *,
    scope: str,
    topic: str,
    kind: str,
    rows: list[sqlite3.Row],
) -> None:
    now = utc_now()
    selected = rows[:8]
    item_ids = [row["item_id"] for row in selected]
    bullet_lines = [f"- [{row['type']}] {row['content']}" for row in selected[:5]]
    summary = "\n".join(bullet_lines)
    conn.execute(
        """
        INSERT INTO memory_summaries (
            summary_id, scope, topic, kind, summary, item_ids, created_at,
            updated_at, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"sum_{stable_hash(scope, topic, kind)[:24]}",
            scope,
            topic,
            kind,
            summary,
            json_dumps(item_ids),
            now,
            now,
            json_dumps({"item_count": len(rows)}),
        ),
    )


def rebuild_conflict_queue(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM conflict_reviews WHERE status = 'open'")
    candidates = conn.execute(
        """
        SELECT *
        FROM memory_candidates
        WHERE status = 'pending'
        ORDER BY updated_at DESC
        """
    ).fetchall()

    opened = 0
    now = utc_now()
    for candidate in candidates:
        metadata = json_loads(candidate["metadata"], {})
        conflict_ids = metadata.get("possible_conflict_item_ids") or []
        for item_id in conflict_ids:
            review_hash = stable_hash(candidate["candidate_id"], item_id)
            conn.execute(
                """
                INSERT OR IGNORE INTO conflict_reviews (
                    review_id, candidate_id, item_id, status, reason,
                    created_at, updated_at, metadata
                ) VALUES (?, ?, ?, 'open', ?, ?, ?, ?)
                """,
                (
                    f"conf_{review_hash[:24]}",
                    candidate["candidate_id"],
                    item_id,
                    "candidate_possible_conflict",
                    now,
                    now,
                    json_dumps({}),
                ),
            )
            opened += 1

    return opened


def record_curator_run(conn: sqlite3.Connection, result: dict[str, Any]) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO curator_runs (
            run_id, status, started_at, finished_at, result, metadata
        ) VALUES (?, 'completed', ?, ?, ?, ?)
        """,
        (
            f"cur_{stable_hash(now, json_dumps(result))[:24]}",
            now,
            now,
            json_dumps(result),
            json_dumps({}),
        ),
    )


def normalize_memory(content: str) -> str:
    return re.sub(r"\s+", " ", content.strip().lower())

