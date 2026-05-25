from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memsu.store import MemSuStore


class MemSuStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "memsu.db"
        self.store = MemSuStore(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_event_append_is_deduped_by_source_hash(self) -> None:
        first = self.store.append_event(
            source_agent="codex",
            source_type="command",
            actor="agent",
            event_type="command_run",
            content="ran tests",
        )
        second = self.store.append_event(
            source_agent="codex",
            source_type="command",
            actor="agent",
            event_type="command_run",
            content="ran tests",
        )

        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["event_id"], second["event_id"])

    def test_retain_recall_and_forget_memory(self) -> None:
        retained = self.store.retain_memory(
            "memSu should prefer scoped SQLite memory in the MVP",
            type="decision",
            scope="project:memsu",
            salience=0.9,
        )

        recalled = self.store.recall("SQLite memory", scope="project:memsu")
        self.assertEqual(1, len(recalled))
        self.assertEqual(retained["item_id"], recalled[0]["item_id"])

        forgotten = self.store.forget(retained["item_id"], reason="test")
        self.assertEqual("archived", forgotten["status"])
        self.assertEqual([], self.store.recall("SQLite memory", scope="project:memsu"))
        archived = self.store.audit(scope="project:memsu", status="archived")
        self.assertEqual(retained["item_id"], archived[0]["item_id"])


if __name__ == "__main__":
    unittest.main()

