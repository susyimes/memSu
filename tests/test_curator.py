from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memsu.store import MemSuStore


class CuratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = MemSuStore(Path(self.temp_dir.name) / "memsu.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_curator_archives_duplicates_and_writes_summaries(self) -> None:
        first = self.store.retain_memory(
            "memSu keeps memory review-first",
            type="decision",
            scope="project:memSu",
            salience=0.8,
        )
        duplicate = self.store.retain_memory(
            "memSu keeps memory review-first",
            type="decision",
            scope="project:memSu",
            salience=0.4,
        )

        result = self.store.run_curator()

        self.assertEqual(1, result["archived_duplicates"])
        active = self.store.audit(scope="project:memSu", status="active")
        archived = self.store.audit(scope="project:memSu", status="archived")
        self.assertEqual(first["item_id"], active[0]["item_id"])
        self.assertEqual(duplicate["item_id"], archived[0]["item_id"])

        summaries = self.store.list_memory_summaries(scope="project:memSu")
        self.assertGreaterEqual(len(summaries), 1)
        self.assertIn("memSu keeps memory review-first", summaries[0]["summary"])

    def test_curator_marks_old_low_salience_memory_stale(self) -> None:
        retained = self.store.retain_memory(
            "old low salience implementation detail",
            type="note",
            scope="project:memSu",
            salience=0.1,
        )
        self.store.init()
        with self.store.session() as conn:
            conn.execute(
                """
                UPDATE memories
                SET updated_at = '2000-01-01T00:00:00+00:00',
                    last_used_at = '2000-01-01T00:00:00+00:00'
                WHERE item_id = ?
                """,
                (retained["item_id"],),
            )

        result = self.store.run_curator(stale_days=1, stale_salience_threshold=0.3)

        self.assertEqual(1, result["stale_marked"])
        stale = self.store.audit(scope="project:memSu", status="stale")
        self.assertEqual(retained["item_id"], stale[0]["item_id"])

    def test_curator_builds_conflict_review_queue(self) -> None:
        existing = self.store.retain_memory(
            "memSu uses SQLite store for local memory",
            type="decision",
            scope="project:memSu",
        )
        event = self.store.append_event(
            source_agent="codex",
            source_type="conversation",
            actor="agent",
            event_type="conversation_turn",
            content="Decision: memSu uses Postgres store for local memory.",
            repo="susyimes/memSu",
        )
        extracted = self.store.extract_candidates(event_id=event["event_id"])
        candidate_id = extracted["candidates"][0]["candidate_id"]

        result = self.store.run_curator()

        self.assertEqual(1, result["conflicts_opened"])
        conflicts = self.store.list_conflict_reviews()
        self.assertEqual(candidate_id, conflicts[0]["candidate_id"])
        self.assertEqual(existing["item_id"], conflicts[0]["item_id"])

    def test_curator_runs_are_recorded(self) -> None:
        self.store.retain_memory(
            "memSu records curator runs",
            type="note",
            scope="project:memSu",
        )

        self.store.run_curator()

        runs = self.store.list_curator_runs()
        self.assertEqual("completed", runs[0]["status"])
        self.assertIn("summaries_written", runs[0]["result"])


if __name__ == "__main__":
    unittest.main()

