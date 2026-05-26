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

        path.write_text("custom user notes", encoding="utf-8")
        second = ensure_inspire_files()
        self.assertFalse(second["created"])
        self.assertEqual("custom user notes", read_inspire()["content"])

        forced = ensure_inspire_files(overwrite=True)
        self.assertTrue(forced["created"])
        self.assertIn("memSu Observation Inspire", read_inspire()["content"])


if __name__ == "__main__":
    unittest.main()
