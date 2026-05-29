from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from memsu.agent_guide import ensure_agent_guide
from memsu.discovery import capabilities_manifest, ensure_discovery_files, status_payload
from memsu.inbox import ensure_inbox
from memsu.inspire import ensure_inspire_files
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
        self.assertEqual("${MEMSU_HOME:-~/.memsu}/AGENTS.md", manifest["paths"]["agent_guide"])
        self.assertIn("guide_show", manifest["commands"])

    def test_status_reports_resolved_paths_after_init(self) -> None:
        store = MemSuStore(self.root / "memsu.db")
        store.init()
        files = ensure_discovery_files()
        agent_guide = ensure_agent_guide()
        inspire = ensure_inspire_files()
        inbox = ensure_inbox()

        status = status_payload(store)

        self.assertTrue(status["ok"])
        self.assertTrue(status["initialized"])
        self.assertEqual("cli-first", status["mode"])
        self.assertTrue(Path(files["install_marker"]).exists())
        self.assertTrue(Path(agent_guide["agent_guide_path"]).exists())
        self.assertTrue(Path(inspire["inspire_path"]).exists())
        self.assertTrue(Path(inbox["inbox_dir"]).exists())
        self.assertEqual(str(self.root), status["resolved_paths"]["home"])
        self.assertEqual(str(self.root / "AGENTS.md"), status["resolved_paths"]["agent_guide"])
        self.assertEqual(str(self.root / "inspire.md"), status["resolved_paths"]["inspire"])
        self.assertEqual(str(self.root / "inbox"), status["resolved_paths"]["inbox"])
        self.assertEqual(str(self.root / "inbox" / "archive"), status["resolved_paths"]["inbox_archive"])
        self.assertEqual(str(self.root / "tasks.md"), status["resolved_paths"]["tasks"])
        self.assertEqual("${MEMSU_HOME:-~/.memsu}", status["manifest_templates"]["home"])
        self.assertEqual("${MEMSU_HOME:-~/.memsu}/AGENTS.md", status["manifest_templates"]["agent_guide"])
        self.assertEqual("${MEMSU_HOME:-~/.memsu}/inspire.md", status["manifest_templates"]["inspire"])
        self.assertEqual("${MEMSU_HOME:-~/.memsu}/inbox", status["manifest_templates"]["inbox"])
        self.assertEqual("${MEMSU_HOME:-~/.memsu}/inbox/archive", status["manifest_templates"]["inbox_archive"])
        self.assertEqual("${MEMSU_HOME:-~/.memsu}/tasks.md", status["manifest_templates"]["tasks"])
        self.assertTrue(status["files"]["agent_guide"])


if __name__ == "__main__":
    unittest.main()
