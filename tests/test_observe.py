from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from memsu.observe import is_sensitive_path, openclaw_runs_fact, resolve_hermes_root, run_observe
from memsu.store import MemSuStore


class ObserveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.previous_home = os.environ.get("MEMSU_HOME")
        os.environ["MEMSU_HOME"] = str(self.root / "memsu-home")
        self.store = MemSuStore(self.root / "memsu-home" / "memsu.db")

    def tearDown(self) -> None:
        if self.previous_home is None:
            os.environ.pop("MEMSU_HOME", None)
        else:
            os.environ["MEMSU_HOME"] = self.previous_home
        self.temp_dir.cleanup()

    def test_observe_run_writes_markdown_snapshot_and_store_row(self) -> None:
        evidence_home = self.root / "evidence"
        codex_sessions = evidence_home / ".codex" / "sessions"
        codex_sessions.mkdir(parents=True)
        (evidence_home / ".codex" / "session_index.jsonl").write_text(
            "{}\n",
            encoding="utf-8",
        )
        (codex_sessions / "session.jsonl").write_text(
            "\n".join(
                [
                    '{"type":"session_meta","payload":{"cwd":"C:/work/memSu"}}',
                    '{"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"让 observe 保存 agent 会话摘要"}]}}',
                    '{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"已把最近会话摘要写入 observe。"}]}}',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        secret_file = evidence_home / ".codex" / "sessions" / "token.secret"
        secret_file.write_text("token=do-not-read", encoding="utf-8")

        result = run_observe(
            self.store,
            evidence_home=evidence_home,
            now=datetime(2026, 5, 25, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
        )

        observe_path = Path(result["observe_path"])
        self.assertTrue(observe_path.exists())
        content = observe_path.read_text(encoding="utf-8")
        self.assertIn("## 快照 09:30", content)
        self.assertIn("### 当前图景", content)
        self.assertIn("### 最近 Agent 会话摘要", content)
        self.assertIn("让 observe 保存 agent 会话摘要", content)
        self.assertNotIn("do-not-read", content)

        snapshots = self.store.list_observation_snapshots(local_date="2026-05-25")
        self.assertEqual(1, len(snapshots))
        self.assertEqual(result["snapshot_id"], snapshots[0]["snapshot_id"])
        self.assertIn("Codex", snapshots[0]["agent_usage"])
        self.assertGreaterEqual(snapshots[0]["sources"]["sensitive_skipped_count"], 1)

        events = self.store.list_events(limit=5)
        self.assertEqual("observation_snapshot", events[0]["event_type"])

    def test_sensitive_path_filter_covers_common_credential_names(self) -> None:
        sensitive_names = [
            "credentials.json",
            "credential.json",
            "oauth_creds.json",
            "api_key.txt",
            "key.txt",
            ".env",
            ".env.local",
            "id_ed25519",
            "private-key.pem",
        ]

        for name in sensitive_names:
            with self.subTest(name=name):
                self.assertTrue(is_sensitive_path(Path(name)))

    def test_openclaw_runs_fact_reads_sqlite_without_sidecars(self) -> None:
        runs_db = self.root / "runs.sqlite"
        conn = sqlite3.connect(runs_db)
        try:
            conn.execute("CREATE TABLE runs (id TEXT PRIMARY KEY)")
            conn.commit()
        finally:
            conn.close()

        fact = openclaw_runs_fact(runs_db)

        self.assertIn("包含 1 张表", fact)
        self.assertFalse((self.root / "runs.sqlite-wal").exists())
        self.assertFalse((self.root / "runs.sqlite-shm").exists())

    def test_resolve_hermes_root_supports_windows_default(self) -> None:
        evidence_home = self.root / "evidence"
        windows_hermes = evidence_home / "AppData" / "Local" / "hermes"
        windows_hermes.mkdir(parents=True)
        previous_hermes_home = os.environ.pop("HERMES_HOME", None)
        try:
            self.assertEqual(windows_hermes, resolve_hermes_root(evidence_home))
        finally:
            if previous_hermes_home is not None:
                os.environ["HERMES_HOME"] = previous_hermes_home


if __name__ == "__main__":
    unittest.main()
