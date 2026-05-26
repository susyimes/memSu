from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from memsu.inspire import ensure_inspire_files, read_inspire


class InspireTests(unittest.TestCase):
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

    def test_inspire_template_is_created_but_not_overwritten(self) -> None:
        created = ensure_inspire_files()
        path = Path(created["inspire_path"])
        self.assertTrue(path.exists())
        self.assertTrue(Path(created["inspire_dir"]).exists())
        self.assertTrue(created["user_editable"])
        created_names = [Path(item).name for item in created["created_files"]]
        self.assertIn("00-v4-loop.md", created_names)
        self.assertIn("05-local-signal-surfaces.md", created_names)
        self.assertIn("agents.md", created_names)

        path.write_text("custom user notes", encoding="utf-8")
        local_signals = Path(created["inspire_dir"]) / "05-local-signal-surfaces.md"
        local_signals.write_text("custom local signals", encoding="utf-8")
        second = ensure_inspire_files()
        self.assertFalse(second["created"])
        self.assertEqual([], second["created_files"])
        self.assertTrue(read_inspire()["content"].startswith("custom user notes"))
        self.assertIn("custom local signals", read_inspire()["content"])

        forced = ensure_inspire_files(overwrite=True)
        self.assertTrue(forced["created"])
        self.assertTrue(forced["created_files"])
        forced_content = read_inspire()["content"]
        self.assertIn("memSu V4 观察启发配置", forced_content)
        self.assertIn("V4 本地观察信号面", forced_content)
        self.assertIn("本地 agent 会话元数据", forced_content)

    def test_inspire_dir_markdown_files_are_read_after_main_file(self) -> None:
        created = ensure_inspire_files()
        path = Path(created["inspire_path"])
        inspire_dir = Path(created["inspire_dir"])
        path.write_text("main notes", encoding="utf-8")
        (inspire_dir / "agents.md").write_text("agent notes", encoding="utf-8")
        (inspire_dir / "projects.md").write_text("project notes", encoding="utf-8")
        (inspire_dir / "ignored.txt").write_text("ignored notes", encoding="utf-8")

        inspire = read_inspire()

        self.assertIn("main notes", inspire["content"])
        self.assertIn("# inspire.d/agents.md", inspire["content"])
        self.assertIn("agent notes", inspire["content"])
        self.assertIn("# inspire.d/projects.md", inspire["content"])
        self.assertIn("project notes", inspire["content"])
        self.assertNotIn("ignored notes", inspire["content"])
        inspire_file_names = [Path(item).name for item in inspire["inspire_files"]]
        self.assertIn("agents.md", inspire_file_names)
        self.assertIn("projects.md", inspire_file_names)


if __name__ == "__main__":
    unittest.main()
