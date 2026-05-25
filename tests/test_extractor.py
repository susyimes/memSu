from __future__ import annotations

import unittest
from unittest.mock import patch

from memsu.extractor import extract_candidates_from_event, extract_candidates_with_llm


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


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

    def test_llm_extraction_accepts_openai_compatible_json(self) -> None:
        event = {
            "event_id": "evt_test",
            "content": "Decision: memSu can use an optional LLM extractor.",
            "repo": "susyimes/memSu",
            "sensitivity": "normal",
        }
        raw = (
            b'{"choices":[{"message":{"content":"{\\"candidates\\":[{\\"content\\":'
            b'\\"memSu can use an optional LLM extractor.\\",\\"type\\":\\"decision\\",'
            b'\\"scope\\":\\"project:memSu\\",\\"confidence\\":0.82,\\"salience\\":0.71}]}"}}]}'
        )

        with patch("memsu.extractor.urllib.request.urlopen", return_value=FakeResponse(raw)):
            candidates = extract_candidates_with_llm(
                event,
                endpoint="http://127.0.0.1:9999/v1/chat/completions",
                model="test-model",
            )

        self.assertEqual(1, len(candidates))
        self.assertEqual("decision", candidates[0].type)
        self.assertEqual("project:memSu", candidates[0].scope)
        self.assertEqual("llm", candidates[0].metadata["extractor"])
        self.assertEqual("test-model", candidates[0].metadata["model"])

    def test_llm_extraction_skips_sensitive_events_without_calling_endpoint(self) -> None:
        event = {
            "event_id": "evt_secret",
            "content": "Decision: never send this credential to an LLM.",
            "repo": "susyimes/memSu",
            "sensitivity": "credential",
        }

        with patch("memsu.extractor.urllib.request.urlopen") as urlopen:
            candidates = extract_candidates_with_llm(
                event,
                endpoint="http://127.0.0.1:9999/v1/chat/completions",
            )

        self.assertEqual([], candidates)
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
