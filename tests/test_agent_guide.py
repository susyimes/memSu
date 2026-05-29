from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from memsu.agent_guide import agent_guide_status, ensure_agent_guide, read_agent_guide
from memsu.cli import main
from memsu.paths import default_agent_guide_path


class AgentGuideTests(unittest.TestCase):
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

    def test_agent_guide_created_and_readable(self) -> None:
        result = ensure_agent_guide()

        self.assertTrue(result["created"])
        self.assertEqual(str(self.root / "AGENTS.md"), result["agent_guide_path"])
        self.assertTrue(default_agent_guide_path().exists())

        content = read_agent_guide()["content"]
        self.assertIn("Read Order", content)
        self.assertIn("python -m memsu inbox promote", content)
        self.assertIn("python -m memsu task claim", content)
        self.assertIn("python -m memsu advance agenda", content)
        self.assertIn("Do not copy private user alignment files", content)

    def test_agent_guide_status_does_not_create_file(self) -> None:
        status = agent_guide_status()

        self.assertFalse(status["exists"])
        self.assertFalse(default_agent_guide_path().exists())

    def test_cli_guide_commands_smoke(self) -> None:
        self.assertEqual(0, main(["guide", "path"]))
        self.assertEqual(0, main(["guide", "init"]))
        self.assertTrue(default_agent_guide_path().exists())
        self.assertEqual(0, main(["guide", "show"]))
        self.assertEqual(0, main(["guide", "init", "--force"]))

    def test_cli_init_creates_agent_guide(self) -> None:
        self.assertEqual(0, main(["init"]))

        self.assertTrue(default_agent_guide_path().exists())
        guide = read_agent_guide()
        self.assertTrue(guide["exists"])
        self.assertIn("memSu Agent Guide", guide["content"])


if __name__ == "__main__":
    unittest.main()
