from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memsu.store import MemSuStore


class MemSuStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "memsu.db"
        self.store = MemSuStore(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_event_append_is_deduped_by_source_hash(self) -> None:
        first = self.store.append_event(
            source_agent="codex",
            source_type="command",
            actor="agent",
            event_type="command_run",
            content="ran tests",
        )
        second = self.store.append_event(
            source_agent="codex",
            source_type="command",
            actor="agent",
            event_type="command_run",
            content="ran tests",
        )

        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["event_id"], second["event_id"])

    def test_retain_recall_and_forget_memory(self) -> None:
        retained = self.store.retain_memory(
            "memSu should prefer scoped SQLite memory in the MVP",
            type="decision",
            scope="project:memsu",
            salience=0.9,
        )

        recalled = self.store.recall("SQLite memory", scope="project:memsu")
        self.assertEqual(1, len(recalled))
        self.assertEqual(retained["item_id"], recalled[0]["item_id"])

        forgotten = self.store.forget(retained["item_id"], reason="test")
        self.assertEqual("archived", forgotten["status"])
        self.assertEqual([], self.store.recall("SQLite memory", scope="project:memsu"))
        archived = self.store.audit(scope="project:memsu", status="archived")
        self.assertEqual(retained["item_id"], archived[0]["item_id"])
        self.assertIn("pending_action_count", self.store.health())

    def test_extract_accept_and_reject_candidates(self) -> None:
        event = self.store.append_event(
            source_agent="codex",
            source_type="conversation",
            actor="agent",
            event_type="conversation_turn",
            content="Decision: memSu should review extracted candidates before accepting them.",
            workspace="memSu",
            repo="susyimes/memSu",
        )

        extracted = self.store.extract_candidates(event_id=event["event_id"])
        self.assertEqual(1, extracted["created_count"])
        candidate_id = extracted["candidates"][0]["candidate_id"]

        pending = self.store.list_candidates(scope="project:memSu")
        self.assertEqual(candidate_id, pending[0]["candidate_id"])

        accepted = self.store.accept_candidate(candidate_id)
        self.assertEqual("accepted", accepted["status"])
        recalled = self.store.recall("review extracted candidates", scope="project:memSu")
        self.assertEqual(accepted["item_id"], recalled[0]["item_id"])

        second_event = self.store.append_event(
            source_agent="codex",
            source_type="conversation",
            actor="agent",
            event_type="conversation_turn",
            content="Preference: keep rejected candidates auditable.",
            workspace="memSu",
            repo="susyimes/memSu",
        )
        second = self.store.extract_candidates(event_id=second_event["event_id"])
        rejected_id = second["candidates"][0]["candidate_id"]
        rejected = self.store.reject_candidate(rejected_id, reason="not durable")
        self.assertEqual("rejected", rejected["status"])
        rejected_candidates = self.store.list_candidates(status="rejected", scope="project:memSu")
        self.assertEqual(rejected_id, rejected_candidates[0]["candidate_id"])

    def test_candidate_marks_possible_conflicts(self) -> None:
        existing = self.store.retain_memory(
            "memSu uses SQLite store for local memory",
            type="decision",
            scope="project:memSu",
        )
        event = self.store.append_event(
            source_agent="codex",
            source_type="conversation",
            actor="agent",
            event_type="conversation_turn",
            content="Decision: memSu uses Postgres store for local memory.",
            workspace="memSu",
            repo="susyimes/memSu",
        )

        extracted = self.store.extract_candidates(event_id=event["event_id"])
        candidate = extracted["candidates"][0]
        self.assertEqual(
            [existing["item_id"]],
            candidate["metadata"]["possible_conflict_item_ids"],
        )

    def test_extract_rejects_unknown_method(self) -> None:
        with self.assertRaises(ValueError):
            self.store.extract_candidates(method="unknown")

    def test_observation_run_evidence_and_findings_are_recorded(self) -> None:
        run = self.store.record_observation_run(
            mode="agent",
            since="24h",
            authorization_level="metadata",
            status="planned",
            prompt="plan prompt",
            metadata={"toolbelt": ["local_time_context"]},
        )
        evidence = self.store.record_evidence_ref(
            run_id=run["run_id"],
            source_type="inspire",
            source_ref="inspire.md",
            summary="loaded inspire notes",
        )
        finding = self.store.record_observation_finding(
            run_id=run["run_id"],
            kind="plan",
            claim="Agent-led observe plan is ready.",
            confidence=1.0,
            evidence_ids=[evidence["evidence_id"]],
        )

        self.assertEqual(run["run_id"], self.store.list_observation_runs()[0]["run_id"])
        self.assertEqual(evidence["evidence_id"], self.store.list_evidence_refs(run_id=run["run_id"])[0]["evidence_id"])
        self.assertEqual(finding["finding_id"], self.store.list_observation_findings(run_id=run["run_id"])[0]["finding_id"])
        self.assertIn(evidence["evidence_id"], finding["evidence_ids"])
        health = self.store.health()
        self.assertEqual(1, health["observation_run_count"])
        self.assertEqual(1, health["evidence_ref_count"])
        self.assertEqual(1, health["observation_finding_count"])


if __name__ == "__main__":
    unittest.main()
