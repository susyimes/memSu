from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from memsu.cli import main
from memsu.inbox import (
    capture_inbox_note,
    ensure_inbox,
    promote_inbox_file,
    read_inbox,
)
from memsu.paths import (
    default_agent_guide_path,
    default_inbox_archive_dir,
    default_inbox_dir,
    default_tasks_path,
)
from memsu.tasks import read_task_board


class InboxTests(unittest.TestCase):
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

    def test_inbox_init_lists_unprocessed_files(self) -> None:
        status = ensure_inbox()
        inbox_dir = Path(status["inbox_dir"])
        (inbox_dir / "raw-future.md").write_text(
            "以后需要让 agent 自动整理未来任务。\n",
            encoding="utf-8",
        )

        inbox = read_inbox()

        self.assertEqual(1, inbox["file_count"])
        self.assertEqual("raw-future.md", inbox["files"][0]["relative_path"])

    def test_capture_and_promote_archives_source_and_appends_task(self) -> None:
        capture = capture_inbox_note(
            title="乱写 future task",
            content="以后需要做 inbox -> tasks.md 的整理链路。",
            now="2026-05-28T10:00:00+00:00",
        )
        relative = capture["relative_path"]

        result = promote_inbox_file(
            relative,
            title="Implement inbox-to-task promotion",
            status="todo",
            priority="P2",
            scope="project:memSu",
            context="人类乱写资料进入 inbox，agent 整理后写入任务板。",
            acceptance=[
                "source file is archived",
                "tasks.md contains promoted task",
            ],
            note="promoted by test",
            now="2026-05-28T10:01:00+00:00",
        )

        self.assertTrue(result["ok"])
        self.assertFalse(Path(result["source_path"]).exists())
        self.assertTrue(Path(result["archive_path"]).exists())
        self.assertIn("archive/2026-05-28", result["archive_relative_path"])
        board = read_task_board()
        promoted = board["tasks"][-1]
        self.assertEqual("Implement inbox-to-task promotion", promoted["title"])
        self.assertEqual("project:memSu", promoted["scope"])
        self.assertEqual(result["archive_relative_path"], promoted["source"])

    def test_cli_inbox_commands_smoke(self) -> None:
        self.assertEqual(0, main(["inbox", "init"]))
        self.assertEqual(0, main(["inbox", "add", "--title", "Future thing", "--content", "later task"]))
        inbox = read_inbox()
        self.assertEqual(1, inbox["file_count"])
        rel = inbox["files"][0]["relative_path"]

        self.assertEqual(0, main(["inbox", "list"]))
        self.assertEqual(
            0,
            main(
                [
                    "inbox",
                    "promote",
                    rel,
                    "--title",
                    "Future thing",
                    "--scope",
                    "project:memSu",
                    "--acceptance",
                    "task is visible",
                ]
            ),
        )
        self.assertEqual(0, len(read_inbox()["files"]))

    def test_init_creates_inbox_archive_and_task_board(self) -> None:
        self.assertEqual(0, main(["init"]))

        self.assertTrue(default_inbox_dir().exists())
        self.assertTrue(default_inbox_archive_dir().exists())
        self.assertTrue(default_tasks_path().exists())
        self.assertTrue(default_agent_guide_path().exists())


if __name__ == "__main__":
    unittest.main()
