from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .adapters import snapshot_git_repo
from .capabilities import (
    GIT_ACTIVITY,
    OBSERVE_TO_PROPOSALS,
    get_advance_capability,
    list_advance_capabilities,
    normalize_capability_name,
    supported_capability_names,
)
from .observe import run_observe
from .store import MemSuStore, json_dumps, utc_now


def advance_capabilities(*, kind: str = "") -> dict[str, Any]:
    capabilities = list_advance_capabilities(kind=kind)
    return {
        "ok": True,
        "capabilities": capabilities,
        "count": len(capabilities),
    }


def plan_advance_run(
    store: MemSuStore | None = None,
    *,
    since: str = "24h",
    limit: int = 10,
    rank_method: str = "rule",
    model: str = "",
    persist: bool = False,
) -> dict[str, Any]:
    store = store or MemSuStore()
    agenda = build_advance_agenda(
        store,
        since=since,
        limit=limit,
        rank_method=rank_method,
        model=model,
    )
    recommended_calls = [
        {
            "kind": "skill",
            "name": OBSERVE_TO_PROPOSALS,
            "reason": "Turn the current agenda into policy-gated suggestions without taking L3 action.",
            "risk_level": "L2",
        }
    ]
    if agenda["source_counts"]["events"] == 0 or not agenda.get("latest_snapshot_id"):
        recommended_calls.append(
            {
                "kind": "adapter",
                "name": GIT_ACTIVITY,
                "reason": "Record a read-only Git activity baseline for the current repository.",
                "risk_level": "L1",
            }
        )

    result = {
        "ok": True,
        "status": "planned",
        "mode": "auto",
        "since": since,
        "agenda": agenda,
        "recommended_capability_calls": recommended_calls,
        "capabilities": list_advance_capabilities(),
    }
    if persist:
        result["advancement"] = persist_advancement_result(
            store,
            agenda=agenda,
            mode="auto",
            since=since,
            status="planned",
            capability_calls=recommended_calls,
            metadata={"dry_run": True},
            workline_status="planned",
            opportunity_status="planned",
        )
    return result


def build_advance_agenda(
    store: MemSuStore | None = None,
    *,
    since: str = "24h",
    limit: int = 10,
    rank_method: str = "rule",
    model: str = "",
) -> dict[str, Any]:
    store = store or MemSuStore()
    store.init()
    source_limit = max(limit, 50)
    since_cutoff = parse_since_cutoff(since)
    snapshots = filter_by_since(
        store.list_observation_snapshots(limit=source_limit),
        since_cutoff=since_cutoff,
        timestamp_keys=("created_at",),
    )[:3]
    findings = filter_by_since(
        store.list_observation_findings(limit=source_limit),
        since_cutoff=since_cutoff,
        timestamp_keys=("created_at",),
    )[:limit]
    candidates = filter_by_since(
        store.list_candidates(status="pending", limit=source_limit),
        since_cutoff=since_cutoff,
        timestamp_keys=("updated_at", "created_at"),
    )[:limit]
    conflicts = filter_by_since(
        store.list_conflict_reviews(status="open", limit=source_limit),
        since_cutoff=since_cutoff,
        timestamp_keys=("updated_at", "created_at"),
    )[:limit]
    summaries = filter_by_since(
        store.list_memory_summaries(limit=source_limit),
        since_cutoff=since_cutoff,
        timestamp_keys=("updated_at", "created_at"),
    )[:limit]
    events = filter_by_since(
        store.list_events(limit=source_limit),
        since_cutoff=since_cutoff,
        timestamp_keys=("timestamp",),
    )[:limit]

    worklines = derive_worklines(
        snapshots=snapshots,
        findings=findings,
        events=events,
        limit=limit,
    )
    suggestions = derive_suggestions(
        snapshots=snapshots,
        worklines=worklines,
        candidates=candidates,
        conflicts=conflicts,
        summaries=summaries,
    )
    history_suggestions = derive_history_suggestions(store, worklines=worklines)
    suggestions.extend(history_suggestions)
    suggestions, ranking = rank_suggestions(
        suggestions,
        worklines=worklines,
        method=rank_method,
        model=model,
    )
    brief = render_agenda_brief(
        worklines=worklines,
        suggestions=suggestions,
        candidates=candidates,
        conflicts=conflicts,
        snapshots=snapshots,
    )

    return {
        "ok": True,
        "mode": "agenda",
        "since": since,
        "worklines": worklines,
        "suggestions": suggestions,
        "pending_candidate_count": len(candidates),
        "open_conflict_count": len(conflicts),
        "summary_count": len(summaries),
        "history_suggestion_count": len(history_suggestions),
        "ranking": ranking,
        "latest_snapshot_id": snapshots[0]["snapshot_id"] if snapshots else "",
        "brief": brief,
        "source_counts": {
            "snapshots": len(snapshots),
            "findings": len(findings),
            "events": len(events),
            "summaries": len(summaries),
            "history_suggestions": len(history_suggestions),
        },
    }


