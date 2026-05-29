from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from memsu.cli import main
from memsu.tasks import claim_task, ensure_task_board, read_task_board, release_task, update_task_status


class TaskBoardTests(unittest.TestCase):
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

    def test_task_board_template_is_created_but_not_overwritten(self) -> None:
        created = ensure_task_board()
        path = Path(created["tasks_path"])

        self.assertTrue(path.exists())
        self.assertTrue(created["created"])
        self.assertEqual(1, created["task_count"])

        path.write_text("# memSu Tasks\n\n## [active][P2] Custom task\n", encoding="utf-8")
        second = ensure_task_board()

        self.assertFalse(second["created"])
        self.assertIn("Custom task", path.read_text(encoding="utf-8"))

    def test_task_board_parses_and_updates_status_with_history(self) -> None:
        created = ensure_task_board(overwrite=True)
        board = read_task_board()
        task_id = board["tasks"][0]["task_id"]

        result = update_task_status(
            task_id,
            status="active",
            note="started implementation",
            now="2026-05-28T10:00:00+00:00",
        )

        self.assertTrue(result["ok"])
        updated = read_task_board()
        self.assertEqual("active", updated["tasks"][0]["status"])
        content = Path(created["tasks_path"]).read_text(encoding="utf-8")
        self.assertIn("## [active][P1] Stabilize observe-to-assistance loop", content)
        self.assertIn("history:", content)
        self.assertIn("status todo -> active", content)
        self.assertIn("started implementation", content)

    def test_task_claim_and_release_are_separate_from_status(self) -> None:
        created = ensure_task_board(overwrite=True)
        task_id = read_task_board()["tasks"][0]["task_id"]

        claimed = claim_task(
            task_id,
            agent="Codex",
            lease="2h",
            note="start work",
            now="2026-05-29T01:00:00+00:00",
        )

        self.assertTrue(claimed["ok"])
        task = read_task_board()["tasks"][0]
        self.assertEqual("todo", task["status"])
        self.assertEqual("Codex", task["claimed_by"])
        self.assertEqual("2026-05-29T03:00:00+00:00", task["claim_until"])

        conflict = claim_task(task_id, agent="Claude", now="2026-05-29T01:10:00+00:00")
        self.assertFalse(conflict["ok"])
        self.assertEqual("already_claimed", conflict["status"])

        released = release_task(
            task_id,
            agent="Codex",
            note="handoff",
            now="2026-05-29T01:30:00+00:00",
        )

        self.assertTrue(released["ok"])
        task = read_task_board()["tasks"][0]
        self.assertEqual("todo", task["status"])
        self.assertEqual("", task["claimed_by"])
        content = Path(created["tasks_path"]).read_text(encoding="utf-8")
        self.assertIn("claimed by Codex", content)
        self.assertIn("claim released", content)

    def test_cli_task_commands_smoke(self) -> None:
        self.assertEqual(0, main(["task", "init", "--force"]))
        board = read_task_board()
        task_id = board["tasks"][0]["task_id"]

        self.assertEqual(0, main(["task", "list"]))
        self.assertEqual(0, main(["task", "show", task_id]))
        self.assertEqual(0, main(["task", "claim", task_id, "--agent", "Codex", "--lease", "30m"]))
        self.assertEqual(0, main(["task", "release", task_id, "--agent", "Codex"]))
        self.assertEqual(0, main(["task", "update", task_id, "--status", "verifying"]))


if __name__ == "__main__":
    unittest.main()
