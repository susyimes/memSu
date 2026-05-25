from __future__ import annotations

import unittest

from memsu.extractor import extract_candidates_from_event


class ExtractorTests(unittest.TestCase):
    def test_marker_extraction_uses_repo_scope(self) -> None:
        event = {
            "event_id": "evt_test",
            "content": "Decision: memSu keeps candidate extraction review-first.",
            "repo": "susyimes/memSu",
            "sensitivity": "normal",
        }

        candidates = extract_candidates_from_event(event)

        self.assertEqual(1, len(candidates))
        self.assertEqual("decision", candidates[0].type)
        self.assertEqual("project:memSu", candidates[0].scope)

    def test_sensitive_events_do_not_extract(self) -> None:
        event = {
            "event_id": "evt_test",
            "content": "Decision: store this secret.",
            "repo": "susyimes/memSu",
            "sensitivity": "secret",
        }

        self.assertEqual([], extract_candidates_from_event(event))


if __name__ == "__main__":
    unittest.main()