def persist_advancement_result(
    store: MemSuStore,
    *,
    agenda: dict[str, Any],
    mode: str,
    since: str,
    status: str,
    capability_calls: list[dict[str, Any]],
    policy_results: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    workline_status: str = "active",
    opportunity_status: str = "",
) -> dict[str, Any]:
    policy_results = policy_results or []
    run = store.record_advancement_run(
        mode=mode,
        since=since,
        status=status,
        policy_summary=summarize_policy_results(policy_results),
        capability_calls=capability_calls,
        metadata={
            "latest_snapshot_id": agenda.get("latest_snapshot_id", ""),
            "source_counts": agenda.get("source_counts", {}),
            **(metadata or {}),
        },
        finished_at=utc_now(),
    )
    workline_records: list[dict[str, Any]] = []
    for workline in agenda.get("worklines", []):
        snapshot_id = workline.get("snapshot_id", "")
        workline_records.append(
            store.record_workline(
                run_id=run["run_id"],
                title=workline.get("title", ""),
                scope=workline.get("scope", ""),
                status=workline_status,
                confidence=float(workline.get("confidence") or 0.5),
                evidence_ids=workline_evidence(workline),
                source_snapshot_ids=[snapshot_id] if snapshot_id else [],
                summary=workline.get("title", ""),
                metadata={
                    "basis": workline.get("basis", ""),
                    "facts": workline.get("facts", []),
                    "inferences": workline.get("inferences", []),
                    "unknowns": workline.get("unknowns", []),
                    "finding_id": workline.get("finding_id", ""),
                    "event_id": workline.get("event_id", ""),
                },
            )
        )

    opportunity_records: list[dict[str, Any]] = []
    suggestions = policy_results or agenda.get("suggestions", [])
    default_workline_id = workline_records[0]["workline_id"] if workline_records else ""
    evidence_to_workline = workline_evidence_index(workline_records)
    capability_name = (metadata or {}).get("capability_name", "")
    for item in suggestions:
        policy = item.get("policy", {})
        opportunity_records.append(
            store.record_advancement_opportunity(
                run_id=run["run_id"],
                workline_id=resolve_opportunity_workline_id(
                    item,
                    evidence_to_workline=evidence_to_workline,
                    default_workline_id=default_workline_id,
                ),
                kind=item.get("kind", "suggestion"),
                title=item.get("kind", "suggestion"),
                description=item.get("description", ""),
                risk_level=policy.get("risk_level") or item.get("risk_level", "L2"),
                policy_decision=policy.get("decision", "not_evaluated"),
                status=policy.get("status") or opportunity_status or "suggested",
                evidence_ids=item.get("evidence", []),
                proposal_id=policy.get("proposal_id", ""),
                capability_name=capability_name,
                metadata={
                    "priority": item.get("priority", 0),
                    "policy": policy,
                },
            )
        )

    return {
        "run": run,
        "worklines": workline_records,
        "opportunities": opportunity_records,
    }


