from __future__ import annotations

from dataclasses import dataclass
from typing import Any


L0_ACTIONS = {
    "maintenance",
    "dedupe",
    "summarize",
    "stale_mark",
    "candidate_extract",
}

L1_ACTIONS = {
    "recall",
    "context_injection",
}

L2_ACTIONS = {
    "suggestion",
    "reminder",
    "skill_recommendation",
    "workflow_recommendation",
}

L3_ACTIONS = {
    "file_edit",
    "send_message",
    "task_create",
    "config_change",
    "external_action",
    "cross_agent_share",
    "memory_hard_delete",
}

L4_ACTIONS = {
    "credential_capture",
    "payment",
    "permission_change",
    "hidden_surveillance",
    "keylogging",
    "network_interception",
}

SENSITIVE_LEVELS = {"secret", "credential", "private"}


@dataclass(frozen=True)
class PolicyDecision:
    action_type: str
    risk_level: str
    decision: str
    status: str
    reason: str
    requires_confirmation: bool


def evaluate_action(
    action_type: str,
    *,
    description: str = "",
    sensitivity: str = "normal",
    metadata: dict[str, Any] | None = None,
) -> PolicyDecision:
    normalized = normalize_action(action_type)
    sensitivity = (sensitivity or "normal").lower()
    metadata = metadata or {}

    if normalized in L4_ACTIONS:
        return PolicyDecision(
            action_type=normalized,
            risk_level="L4",
            decision="deny",
            status="denied",
            reason="Action is forbidden or highly restricted by memSu policy.",
            requires_confirmation=False,
        )

    if sensitivity in SENSITIVE_LEVELS and normalized not in L0_ACTIONS | L1_ACTIONS:
        return PolicyDecision(
            action_type=normalized,
            risk_level="L4",
            decision="deny",
            status="denied",
            reason="Sensitive context cannot be used for proactive actions by default.",
            requires_confirmation=False,
        )

    if normalized in L3_ACTIONS:
        return PolicyDecision(
            action_type=normalized,
            risk_level="L3",
            decision="require_confirmation",
            status="pending_confirmation",
            reason="External, destructive, or cross-boundary action requires explicit user confirmation.",
            requires_confirmation=True,
        )

    if normalized in L2_ACTIONS:
        return PolicyDecision(
            action_type=normalized,
            risk_level="L2",
            decision="suggest",
            status="recorded",
            reason="Suggestion-level proactive behavior is allowed with rate limits.",
            requires_confirmation=False,
        )

    if normalized in L1_ACTIONS:
        return PolicyDecision(
            action_type=normalized,
            risk_level="L1",
            decision="allow",
            status="recorded",
            reason="Passive recall/context injection is allowed.",
            requires_confirmation=False,
        )

    if normalized in L0_ACTIONS:
        return PolicyDecision(
            action_type=normalized,
            risk_level="L0",
            decision="allow",
            status="recorded",
            reason="Internal maintenance is allowed.",
            requires_confirmation=False,
        )

    if metadata.get("external") is True:
        return PolicyDecision(
            action_type=normalized,
            risk_level="L3",
            decision="require_confirmation",
            status="pending_confirmation",
            reason="Unknown external action requires explicit confirmation.",
            requires_confirmation=True,
        )

    return PolicyDecision(
        action_type=normalized,
        risk_level="L2",
        decision="suggest",
        status="recorded",
        reason="Unknown low-risk action is downgraded to suggestion.",
        requires_confirmation=False,
    )


def normalize_action(action_type: str) -> str:
    return (action_type or "suggestion").strip().lower().replace("-", "_").replace(" ", "_")

