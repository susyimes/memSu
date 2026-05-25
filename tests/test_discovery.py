from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from memsu.discovery import capabilities_manifest, ensure_discovery_files, status_payload
from memsu.store import MemSuStore


class DiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.previous_home = os.environ.get("MEMSU_HOME")
        os.environ["MEMSU_HOME"] = str(self.root)

    def tearDown(self) -> None:
        if self.previous_home is None:
            os.environ.pop("MEMSU_HOME", None)
        else:
            os.environ["MEMSU_HOME"] = self.previous_home
        self.temp_dir.cleanup()

    def test_manifest_paths_are_machine_independent(self) -> None:
        manifest = capabilities_manifest()
        rendered = str(manifest)

        self.assertIn("${MEMSU_HOME:-~/.memsu}", rendered)
        self.assertNotIn(str(self.root), rendered)
        self.assertFalse(manifest["service_required"])

    def test_status_reports_resolved_paths_after_init(self) -> None:
        store = MemSuStore(self.root / "memsu.db")
        store.init()
        files = ensure_discovery_files()

        status = status_payload(store)

        self.assertTrue(status["ok"])
        self.assertTrue(status["initialized"])
        self.assertEqual("cli-first", status["mode"])
        self.assertTrue(Path(files["install_marker"]).exists())
        self.assertEqual(str(self.root), status["resolved_paths"]["home"])
        self.assertEqual("${MEMSU_HOME:-~/.memsu}", status["manifest_templates"]["home"])


if __name__ == "__main__":
    unittest.main()