def summarize_policy_results(policy_results: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "count": len(policy_results),
        "by_status": {},
        "by_risk_level": {},
    }
    for item in policy_results:
        policy = item.get("policy", {})
        status = policy.get("status", "unknown")
        risk = policy.get("risk_level", item.get("risk_level", "unknown"))
        summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
        summary["by_risk_level"][risk] = summary["by_risk_level"].get(risk, 0) + 1
    return summary


def workline_evidence_index(workline_records: list[dict[str, Any]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for workline in workline_records:
        workline_id = workline.get("workline_id", "")
        if not workline_id:
            continue
        for evidence_id in workline.get("evidence_ids", []):
            if evidence_id:
                index.setdefault(str(evidence_id), workline_id)
        for snapshot_id in workline.get("source_snapshot_ids", []):
            if snapshot_id:
                index.setdefault(str(snapshot_id), workline_id)
    return index


def resolve_opportunity_workline_id(
    item: dict[str, Any],
    *,
    evidence_to_workline: dict[str, str],
    default_workline_id: str,
) -> str:
    for evidence_id in item.get("evidence", []):
        evidence_text = str(evidence_id)
        if evidence_text in evidence_to_workline:
            return evidence_to_workline[evidence_text]
        if evidence_text.startswith("wl_"):
            return evidence_text
    if item.get("kind") == "continue_workline":
        return default_workline_id
    return ""


def run_advance_skill(
    store: MemSuStore | None = None,
    *,
    skill: str,
    since: str = "24h",
    limit: int = 10,
    evidence_home: str | Path | None = None,
    dry_run: bool = False,
    skip_observe: bool = False,
    rank_method: str = "rule",
    model: str = "",
) -> dict[str, Any]:
    store = store or MemSuStore()
    store.init()
    normalized = normalize_capability_name(skill)
    capability = get_advance_capability(name=normalized, kind="skill")
    if capability is None:
        return {
            "ok": False,
            "status": "unsupported_skill",
            "skill": skill,
            "supported_skills": supported_capability_names(kind="skill"),
        }

    if dry_run:
        agenda = build_advance_agenda(
            store,
            since=since,
            limit=limit,
            rank_method=rank_method,
            model=model,
        )
        capability_calls = [
            {
                "kind": "skill",
                "name": normalized,
                "risk_level": capability.max_risk_level,
                "dry_run": True,
            }
        ]
        return {
            "ok": True,
            "status": "planned",
            "skill": normalized,
            "capability": capability.to_dict(),
            "since": since,
            "would_call": list(capability.allowed_commands),
            "skip_observe": skip_observe,
            "agenda": agenda,
            "advancement": persist_advancement_result(
                store,
                agenda=agenda,
                mode="skill",
                since=since,
                status="planned",
                capability_calls=capability_calls,
                metadata={
                    "capability_name": normalized,
                    "dry_run": True,
                    "skip_observe": skip_observe,
                },
                workline_status="planned",
                opportunity_status="planned",
            ),
        }

    observe_snapshot = None
    if not skip_observe:
        observe_snapshot = run_observe(store, evidence_home=evidence_home)

    agenda = build_advance_agenda(
        store,
        since=since,
        limit=limit,
        rank_method=rank_method,
        model=model,
    )
    policy_results = evaluate_suggestions(store, agenda["suggestions"])
    brief = render_proposal_brief(
        agenda=agenda,
        policy_results=policy_results,
    )
    event = store.append_event(
        source_agent="memsu",
        source_type=f"skill:{normalized}",
        actor="system",
        event_type="workflow_result",
        content=brief,
        content_ref="",
        sensitivity="normal",
        metadata={
            "skill": normalized,
            "capability_kind": capability.kind,
            "capability_version": capability.version,
            "max_risk_level": capability.max_risk_level,
            "since": since,
            "observe_snapshot_id": observe_snapshot["snapshot_id"] if observe_snapshot else "",
            "agenda_latest_snapshot_id": agenda.get("latest_snapshot_id", ""),
            "policy_result_count": len(policy_results),
            "output_contract": capability.output_contract,
        },
    )
    capability_calls = [
        {
            "kind": "skill",
            "name": normalized,
            "risk_level": capability.max_risk_level,
            "event_id": event["event_id"],
        }
    ]
    advancement = persist_advancement_result(
        store,
        agenda=agenda,
        mode="skill",
        since=since,
        status="completed",
        capability_calls=capability_calls,
        policy_results=policy_results,
        metadata={
            "capability_name": normalized,
            "event_id": event["event_id"],
            "observe_snapshot_id": observe_snapshot["snapshot_id"] if observe_snapshot else "",
            "skip_observe": skip_observe,
        },
    )

    return {
        "ok": True,
        "status": "completed",
        "skill": normalized,
        "capability": capability.to_dict(),
        "since": since,
        "observe_snapshot": observe_snapshot,
        "agenda": agenda,
        "policy_results": policy_results,
        "event": event,
        "advancement": advancement,
        "brief": brief,
    }


def run_advance_adapter(
    store: MemSuStore | None = None,
    *,
    adapter: str,
    repo_path: str | Path = ".",
    workspace: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    store = store or MemSuStore()
    store.init()
    normalized = normalize_capability_name(adapter)
    capability = get_advance_capability(name=normalized, kind="adapter")
    if capability is None:
        return {
            "ok": False,
            "status": "unsupported_adapter",
            "adapter": adapter,
            "supported_adapters": supported_capability_names(kind="adapter"),
        }

    if dry_run:
        advancement_run = store.record_advancement_run(
            mode="adapter",
            status="planned",
            policy_summary={},
            capability_calls=[
                {
                    "kind": "adapter",
                    "name": normalized,
                    "risk_level": capability.max_risk_level,
                    "dry_run": True,
                }
            ],
            metadata={
                "capability_name": normalized,
                "repo_path": str(repo_path),
                "workspace": workspace,
                "dry_run": True,
            },
            finished_at=utc_now(),
        )
        return {
            "ok": True,
            "status": "planned",
            "adapter": normalized,
            "capability": capability.to_dict(),
            "repo_path": str(repo_path),
            "workspace": workspace,
            "would_call": list(capability.allowed_commands),
            "advancement": {"run": advancement_run, "worklines": [], "opportunities": []},
        }

    if normalized != GIT_ACTIVITY:
        return {
            "ok": False,
            "status": "adapter_not_implemented",
            "adapter": normalized,
        }

    event = snapshot_git_repo(
        store,
        repo_path=str(repo_path),
        workspace=workspace,
        sensitivity="normal",
    )
    advancement_run = store.record_advancement_run(
        mode="adapter",
        status="completed",
        policy_summary={"count": 0, "by_status": {}, "by_risk_level": {}},
        capability_calls=[
            {
                "kind": "adapter",
                "name": normalized,
                "risk_level": capability.max_risk_level,
                "event_id": event["event_id"],
            }
        ],
        metadata={
            "capability_name": normalized,
            "repo_path": str(repo_path),
            "workspace": workspace,
            "event_id": event["event_id"],
        },
        finished_at=utc_now(),
    )
    return {
        "ok": True,
        "status": "completed",
        "adapter": normalized,
        "capability": capability.to_dict(),
        "event": event,
        "advancement": {"run": advancement_run, "worklines": [], "opportunities": []},
    }


def derive_worklines(
    *,
    snapshots: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    events: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    worklines: list[dict[str, Any]] = []
    if snapshots:
        latest = snapshots[0]
        session_summaries = latest.get("sources", {}).get("session_summaries", {})
        if isinstance(session_summaries, dict):
            for source, summaries in session_summaries.items():
                for summary in list(summaries or [])[:2]:
                    worklines.append(
                        {
                            "title": compact(f"{source}: {summary}", 180),
                            "scope": f"agent:{source.lower()}",
                            "confidence": 0.75,
                            "basis": "latest_observe_session_summary",
                            "snapshot_id": latest["snapshot_id"],
                            "facts": [compact(summary, 220)],
                            "inferences": ["该 agent 最近可能对应一个活跃工作线。"],
                            "unknowns": ["需要更明确的项目证据才能确认下一步动作。"],
                        }
                    )
        if not worklines:
            for item in latest.get("current_picture", [])[:2]:
                worklines.append(
                    {
                        "title": compact(item, 140),
                        "scope": "observe:latest",
                        "confidence": 0.6,
                        "basis": "latest_observe_current_picture",
                        "snapshot_id": latest["snapshot_id"],
                        "facts": [compact(item, 220)],
                        "inferences": [],
                        "unknowns": latest.get("unknown", [])[:2],
                    }
                )

    for finding in findings:
        if len(worklines) >= limit:
            break
        worklines.append(
            {
                "title": compact(finding.get("claim", ""), 160),
                "scope": finding.get("scope") or "finding",
                "confidence": float(finding.get("confidence") or 0.5),
                "basis": f"observation_finding:{finding.get('kind') or 'unknown'}",
                "finding_id": finding.get("finding_id", ""),
                "facts": [compact(finding.get("claim", ""), 220)],
                "inferences": [],
                "unknowns": [],
            }
        )

    for event in events:
        if len(worklines) >= limit:
            break
        if event.get("event_type") != "workflow_result":
            continue
        content = compact(event.get("content", ""), 180)
        if not content:
            continue
        worklines.append(
            {
                "title": content,
                "scope": event.get("workspace") or event.get("repo") or "workflow",
                "confidence": 0.55,
                "basis": "recent_workflow_event",
                "event_id": event.get("event_id", ""),
                "facts": [content],
                "inferences": [],
                "unknowns": [],
            }
        )

    if not worklines:
        worklines.append(
            {
                "title": "暂无足够观察记录；建议先运行 memSu observe。",
                "scope": "observe",
                "confidence": 0.4,
                "basis": "no_recent_observe_context",
                "facts": [],
                "inferences": [],
                "unknowns": ["缺少 observe snapshot 或 recent workflow event。"],
            }
        )
    return worklines[:limit]


def derive_suggestions(
    *,
    snapshots: list[dict[str, Any]],
    worklines: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    if not snapshots:
        suggestions.append(
            suggestion(
                "run_observe",
                "运行 memSu observe，先建立最新本机工作图景。",
                evidence=[],
                priority=0.9,
            )
        )
    if candidates:
        suggestions.append(
            suggestion(
                "review_candidates",
                f"review {len(candidates)} 条 pending memory candidates，避免有价值观察停留在候选区。",
                evidence=[item["candidate_id"] for item in candidates[:5]],
                priority=0.85,
            )
        )
    if conflicts:
        suggestions.append(
            suggestion(
                "resolve_conflicts",
                f"检查 {len(conflicts)} 条 open conflict reviews，确认是否存在过期或冲突记忆。",
                evidence=[item["review_id"] for item in conflicts[:5]],
                priority=0.8,
            )
        )
    if worklines:
        strongest = worklines[0]
        suggestions.append(
            suggestion(
                "continue_workline",
                f"围绕当前最强工作线继续推进：{strongest['title']}",
                evidence=workline_evidence(strongest),
                priority=float(strongest.get("confidence") or 0.5),
            )
        )
    if summaries and not candidates and not conflicts:
        suggestions.append(
            suggestion(
                "inject_context",
                "在下一次 agent 工作前注入相关 scope summary，减少重复解释。",
                evidence=[item["summary_id"] for item in summaries[:5]],
                priority=0.55,
            )
        )
    return suggestions


def derive_history_suggestions(
    store: MemSuStore,
    *,
    worklines: list[dict[str, Any]],
    repeat_threshold: int = 3,
    stale_days: int = 14,
) -> list[dict[str, Any]]:
    previous = store.list_worklines(status="active", limit=200)
    suggestions: list[dict[str, Any]] = []
    current_signatures = {workline_signature(item) for item in worklines}

    for workline in worklines:
        if not is_reusable_workline(workline):
            continue
        signature = workline_signature(workline)
        if not signature:
            continue
        matches = [
            item
            for item in previous
            if is_reusable_workline(item) and workline_signature(item) == signature
        ]
        total_count = len(matches) + 1
        if total_count < repeat_threshold:
            continue
        evidence = [item["workline_id"] for item in matches[:5]]
        evidence.extend(workline_evidence(workline))
        suggestions.append(
            suggestion(
                "create_skill_candidate",
                f"工作线“{workline['title']}”已重复出现 {total_count} 次，可考虑沉淀为稳定 skill 或 adapter。",
                evidence=evidence,
                priority=min(0.95, 0.55 + total_count * 0.1),
            )
        )

    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
    stale_seen: set[str] = set()
    for item in previous:
        if not is_reusable_workline(item):
            continue
        signature = workline_signature(item)
        if not signature or signature in current_signatures or signature in stale_seen:
            continue
        created_at = parse_timestamp(item.get("created_at", ""))
        if created_at is None or created_at >= stale_cutoff:
            continue
        stale_seen.add(signature)
        suggestions.append(
            suggestion(
                "review_stale_workline",
                f"历史工作线“{item['title']}”超过 {stale_days} 天未在当前议程中出现，可 review 是否标记为已结束或降权。",
                evidence=[item["workline_id"]],
                priority=0.45,
            )
        )

    return dedupe_suggestions(suggestions)


def rank_suggestions(
    suggestions: list[dict[str, Any]],
    *,
    worklines: list[dict[str, Any]],
    method: str = "rule",
    model: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    requested = (method or "rule").strip().lower()
    if requested not in {"rule", "llm"}:
        requested = "rule"
    if requested == "llm":
        endpoint = os.environ.get("MEMSU_LLM_ENDPOINT", "")
        if endpoint:
            try:
                ranked = rank_suggestions_with_llm(
                    suggestions,
                    worklines=worklines,
                    endpoint=endpoint,
                    model=model or os.environ.get("MEMSU_LLM_MODEL", "memsu-advance-ranker"),
                )
                return ranked, {
                    "method": "llm",
                    "requested_method": requested,
                    "model": model or os.environ.get("MEMSU_LLM_MODEL", "memsu-advance-ranker"),
                    "fallback": False,
                }
            except Exception as exc:
                ranked = rank_suggestions_by_rule(suggestions)
                return ranked, {
                    "method": "rule",
                    "requested_method": requested,
                    "fallback": True,
                    "reason": str(exc),
                }
        ranked = rank_suggestions_by_rule(suggestions)
        return ranked, {
            "method": "rule",
            "requested_method": requested,
            "fallback": True,
            "reason": "MEMSU_LLM_ENDPOINT is not configured.",
        }
    return rank_suggestions_by_rule(suggestions), {
        "method": "rule",
        "requested_method": requested,
        "fallback": False,
    }


def rank_suggestions_by_rule(suggestions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        suggestions,
        key=lambda item: float(item.get("priority") or 0),
        reverse=True,
    )
    return [
        {
            **item,
            "rank": index,
            "rank_reason": item.get("rank_reason", "rule_priority"),
        }
        for index, item in enumerate(ranked, start=1)
    ]


def rank_suggestions_with_llm(
    suggestions: list[dict[str, Any]],
    *,
    worklines: list[dict[str, Any]],
    endpoint: str,
    model: str,
) -> list[dict[str, Any]]:
    if not suggestions:
        return []
    indexed = [
        {
            "id": f"sug_{index}",
            "kind": item.get("kind", ""),
            "risk_level": item.get("risk_level", "L2"),
            "priority": item.get("priority", 0),
            "description": item.get("description", ""),
            "evidence": item.get("evidence", []),
        }
        for index, item in enumerate(suggestions)
    ]
    prompt = (
        "Rank these memSu advancement suggestions. Return JSON only with key "
        "ranked, an array of objects with id and reason. Do not propose actions. "
        "Only rank suggestions that include risk_level and evidence fields.\n"
        + json.dumps(
            {
                "worklines": worklines[:5],
                "suggestions": indexed,
            },
            ensure_ascii=False,
        )
    )
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You rank local memSu suggestions without authorizing or executing actions.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }
    headers = {"Content-Type": "application/json; charset=utf-8"}
    api_key = os.environ.get("MEMSU_LLM_API_KEY", "")
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
    content = extract_llm_content(data)
    ranking = json.loads(content)
    ranked_payloads = ranking.get("ranked", []) if isinstance(ranking, dict) else []
    by_id = {f"sug_{index}": item for index, item in enumerate(suggestions)}
    ranked: list[dict[str, Any]] = []
    used: set[str] = set()
    for payload_item in ranked_payloads:
        if not isinstance(payload_item, dict):
            continue
        suggestion_id = str(payload_item.get("id") or "")
        suggestion = by_id.get(suggestion_id)
        if not suggestion or suggestion_id in used:
            continue
        if not suggestion.get("risk_level") or "evidence" not in suggestion:
            continue
        used.add(suggestion_id)
        ranked.append(
            {
                **suggestion,
                "rank": len(ranked) + 1,
                "rank_reason": str(payload_item.get("reason") or "llm_ranked"),
            }
        )
    for suggestion_id, suggestion in by_id.items():
        if suggestion_id in used:
            continue
        ranked.append(
            {
                **suggestion,
                "rank": len(ranked) + 1,
                "rank_reason": "llm_unranked_rule_append",
            }
        )
    return ranked


def extract_llm_content(payload: dict[str, Any]) -> str:
    if "ranked" in payload:
        return json.dumps(payload, ensure_ascii=False)
    choices = payload.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
    raise ValueError("LLM response did not contain ranking JSON")


def workline_signature(workline: dict[str, Any]) -> str:
    scope = str(workline.get("scope") or "").strip().lower()
    title = " ".join(str(workline.get("title") or "").lower().split())
    if not scope and not title:
        return ""
    return f"{scope}:{title[:80]}"


def is_reusable_workline(workline: dict[str, Any]) -> bool:
    scope = str(workline.get("scope") or "").strip().lower()
    title = str(workline.get("title") or "").strip().lower()
    raw_metadata = workline.get("metadata")
    metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    basis = str(workline.get("basis") or metadata.get("basis") or "").strip().lower()
    if scope in {"finding", "observe", "observe:latest"}:
        return False
    if basis in {"observation_finding:plan", "no_recent_observe_context"}:
        return False
    noisy_titles = (
        "agent-led observe plan created",
        "暂无足够观察记录",
    )
    return not any(title.startswith(noise) for noise in noisy_titles)


def parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_since_cutoff(since: str) -> datetime | None:
    value = (since or "").strip().lower()
    if not value:
        return None
    units = {
        "m": "minutes",
        "h": "hours",
        "d": "days",
    }
    suffix = value[-1:]
    amount = value[:-1]
    if suffix in units and amount.isdigit():
        return datetime.now(timezone.utc) - timedelta(**{units[suffix]: int(amount)})
    parsed = parse_timestamp(value)
    if parsed is None:
        return None
    return parsed.astimezone(timezone.utc)


def filter_by_since(
    items: list[dict[str, Any]],
    *,
    since_cutoff: datetime | None,
    timestamp_keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    if since_cutoff is None:
        return items
    filtered: list[dict[str, Any]] = []
    for item in items:
        timestamp = None
        for key in timestamp_keys:
            timestamp = parse_timestamp(str(item.get(key) or ""))
            if timestamp is not None:
                break
        if timestamp is not None and timestamp.astimezone(timezone.utc) >= since_cutoff:
            filtered.append(item)
    return filtered


def dedupe_suggestions(suggestions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in suggestions:
        key = (item.get("kind", ""), item.get("description", ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def suggestion(kind: str, description: str, *, evidence: list[str], priority: float) -> dict[str, Any]:
    return {
        "kind": kind,
        "action_type": "suggestion",
        "risk_level": "L2",
        "description": description,
        "evidence": evidence,
        "priority": round(priority, 3),
    }


def workline_evidence(workline: dict[str, Any]) -> list[str]:
    for key in ["snapshot_id", "finding_id", "event_id"]:
        value = workline.get(key)
        if value:
            return [str(value)]
    return []


def evaluate_suggestions(
    store: MemSuStore,
    suggestions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in suggestions:
        result = store.evaluate_policy(
            action_type=item.get("action_type", "suggestion"),
            description=item.get("description", ""),
            sensitivity="normal",
            metadata={
                "capability": OBSERVE_TO_PROPOSALS,
                "suggestion_kind": item.get("kind", ""),
                "evidence": item.get("evidence", []),
                "priority": item.get("priority", 0),
            },
        )
        results.append({**item, "policy": result})
    return results


def render_agenda_brief(
    *,
    worklines: list[dict[str, Any]],
    suggestions: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
) -> str:
    lines = ["# memSu 推进议程", ""]
    if snapshots:
        latest = snapshots[0]
        lines.append(f"最新观察：{latest['local_date']} {latest['local_time']} ({latest['snapshot_id']})")
    else:
        lines.append("最新观察：无")
    lines.append("")
    lines.extend(render_worklines(worklines))
    lines.extend(render_suggestions(suggestions, title="建议"))
    lines.append("## 候选记忆")
    if candidates:
        lines.extend(f"- {item['candidate_id']}: {compact(item['content'], 120)}" for item in candidates[:5])
    else:
        lines.append("- 无 pending candidates")
    lines.append("")
    lines.append("## 冲突")
    if conflicts:
        lines.extend(f"- {item['review_id']}: candidate={item['candidate_id']} item={item['item_id']}" for item in conflicts[:5])
    else:
        lines.append("- 无 open conflicts")
    lines.append("")
    return "\n".join(lines)


def render_proposal_brief(
    *,
    agenda: dict[str, Any],
    policy_results: list[dict[str, Any]],
) -> str:
    lines = ["# memSu 观察后提议", ""]
    lines.extend(render_worklines(agenda["worklines"]))
    lines.extend(render_suggestions(policy_results, title="建议"))
    pending = [
        item for item in policy_results
        if item.get("policy", {}).get("status") == "pending_confirmation"
    ]
    lines.append("## 待确认")
    if pending:
        lines.extend(f"- [L3] {item['description']}" for item in pending)
    else:
        lines.append("- 无")
    lines.append("")
    lines.append("## 未知")
    unknowns: list[str] = []
    for workline in agenda["worklines"]:
        unknowns.extend(workline.get("unknowns", []))
    if unknowns:
        lines.extend(f"- {compact(item, 160)}" for item in unknowns[:5])
    else:
        lines.append("- 暂无明确未知项")
    lines.append("")
    lines.append("## 原始议程")
    lines.append("```json")
    lines.append(json_dumps({"worklines": agenda["worklines"], "suggestions": agenda["suggestions"]}))
    lines.append("```")
    return "\n".join(lines)


def render_worklines(worklines: list[dict[str, Any]]) -> list[str]:
    lines = ["## 当前主线"]
    for item in worklines[:5]:
        lines.append(
            f"- {item['title']}；scope={item['scope']}；confidence={item['confidence']}"
        )
    if not worklines:
        lines.append("- 无")
    lines.append("")
    lines.append("## 证据")
    for item in worklines[:5]:
        refs = workline_evidence(item)
        basis = item.get("basis", "unknown")
        ref_text = ", ".join(refs) if refs else "无直接 id"
        lines.append(f"- {basis}: {ref_text}")
    if not worklines:
        lines.append("- 无")
    lines.append("")
    return lines


def render_suggestions(suggestions: list[dict[str, Any]], *, title: str) -> list[str]:
    lines = [f"## {title}"]
    if not suggestions:
        lines.append("- 无")
    for item in suggestions[:8]:
        policy = item.get("policy", {})
        policy_status = policy.get("status")
        suffix = f"；policy={policy_status}" if policy_status else ""
        lines.append(
            f"- [L2] {item['description']}；kind={item['kind']}; priority={item['priority']}{suffix}"
        )
    lines.append("")
    return lines


def compact(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit]
