from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from memsu.hardening import privacy_scan
from memsu.store import MemSuStore


class HardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store = MemSuStore(self.root / "memsu.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_backup_export_and_migration_status(self) -> None:
        self.store.retain_memory(
            "memSu backup export test",
            type="note",
            scope="project:memSu",
        )

        backup = self.store.create_backup(backup_dir=self.root / "backups")
        export = self.store.export_json(output_path=self.root / "export.json")
        migrations = self.store.migration_status()

        self.assertTrue(Path(backup["backup_path"]).exists())
        self.assertTrue(Path(export["export_path"]).exists())
        exported = json.loads(Path(export["export_path"]).read_text(encoding="utf-8"))
        self.assertIn("memories", exported["tables"])
        self.assertGreaterEqual(migrations["schema_version"], 1)

    def test_privacy_scan_redacts_sensitive_preview(self) -> None:
        self.store.append_event(
            source_agent="shell",
            source_type="command",
            actor="user",
            event_type="command_run",
            content="token=super-secret-value user@example.com",
        )

        result = privacy_scan(self.store)

        self.assertEqual(2, result["finding_count"])
        previews = " ".join(item["preview"] for item in result["findings"])
        self.assertIn("[REDACTED]", previews)
        self.assertIn("[EMAIL]", previews)

    def test_vector_index_recall(self) -> None:
        self.store.retain_memory(
            "sparse vector backend ranks local memory",
            type="note",
            scope="project:memSu",
        )
        self.store.rebuild_vector_index()

        recalled = self.store.vector_recall("vector local memory", scope="project:memSu")

        self.assertEqual(1, len(recalled))
        self.assertGreater(recalled[0]["vector_score"], 0)


if __name__ == "__main__":
    unittest.main()
