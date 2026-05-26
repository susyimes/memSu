from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from memsu.agent_observe import run_agent_observe
from memsu.store import MemSuStore


class AgentObserveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.previous_home = os.environ.get("MEMSU_HOME")
        self.previous_endpoint = os.environ.pop("MEMSU_LLM_ENDPOINT", None)
        os.environ["MEMSU_HOME"] = str(self.root / "memsu-home")
        self.store = MemSuStore(self.root / "memsu-home" / "memsu.db")

    def tearDown(self) -> None:
        if self.previous_home is None:
            os.environ.pop("MEMSU_HOME", None)
        else:
            os.environ["MEMSU_HOME"] = self.previous_home
        if self.previous_endpoint is not None:
            os.environ["MEMSU_LLM_ENDPOINT"] = self.previous_endpoint
        self.temp_dir.cleanup()

    def test_dry_run_plan_records_run_and_preserves_inspire(self) -> None:
        result = run_agent_observe(self.store, dry_run_plan=True, include_prompt=True)

        self.assertTrue(result["ok"])
        self.assertEqual("planned", result["status"])
        self.assertTrue(Path(result["inspire"]["inspire_path"]).exists())
        self.assertIn("local_time_context", result["toolbelt"])
        self.assertIn("User-owned inspire notes", result["prompt"])

        runs = self.store.list_observation_runs()
        evidence = self.store.list_evidence_refs(run_id=result["run"]["run_id"])
        findings = self.store.list_observation_findings(run_id=result["run"]["run_id"])

        self.assertEqual(1, len(runs))
        self.assertEqual(1, len(evidence))
        self.assertEqual(1, len(findings))
        self.assertEqual("planned", findings[0]["status"])
        self.assertTrue(runs[0]["finished_at"])

    def test_agent_observe_requires_model_without_dry_run(self) -> None:
        result = run_agent_observe(self.store)

        self.assertFalse(result["ok"])
        self.assertEqual("needs_model", result["status"])
        self.assertEqual("blocked", result["finding"]["status"])
        self.assertNotIn("prompt", result)

    def test_prompt_is_hidden_by_default(self) -> None:
        result = run_agent_observe(self.store, dry_run_plan=True)

        self.assertTrue(result["ok"])
        self.assertNotIn("prompt", result)

    def test_dry_run_does_not_record_model_when_endpoint_exists(self) -> None:
        os.environ["MEMSU_LLM_ENDPOINT"] = "http://127.0.0.1:9/v1/chat/completions"

        result = run_agent_observe(self.store, dry_run_plan=True)

        self.assertTrue(result["ok"])
        self.assertEqual("", result["run"]["model"])


if __name__ == "__main__":
    unittest.main()
