from __future__ import annotations

import re
import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CandidateDraft:
    content: str
    type: str
    scope: str
    confidence: float
    salience: float
    metadata: dict[str, Any]


MARKER_RULES: tuple[tuple[re.Pattern[str], str, float, float], ...] = (
    (re.compile(r"^\s*(?:remember|memory|note)\s*:\s*(.+)$", re.I), "note", 0.85, 0.55),
    (re.compile(r"^\s*(?:decision|decided)\s*:\s*(.+)$", re.I), "decision", 0.85, 0.75),
    (re.compile(r"^\s*(?:project rule|rule)\s*:\s*(.+)$", re.I), "project_rule", 0.85, 0.8),
    (re.compile(r"^\s*(?:preference|prefer)\s*:\s*(.+)$", re.I), "preference", 0.85, 0.7),
    (re.compile(r"^\s*(?:lesson|workflow lesson)\s*:\s*(.+)$", re.I), "workflow_lesson", 0.8, 0.65),
    (re.compile(r"^\s*(?:failure pattern|failure)\s*:\s*(.+)$", re.I), "failure_pattern", 0.8, 0.65),
    (re.compile(r"^\s*(?:skill candidate|skill)\s*:\s*(.+)$", re.I), "skill_candidate", 0.8, 0.65),
)

SENTENCE_RULES: tuple[tuple[re.Pattern[str], str, float, float], ...] = (
    (re.compile(r"\bwe decided to\b\s+(.+)", re.I), "decision", 0.7, 0.65),
    (re.compile(r"\bthe decision is\b\s+(.+)", re.I), "decision", 0.7, 0.65),
    (re.compile(r"\bi prefer\b\s+(.+)", re.I), "preference", 0.7, 0.6),
    (re.compile(r"\buser prefers\b\s+(.+)", re.I), "preference", 0.75, 0.65),
    (re.compile(r"\bfailed because\b\s+(.+)", re.I), "failure_pattern", 0.65, 0.55),
)


def extract_candidates_from_event(event: dict[str, Any]) -> list[CandidateDraft]:
    content = (event.get("content") or "").strip()
    if not content:
        return []

    sensitivity = (event.get("sensitivity") or "normal").lower()
    if sensitivity in {"secret", "credential", "private"}:
        return []

    scope = infer_scope(event)
    drafts: list[CandidateDraft] = []

    for raw_line in content.splitlines():
        line = clean_line(raw_line)
        if not line:
            continue
        for pattern, memory_type, confidence, salience in MARKER_RULES:
            match = pattern.search(line)
            if match:
                drafts.append(
                    CandidateDraft(
                        content=normalize_memory_text(match.group(1)),
                        type=memory_type,
                        scope=scope,
                        confidence=confidence,
                        salience=salience,
                        metadata={"extractor": "marker", "pattern": pattern.pattern},
                    )
                )
                break

    if drafts:
        return dedupe_drafts(drafts)

    if event.get("event_type") == "memory_write":
        return [
            CandidateDraft(
                content=normalize_memory_text(content),
                type="note",
                scope=scope,
                confidence=0.8,
                salience=0.6,
                metadata={"extractor": "memory_write"},
            )
        ]

    for sentence in split_sentences(content):
        line = clean_line(sentence)
        for pattern, memory_type, confidence, salience in SENTENCE_RULES:
            match = pattern.search(line)
            if match:
                drafts.append(
                    CandidateDraft(
                        content=normalize_memory_text(match.group(0)),
                        type=memory_type,
                        scope=scope,
                        confidence=confidence,
                        salience=salience,
                        metadata={"extractor": "sentence", "pattern": pattern.pattern},
                    )
                )
                break

    return dedupe_drafts(drafts)


def extract_candidates_with_llm(
    event: dict[str, Any],
    *,
    endpoint: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> list[CandidateDraft]:
    sensitivity = (event.get("sensitivity") or "normal").lower()
    if sensitivity in {"secret", "credential", "private"}:
        return []

    endpoint = endpoint or os.environ.get("MEMSU_LLM_ENDPOINT", "")
    api_key = api_key or os.environ.get("MEMSU_LLM_API_KEY", "")
    model = model or os.environ.get("MEMSU_LLM_MODEL", "memsu-extractor")
    if not endpoint:
        raise ValueError("MEMSU_LLM_ENDPOINT is required for LLM extraction")

    event_payload = {
        "event_id": event.get("event_id", ""),
        "source_agent": event.get("source_agent", ""),
        "source_type": event.get("source_type", ""),
        "event_type": event.get("event_type", ""),
        "workspace": event.get("workspace", ""),
        "repo": event.get("repo", ""),
        "sensitivity": event.get("sensitivity", "normal"),
        "content": event.get("content", ""),
    }
    prompt = (
        "Extract durable memory candidates from this event. "
        "Return JSON only with key candidates, an array of objects with "
        "content, type, scope, confidence, salience. Skip secrets and temporary facts.\n"
        + json.dumps(event_payload, ensure_ascii=False)
    )
    request_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are memSu's conservative memory extraction engine."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8")

    payload = json.loads(raw)
    content = extract_llm_content(payload)
    extracted = json.loads(content)
    candidate_payloads = extracted.get("candidates", []) if isinstance(extracted, dict) else []
    drafts: list[CandidateDraft] = []
    for item in candidate_payloads:
        if not isinstance(item, dict):
            continue
        memory_type = item.get("type", "note")
        if memory_type not in {
            "preference",
            "project_rule",
            "fact",
            "decision",
            "workflow_lesson",
            "failure_pattern",
            "skill_candidate",
            "note",
        }:
            memory_type = "note"
        content_text = normalize_memory_text(str(item.get("content", "")))
        if not content_text:
            continue
        drafts.append(
            CandidateDraft(
                content=content_text,
                type=memory_type,
                scope=str(item.get("scope") or infer_scope(event)),
                confidence=float(item.get("confidence", 0.7)),
                salience=float(item.get("salience", 0.5)),
                metadata={"extractor": "llm", "model": model},
            )
        )
    return dedupe_drafts(drafts)


def extract_llm_content(payload: dict[str, Any]) -> str:
    if "candidates" in payload:
        return json.dumps(payload, ensure_ascii=False)
    choices = payload.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
    raise ValueError("LLM response did not contain JSON candidate content")


def infer_scope(event: dict[str, Any]) -> str:
    metadata = event.get("metadata") or {}
    if isinstance(metadata, dict):
        metadata_scope = (metadata.get("scope") or "").strip()
        if metadata_scope:
            return metadata_scope

    repo = (event.get("repo") or "").strip()
    if repo:
        return f"project:{repo.split('/')[-1]}"

    workspace = (event.get("workspace") or "").strip()
    if workspace:
        return f"workspace:{workspace}"

    source_agent = (event.get("source_agent") or "").strip()
    if source_agent:
        return f"agent:{source_agent}"

    return "global_user"


def clean_line(line: str) -> str:
    line = line.strip()
    if line.lower().startswith(("user:", "assistant:", "system:")):
        return line.split(":", 1)[1].strip()
    return line


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def normalize_memory_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    return text[:1000]


def dedupe_drafts(drafts: list[CandidateDraft]) -> list[CandidateDraft]:
    seen: set[tuple[str, str, str]] = set()
    result: list[CandidateDraft] = []
    for draft in drafts:
        key = (draft.type, draft.scope, draft.content.lower())
        if key in seen or not draft.content:
            continue
        seen.add(key)
        result.append(draft)
    return result
