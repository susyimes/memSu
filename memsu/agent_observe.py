from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from .inspire import ensure_inspire_files, read_inspire
from .store import MemSuStore, stable_hash


TOOLBELT = [
    "local_time_context",
    "list_roots",
    "list_recent_paths",
    "find_git_repos",
    "summarize_git_repo",
    "list_windows_recent",
    "list_visible_processes",
    "list_process_commands",
    "query_installed_apps",
    "check_common_app_paths",
    "tail_shell_history_safely",
    "read_safe_text_excerpt",
    "record_evidence",
    "propose_memory_candidate",
    "update_inspire_proposal",
]


def build_agent_observe_prompt(
    *,
    inspire_content: str,
    since: str,
    authorization_level: str,
) -> str:
    return (
        "You are memSu's agent-led local observation planner.\n"
        "Goal: decide how to understand recent local work, agent/tool changes, "
        "repeated workflows, and durable memory candidates.\n\n"
        f"Observation window: {since}\n"
        f"Authorization level: {authorization_level}\n\n"
        "Hard rules:\n"
        "- Only use local read-only probes.\n"
        "- Do not read credential-like files.\n"
        "- Do not treat inference as fact.\n"
        "- Do not automatically accept long-term memory.\n"
        "- Attach evidence to important claims.\n\n"
        "Available tool families:\n"
        + "\n".join(f"- {name}" for name in TOOLBELT)
        + "\n\nUser-owned inspire notes:\n"
        + (inspire_content.strip() or "(none)")
        + "\n\nReturn a concise JSON investigation plan with keys: "
        "questions, first_tools, stop_conditions, risks, expected_outputs."
    )


