from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AdvanceCapability:
    name: str
    kind: str
    version: str
    summary: str
    max_risk_level: str
    output_contract: str
    allowed_commands: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    auto_callable: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["allowed_commands"] = list(self.allowed_commands)
        payload["forbidden_actions"] = list(self.forbidden_actions)
        return payload


OBSERVE_TO_PROPOSALS = "observe-to-proposals"
GIT_ACTIVITY = "git-activity"


ADVANCE_CAPABILITIES: tuple[AdvanceCapability, ...] = (
    AdvanceCapability(
        name=OBSERVE_TO_PROPOSALS,
        kind="skill",
        version="0.1",
        summary="Run or read memSu observe and turn it into policy-gated suggestions only.",
        max_risk_level="L2",
        output_contract="observe-to-proposals",
        allowed_commands=(
            "observe run",
            "observe list",
            "observe findings",
            "candidate list",
            "curator conflicts",
            "policy evaluate",
            "adapter workflow",
        ),
        forbidden_actions=(
            "file_edit",
            "send_message",
            "candidate_accept",
            "candidate_reject",
            "config_change",
            "credential_read",
        ),
    ),
    AdvanceCapability(
        name=GIT_ACTIVITY,
        kind="adapter",
        version="0.1",
        summary="Record a read-only Git repository activity snapshot through the existing git adapter.",
        max_risk_level="L1",
        output_contract="git_event",
        allowed_commands=("adapter git",),
        forbidden_actions=(
            "git_commit",
            "git_push",
            "file_edit",
            "branch_change",
            "remote_change",
        ),
    ),
)


def normalize_capability_name(name: str) -> str:
    return (name or "").strip().lower().replace("_", "-")


def list_advance_capabilities(*, kind: str = "") -> list[dict[str, Any]]:
    normalized_kind = (kind or "").strip().lower()
    capabilities = [
        capability
        for capability in ADVANCE_CAPABILITIES
        if not normalized_kind or capability.kind == normalized_kind
    ]
    return [capability.to_dict() for capability in capabilities]


def get_advance_capability(*, name: str, kind: str = "") -> AdvanceCapability | None:
    normalized_name = normalize_capability_name(name)
    normalized_kind = (kind or "").strip().lower()
    for capability in ADVANCE_CAPABILITIES:
        if capability.name != normalized_name:
            continue
        if normalized_kind and capability.kind != normalized_kind:
            continue
        return capability
    return None


def supported_capability_names(*, kind: str = "") -> list[str]:
    return [item["name"] for item in list_advance_capabilities(kind=kind)]
