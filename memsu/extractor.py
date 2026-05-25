from __future__ import annotations

import re
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
