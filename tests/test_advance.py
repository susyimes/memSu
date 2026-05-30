from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from memsu.advance import detect_worklines, generate_opportunities, run_advance_agenda
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

    def seed_snapshot(self) -> dict:
        return self.store.record_observation_snapshot(
            local_date="2026-05-30",
            local_time="17:30",
            timezone_name="Asia/Shanghai",
            current_picture=[
                "memSu store has recent observations.",
                "Codex is the most active source.",
            ],
            known=["Codex has recent session summaries."],
            inferred=["Codex appears active."],
            unknown=["Gemini has sensitive paths skipped."],
            agent_usage={"Codex": "recent 24h 12 metadata files"},
            support_opportunity="Repeated workflow may deserve a memSu adapter or Hermes skill.",
            sources={
                "session_summaries": {
                    "Codex": [
                        "2026-05-30 17:00；cwd=memSu；用户：advance agenda；结果：planned",
                        "2026-05-30 17:05；cwd=memSu；用户：workline detector；结果：planned",
                        "2026-05-30 17:10；cwd=Tooling；用户：agent toolbelt；结果：planned",
                    ]
                }
            },
            observe_path=str(self.root / "observe.md"),
        )

    def test_agenda_records_brief_event_worklines_and_policy(self) -> None:
        snapshot = self.seed_snapshot()
        candidate = self.store.propose_candidate(
            "memSu advance agenda should stay review-first.",
            type="workflow_lesson",
            scope="project:memSu",
            source_event_ids=[snapshot["event"]["event_id"]],
        )
        self.store.append_event(
            source_agent="git",
            source_type="repository",
            actor="system",
            event_type="git_event",
            content="repo: susyimes/memSu\nstatus:\n M memsu/advance.py",
            workspace="memSu",
            repo="susyimes/memSu",
            metadata={
                "branch": "codex/agent-observe-advisor",
                "head": "abc1234",
                "status_short": " M memsu/advance.py",
            },
        )

        result = run_advance_agenda(self.store)

        self.assertTrue(result["ok"])
        self.assertTrue(Path(result["brief_path"]).exists())
        self.assertLessEqual(len(result["worklines"]), 5)
        self.assertEqual("review_candidates", result["opportunities"][0]["kind"])
        self.assertEqual(candidate["candidate_id"], result["worklines"][0]["evidence"][0]["ref"])
        self.assertTrue(all("policy" in item for item in result["opportunities"]))
        self.assertIn("L0", result["policy_summary"]["by_risk"])
        self.assertIn("L2", result["policy_summary"]["by_risk"])

        events = self.store.list_events(limit=5)
        self.assertEqual("advance", events[0]["source_agent"])
        self.assertEqual("workflow_result", events[0]["event_type"])
        self.assertEqual(str(Path(result["brief_path"])), events[0]["content_ref"])

    def test_workline_detector_groups_codex_cwd_and_git_events(self) -> None:
        snapshot = self.seed_snapshot()
        git_event = self.store.append_event(
            source_agent="git",
            source_type="repository",
            actor="system",
            event_type="git_event",
            content="repo: memSu\nstatus:\nclean",
            workspace="memSu",
            repo="susyimes/memSu",
            metadata={"branch": "main", "head": "abc1234", "status_short": ""},
        )
        context = {
            "snapshots": [snapshot],
            "findings": [],
            "candidates": [],
            "conflicts": [],
            "summaries": [],
            "events": self.store.list_events(limit=5),
        }

        worklines = detect_worklines(context, limit=5)

        titles = [item["title"] for item in worklines]
        self.assertIn("Continue memSu work from Codex sessions", titles)
        self.assertTrue(any(item["scope"] == "repo:susyimes/memSu" for item in worklines))
        self.assertTrue(
            any(git_event["event_id"] == evidence["ref"] for item in worklines for evidence in item["evidence"])
        )

    def test_opportunity_generator_policy_classifies_without_execution(self) -> None:
        snapshot = self.seed_snapshot()
        context = {
            "snapshots": [snapshot],
            "findings": [],
            "candidates": [],
            "conflicts": [],
            "summaries": [],
            "events": [],
        }
        worklines = detect_worklines(context, limit=5)

        opportunities = generate_opportunities(self.store, context, worklines)

        kinds = {item["kind"] for item in opportunities}
        self.assertIn("run_maintenance", kinds)
        self.assertIn("continue_workline", kinds)
        self.assertIn("create_skill_candidate", kinds)
        self.assertTrue(all(item["policy"]["proposal_id"] for item in opportunities))
        self.assertFalse(any(item["policy"]["requires_confirmation"] for item in opportunities))


if __name__ == "__main__":
    unittest.main()
