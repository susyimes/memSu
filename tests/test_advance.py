from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from memsu.advance import build_advance_agenda, run_advance_skill
from memsu.cli import main
from memsu.store import MemSuStore


class AdvanceTests(unittest.TestCase):
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

    def test_agenda_uses_existing_snapshot_and_pending_candidates(self) -> None:
        snapshot = self.store.record_observation_snapshot(
            local_date="2026-05-27",
            local_time="10:00",
            timezone_name="Asia/Shanghai",
            current_picture=["当前主线是 memSu auto 模式。"],
            known=["observe-to-proposals skill 已设计。"],
            inferred=["auto kernel 可以通过 skill 控制推进。"],
            unknown=["尚未实现 advance CLI。"],
            agent_usage={"Codex": "最近 24 小时活跃。"},
            support_opportunity="建议实现 advance agenda。",
            sources={
                "session_summaries": {
                    "Codex": [
                        "cwd=memSu；用户：实现 skill/adapter 控制的 auto 模式；结果：设计已加入。"
                    ]
                }
            },
            observe_path=str(self.root / "observe.md"),
        )
        event = self.store.append_event(
            source_agent="codex",
            source_type="conversation",
            actor="agent",
            event_type="conversation_turn",
            content="Decision: memSu auto should call stable skills and adapters.",
            repo="susyimes/memSu",
        )
        extracted = self.store.extract_candidates(event_id=event["event_id"])

        agenda = build_advance_agenda(self.store)

        self.assertTrue(agenda["ok"])
        self.assertEqual(snapshot["snapshot_id"], agenda["latest_snapshot_id"])
        self.assertEqual(1, agenda["pending_candidate_count"])
        self.assertIn("Codex", agenda["worklines"][0]["title"])
        self.assertEqual(
            extracted["candidates"][0]["candidate_id"],
            agenda["suggestions"][0]["evidence"][0],
        )
        self.assertIn("memSu 推进议程", agenda["brief"])

    def test_observe_to_proposals_records_policy_and_workflow_event(self) -> None:
        evidence_home = self.root / "evidence"
        codex_sessions = evidence_home / ".codex" / "sessions"
        codex_sessions.mkdir(parents=True)
        (codex_sessions / "session.jsonl").write_text(
            "\n".join(
                [
                    '{"payload":{"cwd":"C:/work/memSu"}}',
                    '{"payload":{"role":"user","content":[{"text":"把 auto 做成 skill adapter 控制"}]}}',
                    '{"payload":{"role":"assistant","content":[{"text":"已实现 advance skill MVP。"}]}}',
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        result = run_advance_skill(
            self.store,
            skill="observe-to-proposals",
            evidence_home=evidence_home,
        )

        self.assertTrue(result["ok"])
        self.assertEqual("completed", result["status"])
        self.assertEqual("observe-to-proposals", result["skill"])
        self.assertTrue(result["policy_results"])
        self.assertEqual("workflow_result", self.store.list_events(limit=1)[0]["event_type"])
        self.assertIn("memSu 观察后提议", result["brief"])

    def test_advance_run_rejects_unknown_skill(self) -> None:
        result = run_advance_skill(self.store, skill="danger-skill")

        self.assertFalse(result["ok"])
        self.assertEqual("unsupported_skill", result["status"])

    def test_cli_advance_agenda_smoke(self) -> None:
        exit_code = main(["--db", str(self.store.db_path), "advance", "agenda"])

        self.assertEqual(0, exit_code)


if __name__ == "__main__":
    unittest.main()
