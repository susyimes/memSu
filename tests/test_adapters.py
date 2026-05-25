from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from memsu.adapters import (
    ingest_codex_transcript,
    parse_codex_transcript,
    record_shell_command,
    record_workflow_result,
    snapshot_git_repo,
)
from memsu.store import MemSuStore


class AdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store = MemSuStore(self.root / "memsu.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_shell_and_workflow_adapters_append_events(self) -> None:
        shell = record_shell_command(
            self.store,
            command="python -m unittest",
            exit_code=0,
            stdout="OK",
            workspace="memSu",
            repo="susyimes/memSu",
        )
        workflow = record_workflow_result(
            self.store,
            name="tests",
            status="passed",
            summary="unit tests passed",
            workspace="memSu",
            repo="susyimes/memSu",
        )

        events = self.store.list_events(limit=10)
        self.assertEqual(2, len(events))
        self.assertIn(shell["event_id"], {event["event_id"] for event in events})
        self.assertIn(workflow["event_id"], {event["event_id"] for event in events})

    def test_codex_transcript_adapter_supports_markdown(self) -> None:
        transcript = self.root / "codex.md"
        transcript.write_text(
            "# User\nDecision: keep adapter ingestion explicit.\n"
            "# Assistant\nRecorded as a pending candidate.\n",
            encoding="utf-8",
        )

        parsed = parse_codex_transcript(transcript.read_text(encoding="utf-8"))
        self.assertEqual(["user", "assistant"], [event["role"] for event in parsed])

        result = ingest_codex_transcript(
            self.store,
            path=str(transcript),
            workspace="memSu",
            repo="susyimes/memSu",
            thread_id="thread-1",
        )
        self.assertEqual(2, result["count"])

        extracted = self.store.extract_candidates(limit=10)
        self.assertEqual(1, extracted["created_count"])
        self.assertEqual("project:memSu", extracted["candidates"][0]["scope"])

    def test_git_adapter_snapshots_repo(self) -> None:
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "memSu Test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        (repo / "README.md").write_text("# test\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo, check=True, capture_output=True)

        result = snapshot_git_repo(self.store, repo_path=str(repo), workspace="test")
        event = self.store.get_event(result["event_id"])

        self.assertIsNotNone(event)
        self.assertEqual("git_event", event["event_type"])
        self.assertIn("branch: main", event["content"])


if __name__ == "__main__":
    unittest.main()

