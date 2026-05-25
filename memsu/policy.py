from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import default_policy_path


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


def load_policy_config(path: str | Path | None = None) -> dict[str, Any]:
    policy_path = Path(path) if path else default_policy_path()
    defaults = {
        "proactive_external_actions": False,
        "cross_agent_sensitive_sharing": False,
        "hard_delete_without_confirmation": False,
        "suggestion_cooldown_seconds": 300,
        "quiet_hours_active": False,
    }
    if not policy_path.exists():
        return defaults

    in_defaults = False
    for raw_line in policy_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "defaults:":
            in_defaults = True
            continue
        if line.endswith(":") and not raw_line.startswith((" ", "\t")):
            in_defaults = False
            continue
        if not in_defaults or ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        if key not in defaults:
            continue
        defaults[key] = parse_scalar(value)
    return defaults


def parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value
