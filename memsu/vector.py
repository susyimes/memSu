from __future__ import annotations

import math
import sqlite3
from collections import Counter
from typing import Any

from .store import ACTIVE_STATUS, json_dumps, json_loads, tokenize, utc_now


def rebuild_vector_index(conn: sqlite3.Connection) -> dict[str, Any]:
    conn.execute("DELETE FROM vector_index")
    rows = conn.execute(
        """
        SELECT item_id, scope, content
        FROM memories
        WHERE status = ?
        """,
        (ACTIVE_STATUS,),
    ).fetchall()
    now = utc_now()
    count = 0
    for row in rows:
        terms = Counter(tokenize(row["content"]))
        conn.execute(
            """
            INSERT INTO vector_index (
                item_id, scope, terms_json, updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            (row["item_id"], row["scope"], json_dumps(dict(terms)), now),
        )
        count += 1
    return {"indexed_count": count}


def sparse_vector_recall(
    conn: sqlite3.Connection,
    *,
    query: str,
    scope: str = "",
    limit: int = 5,
) -> list[dict[str, Any]]:
    query_terms = Counter(tokenize(query))
    if not query_terms:
        return []

    if scope:
        rows = conn.execute(
            """
            SELECT v.item_id, v.terms_json, m.content, m.type, m.scope, m.confidence, m.salience
            FROM vector_index v
            JOIN memories m ON m.item_id = v.item_id
            WHERE m.status = ? AND (v.scope = ? OR v.scope = 'global_user')
            """,
            (ACTIVE_STATUS, scope),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT v.item_id, v.terms_json, m.content, m.type, m.scope, m.confidence, m.salience
            FROM vector_index v
            JOIN memories m ON m.item_id = v.item_id
            WHERE m.status = ?
            """,
            (ACTIVE_STATUS,),
        ).fetchall()

    scored: list[tuple[float, sqlite3.Row]] = []
    for row in rows:
        terms = Counter(json_loads(row["terms_json"], {}))
        score = cosine(query_terms, terms)
        if score > 0:
            scored.append((score, row))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "item_id": row["item_id"],
            "content": row["content"],
            "type": row["type"],
            "scope": row["scope"],
            "confidence": row["confidence"],
            "salience": row["salience"],
            "vector_score": score,
        }
        for score, row in scored[:limit]
    ]


def cosine(left: Counter[str], right: Counter[str]) -> float:
    shared = set(left) & set(right)
    numerator = sum(left[key] * right[key] for key in shared)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)

