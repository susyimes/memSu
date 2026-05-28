from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from memsu.advance import (
    advance_capabilities,
    build_advance_agenda,
    plan_advance_run,
    run_advance_adapter,
    run_advance_skill,
)
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
        self.assertEqual(result["advancement"]["run"]["run_id"], self.store.list_advancement_runs()[0]["run_id"])
        self.assertTrue(self.store.list_worklines(run_id=result["advancement"]["run"]["run_id"]))
        self.assertTrue(self.store.list_advancement_opportunities(run_id=result["advancement"]["run"]["run_id"]))

    def test_advance_run_rejects_unknown_skill(self) -> None:
        result = run_advance_skill(self.store, skill="danger-skill")

        self.assertFalse(result["ok"])
        self.assertEqual("unsupported_skill", result["status"])
        self.assertEqual(["observe-to-proposals"], result["supported_skills"])

    def test_capability_registry_lists_skills_and_adapters(self) -> None:
        capabilities = advance_capabilities()
        names = [item["name"] for item in capabilities["capabilities"]]

        self.assertIn("observe-to-proposals", names)
        self.assertIn("git-activity", names)

        skill_only = advance_capabilities(kind="skill")
        self.assertEqual(["skill"], [item["kind"] for item in skill_only["capabilities"]])

    def test_auto_dry_run_plans_registered_capability_calls(self) -> None:
        plan = plan_advance_run(self.store)

        self.assertTrue(plan["ok"])
        self.assertEqual("planned", plan["status"])
        names = [item["name"] for item in plan["recommended_capability_calls"]]
        self.assertIn("observe-to-proposals", names)

    def test_repeated_workline_suggests_skill_candidate(self) -> None:
        title = "Codex: cwd=memSu repeated workflow"
        for _ in range(2):
            run = self.store.record_advancement_run(
                mode="skill",
                status="completed",
                capability_calls=[{"kind": "skill", "name": "observe-to-proposals"}],
            )
            self.store.record_workline(
                run_id=run["run_id"],
                title=title,
                scope="agent:codex",
                status="active",
                confidence=0.75,
            )
        self.store.record_observation_snapshot(
            local_date="2026-05-27",
            local_time="10:00",
            timezone_name="Asia/Shanghai",
            current_picture=["当前主线是 repeated workflow。"],
            known=[],
            inferred=[],
            unknown=[],
            agent_usage={"Codex": "活跃"},
            support_opportunity="无",
            sources={"session_summaries": {"Codex": ["cwd=memSu repeated workflow"]}},
            observe_path=str(self.root / "observe.md"),
        )

        agenda = build_advance_agenda(self.store)

        kinds = [item["kind"] for item in agenda["suggestions"]]
        self.assertIn("create_skill_candidate", kinds)

    def test_dry_run_worklines_do_not_count_as_active_repetition(self) -> None:
        self.store.record_observation_snapshot(
            local_date="2026-05-27",
            local_time="10:00",
            timezone_name="Asia/Shanghai",
            current_picture=["当前主线是 dry-run workflow。"],
            known=[],
            inferred=[],
            unknown=[],
            agent_usage={"Codex": "活跃"},
            support_opportunity="无",
            sources={"session_summaries": {"Codex": ["cwd=memSu repeated dry run"]}},
            observe_path=str(self.root / "observe.md"),
        )
        for _ in range(2):
            run_advance_skill(self.store, skill="observe-to-proposals", dry_run=True)

        agenda = build_advance_agenda(self.store)

        self.assertEqual([], self.store.list_worklines(status="active"))
        self.assertEqual(2, len(self.store.list_worklines(status="planned")))
        self.assertNotIn("create_skill_candidate", [item["kind"] for item in agenda["suggestions"]])

    def test_internal_plan_findings_do_not_become_skill_candidates(self) -> None:
        title = "Agent-led observe plan created; no local investigation executed."
        for _ in range(3):
            run = self.store.record_advancement_run(mode="auto", status="completed")
            self.store.record_workline(
                run_id=run["run_id"],
                title=title,
                scope="finding",
                status="active",
                metadata={"basis": "observation_finding:plan"},
            )
        self.store.record_observation_finding(
            run_id="run_test",
            kind="plan",
            claim=title,
            confidence=1.0,
            status="planned",
        )

        agenda = build_advance_agenda(self.store)

        repeated = [
            item for item in agenda["suggestions"]
            if item["kind"] == "create_skill_candidate"
        ]
        self.assertEqual([], repeated)

    def test_llm_ranking_falls_back_without_endpoint(self) -> None:
        previous_endpoint = os.environ.pop("MEMSU_LLM_ENDPOINT", None)
        try:
            agenda = build_advance_agenda(self.store, rank_method="llm")
        finally:
            if previous_endpoint is not None:
                os.environ["MEMSU_LLM_ENDPOINT"] = previous_endpoint

        self.assertEqual("rule", agenda["ranking"]["method"])
        self.assertTrue(agenda["ranking"]["fallback"])
        self.assertEqual("llm", agenda["ranking"]["requested_method"])
        self.assertEqual(1, agenda["suggestions"][0]["rank"])

    def test_since_filters_old_workflow_events(self) -> None:
        event = self.store.append_event(
            source_agent="workflow",
            source_type="test",
            actor="system",
            event_type="workflow_result",
            content="old workflow should not drive current agenda",
        )
        with self.store.session() as conn:
            conn.execute(
                "UPDATE events SET timestamp = ? WHERE event_id = ?",
                ("2020-01-01T00:00:00+00:00", event["event_id"]),
            )

        agenda = build_advance_agenda(self.store, since="1h")

        self.assertNotIn("old workflow", agenda["worklines"][0]["title"])
        self.assertEqual("run_observe", agenda["suggestions"][0]["kind"])

    def test_skill_run_limit_controls_agenda_size(self) -> None:
        self.store.record_observation_snapshot(
            local_date="2026-05-27",
            local_time="10:00",
            timezone_name="Asia/Shanghai",
            current_picture=["当前主线是 limit test。"],
            known=[],
            inferred=[],
            unknown=[],
            agent_usage={"Codex": "活跃", "Gemini": "活跃"},
            support_opportunity="无",
            sources={
                "session_summaries": {
                    "Codex": ["cwd=memSu limit one", "cwd=memSu limit two"],
                    "Gemini": ["cwd=memSu limit three"],
                }
            },
            observe_path=str(self.root / "observe.md"),
        )

        result = run_advance_skill(
            self.store,
            skill="observe-to-proposals",
            dry_run=True,
            limit=1,
        )

        self.assertEqual(1, len(result["agenda"]["worklines"]))

    def test_opportunities_are_not_all_attached_to_first_workline(self) -> None:
        snapshot = self.store.record_observation_snapshot(
            local_date="2026-05-27",
            local_time="10:00",
            timezone_name="Asia/Shanghai",
            current_picture=["当前主线是 opportunity linkage。"],
            known=[],
            inferred=[],
            unknown=[],
            agent_usage={"Codex": "活跃"},
            support_opportunity="无",
            sources={"session_summaries": {"Codex": ["cwd=memSu opportunity linkage"]}},
            observe_path=str(self.root / "observe.md"),
        )
        event = self.store.append_event(
            source_agent="codex",
            source_type="conversation",
            actor="agent",
            event_type="conversation_turn",
            content="Decision: candidate needs review.",
            repo="susyimes/memSu",
        )
        self.store.extract_candidates(event_id=event["event_id"])

        result = run_advance_skill(self.store, skill="observe-to-proposals", dry_run=True)
        opportunities = result["advancement"]["opportunities"]
        by_kind = {item["kind"]: item for item in opportunities}

        self.assertEqual("", by_kind["review_candidates"]["workline_id"])
        self.assertTrue(by_kind["continue_workline"]["workline_id"])
        self.assertEqual([snapshot["snapshot_id"]], by_kind["continue_workline"]["evidence_ids"])

    def test_git_activity_adapter_records_git_event(self) -> None:
        result = run_advance_adapter(
            self.store,
            adapter="git-activity",
            repo_path=Path.cwd(),
            workspace="memSu",
        )

        self.assertTrue(result["ok"])
        self.assertEqual("completed", result["status"])
        self.assertEqual("git-activity", result["adapter"])
        event = self.store.get_event(result["event"]["event_id"])
        self.assertIsNotNone(event)
        self.assertEqual("git_event", event["event_type"])
        runs = self.store.list_advancement_runs(mode="adapter")
        self.assertEqual(result["advancement"]["run"]["run_id"], runs[0]["run_id"])

    def test_cli_advance_agenda_smoke(self) -> None:
        exit_code = main(["--db", str(self.store.db_path), "advance", "agenda"])

        self.assertEqual(0, exit_code)

    def test_cli_advance_capabilities_smoke(self) -> None:
        exit_code = main(["--db", str(self.store.db_path), "advance", "capabilities"])

        self.assertEqual(0, exit_code)

    def test_cli_advance_run_dry_run_can_auto_plan(self) -> None:
        exit_code = main(["--db", str(self.store.db_path), "advance", "run", "--dry-run"])

        self.assertEqual(0, exit_code)
        self.assertEqual(1, len(self.store.list_advancement_runs(mode="auto")))
        self.assertEqual([], self.store.list_worklines(status="active"))
        self.assertEqual(1, len(self.store.list_worklines(status="planned")))

    def test_cli_advance_run_requires_one_capability_without_dry_run(self) -> None:
        exit_code = main(["--db", str(self.store.db_path), "advance", "run"])

        self.assertEqual(2, exit_code)

    def test_cli_advance_history_commands_smoke(self) -> None:
        run_advance_skill(self.store, skill="observe-to-proposals", dry_run=True)

        self.assertEqual(0, main(["--db", str(self.store.db_path), "advance", "runs"]))
        self.assertEqual(0, main(["--db", str(self.store.db_path), "advance", "worklines"]))
        self.assertEqual(0, main(["--db", str(self.store.db_path), "advance", "opportunities"]))


if __name__ == "__main__":
    unittest.main()
