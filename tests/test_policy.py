from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memsu.store import MemSuStore


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = MemSuStore(Path(self.temp_dir.name) / "memsu.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_suggestion_is_recorded_without_confirmation(self) -> None:
        proposal = self.store.evaluate_policy(
            action_type="suggestion",
            description="Suggest reviewing a repeated workflow.",
        )

        self.assertEqual("L2", proposal["risk_level"])
        self.assertEqual("suggest", proposal["decision"])
        self.assertEqual("recorded", proposal["status"])
        self.assertFalse(proposal["requires_confirmation"])

    def test_external_action_requires_confirmation_and_can_be_approved(self) -> None:
        proposal = self.store.evaluate_policy(
            action_type="send_message",
            description="Send a proactive summary to a chat.",
        )

        self.assertEqual("L3", proposal["risk_level"])
        self.assertEqual("pending_confirmation", proposal["status"])
        self.assertTrue(proposal["requires_confirmation"])

        decided = self.store.decide_action_proposal(
            proposal["proposal_id"],
            decision="approve",
            reason="user confirmed",
        )
        self.assertEqual("approved", decided["status"])

    def test_forbidden_action_is_denied(self) -> None:
        proposal = self.store.evaluate_policy(
            action_type="credential_capture",
            description="Capture credentials from terminal output.",
        )

        self.assertEqual("L4", proposal["risk_level"])
        self.assertEqual("deny", proposal["decision"])
        self.assertEqual("denied", proposal["status"])

    def test_sensitive_suggestion_is_denied_by_default(self) -> None:
        proposal = self.store.evaluate_policy(
            action_type="suggestion",
            description="Suggest sharing private context.",
            sensitivity="private",
        )

        self.assertEqual("L4", proposal["risk_level"])
        self.assertEqual("denied", proposal["status"])

    def test_policy_events_are_logged(self) -> None:
        proposal = self.store.evaluate_policy(
            action_type="file_edit",
            description="Edit a file after detecting a stale convention.",
        )
        self.store.decide_action_proposal(
            proposal["proposal_id"],
            decision="reject",
            reason="not now",
        )

        events = self.store.list_policy_events(limit=10)
        self.assertEqual(["rejected", "evaluated"], [event["event_type"] for event in events])

    def test_suggestion_rate_limit_defers_repeated_suggestions(self) -> None:
        first = self.store.evaluate_policy(
            action_type="suggestion",
            description="Suggest creating a workflow skill.",
        )
        second = self.store.evaluate_policy(
            action_type="suggestion",
            description="Suggest another workflow skill.",
        )

        self.assertEqual("recorded", first["status"])
        self.assertEqual("deferred", second["status"])
        self.assertEqual("defer", second["decision"])

    def test_quiet_hours_defer_suggestions(self) -> None:
        proposal = self.store.evaluate_policy(
            action_type="suggestion",
            description="Suggest a proactive reminder.",
            metadata={"quiet_hours_active": True},
        )

        self.assertEqual("L2", proposal["risk_level"])
        self.assertEqual("deferred", proposal["status"])


if __name__ == "__main__":
    unittest.main()