def run_agent_observe(
    store: MemSuStore | None = None,
    *,
    since: str = "24h",
    authorization_level: str = "metadata",
    dry_run_plan: bool = False,
    include_prompt: bool = False,
    model: str = "",
) -> dict[str, Any]:
    store = store or MemSuStore()
    store.init()
    inspire_info = ensure_inspire_files()
    inspire = read_inspire()
    prompt = build_agent_observe_prompt(
        inspire_content=inspire["content"],
        since=since,
        authorization_level=authorization_level,
    )

    endpoint = os.environ.get("MEMSU_LLM_ENDPOINT", "")
    selected_model = model or os.environ.get("MEMSU_LLM_MODEL", "memsu-observe-agent")
    recorded_model = selected_model if endpoint and not dry_run_plan else ""
    status = "planned" if dry_run_plan else "needs_model" if not endpoint else "planned_by_model"
    run = store.record_observation_run(
        mode="agent",
        since=since,
        authorization_level=authorization_level,
        status=status,
        model=recorded_model,
        prompt=prompt,
        metadata={
            "inspire_path": inspire_info["inspire_path"],
            "inspire_dir": inspire_info["inspire_dir"],
            "toolbelt": TOOLBELT,
            "dry_run_plan": dry_run_plan,
        },
        finished_at="",
    )

    evidence = store.record_evidence_ref(
        run_id=run["run_id"],
        source_type="inspire",
        source_ref=inspire_info["inspire_path"],
        summary="Loaded user-owned inspire notes for agent-led observe planning.",
        source_hash=stable_hash(inspire["content"]),
        metadata={"user_editable": True},
    )

    if dry_run_plan:
        run = store.update_observation_run(
            run["run_id"],
            status="planned",
            metadata={
                "inspire_path": inspire_info["inspire_path"],
                "inspire_dir": inspire_info["inspire_dir"],
                "toolbelt": TOOLBELT,
                "dry_run_plan": True,
            },
        )
        finding = store.record_observation_finding(
            run_id=run["run_id"],
            kind="plan",
            claim="Agent-led observe plan created; no local investigation executed.",
            confidence=1.0,
            evidence_ids=[evidence["evidence_id"]],
            status="planned",
            metadata={"toolbelt": TOOLBELT},
        )
        result = {
            "ok": True,
            "status": "planned",
            "run": run,
            "inspire": inspire_info,
            "toolbelt": TOOLBELT,
            "finding": finding,
        }
        if include_prompt:
            result["prompt"] = prompt
        return result

    if not endpoint:
        run = store.update_observation_run(
            run["run_id"],
            status="needs_model",
            metadata={
                "inspire_path": inspire_info["inspire_path"],
                "inspire_dir": inspire_info["inspire_dir"],
                "toolbelt": TOOLBELT,
                "reason": "MEMSU_LLM_ENDPOINT is not configured.",
            },
        )
        finding = store.record_observation_finding(
            run_id=run["run_id"],
            kind="blocked",
            claim="Agent-led observe requires MEMSU_LLM_ENDPOINT or dry-run planning.",
            confidence=1.0,
            evidence_ids=[evidence["evidence_id"]],
            status="blocked",
            metadata={"missing": "MEMSU_LLM_ENDPOINT"},
        )
        result = {
            "ok": False,
            "status": "needs_model",
            "message": "Set MEMSU_LLM_ENDPOINT for model-led observation, or run with --dry-run-plan.",
            "run": run,
            "inspire": inspire_info,
            "toolbelt": TOOLBELT,
            "finding": finding,
        }
        if include_prompt:
            result["prompt"] = prompt
        return result

    try:
        plan = call_observe_model(endpoint=endpoint, model=selected_model, prompt=prompt)
    except Exception as exc:
        run = store.update_observation_run(
            run["run_id"],
            status="failed",
            metadata={
                "inspire_path": inspire_info["inspire_path"],
                "inspire_dir": inspire_info["inspire_dir"],
                "toolbelt": TOOLBELT,
                "error": str(exc),
            },
        )
        finding = store.record_observation_finding(
            run_id=run["run_id"],
            kind="error",
            claim="Model planning failed before local probes were executed.",
            confidence=1.0,
            evidence_ids=[evidence["evidence_id"]],
            status="failed",
            metadata={"error": str(exc)},
        )
        result = {
            "ok": False,
            "status": "failed",
            "message": str(exc),
            "run": run,
            "inspire": inspire_info,
            "toolbelt": TOOLBELT,
            "finding": finding,
        }
        if include_prompt:
            result["prompt"] = prompt
        return result

    result_ref = f"model-plan:{stable_hash(json.dumps(plan, ensure_ascii=False))[:16]}"
    run = store.update_observation_run(
        run["run_id"],
        status="planned_by_model",
        result_ref=result_ref,
        tool_call_count=0,
        metadata={
            "inspire_path": inspire_info["inspire_path"],
            "inspire_dir": inspire_info["inspire_dir"],
            "toolbelt": TOOLBELT,
            "model_plan": plan,
        },
    )
    finding = store.record_observation_finding(
        run_id=run["run_id"],
        kind="plan",
        claim="Model created an agent-led observation plan. Tool execution is a later V3 step.",
        confidence=0.9,
        evidence_ids=[evidence["evidence_id"]],
        status="planned",
        metadata={"model_plan": plan},
    )
    result = {
        "ok": True,
        "status": "planned_by_model",
        "run": run,
        "inspire": inspire_info,
        "toolbelt": TOOLBELT,
        "model_plan": plan,
        "finding": finding,
    }
    if include_prompt:
        result["prompt"] = prompt
    return result


def call_observe_model(*, endpoint: str, model: str, prompt: str) -> dict[str, Any]:
    api_key = os.environ.get("MEMSU_LLM_API_KEY", "")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You create safe local observation plans for memSu."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8")
    data = json.loads(raw)
    content = extract_message_content(data)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {"raw": content}
    return parsed


def extract_message_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
    if "content" in payload and isinstance(payload["content"], str):
        return payload["content"]
    return json.dumps(payload, ensure_ascii=False)
