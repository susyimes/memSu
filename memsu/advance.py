from __future__ import annotations

from pathlib import Path
from typing import Any

from .observe import run_observe
from .store import MemSuStore, json_dumps


OBSERVE_TO_PROPOSALS = "observe-to-proposals"
SUPPORTED_SKILLS = {OBSERVE_TO_PROPOSALS}


def build_advance_agenda(
    store: MemSuStore | None = None,
    *,
    since: str = "24h",
    limit: int = 10,
) -> dict[str, Any]:
    store = store or MemSuStore()
    store.init()
    snapshots = store.list_observation_snapshots(limit=3)
    findings = store.list_observation_findings(limit=limit)
    candidates = store.list_candidates(status="pending", limit=limit)
    conflicts = store.list_conflict_reviews(status="open", limit=limit)
    summaries = store.list_memory_summaries(limit=limit)
    events = store.list_events(limit=limit)

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
        "latest_snapshot_id": snapshots[0]["snapshot_id"] if snapshots else "",
        "brief": brief,
        "source_counts": {
            "snapshots": len(snapshots),
            "findings": len(findings),
            "events": len(events),
            "summaries": len(summaries),
        },
    }


def run_advance_skill(
    store: MemSuStore | None = None,
    *,
    skill: str,
    since: str = "24h",
    evidence_home: str | Path | None = None,
    dry_run: bool = False,
    skip_observe: bool = False,
) -> dict[str, Any]:
    store = store or MemSuStore()
    store.init()
    normalized = normalize_skill_name(skill)
    if normalized not in SUPPORTED_SKILLS:
        return {
            "ok": False,
            "status": "unsupported_skill",
            "skill": skill,
            "supported_skills": sorted(SUPPORTED_SKILLS),
        }

    if dry_run:
        agenda = build_advance_agenda(store, since=since)
        return {
            "ok": True,
            "status": "planned",
            "skill": normalized,
            "since": since,
            "would_call": [
                "observe run" if not skip_observe else "observe read",
                "candidate list",
                "curator conflicts",
                "policy evaluate suggestion",
                "adapter workflow",
            ],
            "agenda": agenda,
        }

    observe_snapshot = None
    if not skip_observe:
        observe_snapshot = run_observe(store, evidence_home=evidence_home)

    agenda = build_advance_agenda(store, since=since)
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
            "since": since,
            "observe_snapshot_id": observe_snapshot["snapshot_id"] if observe_snapshot else "",
            "agenda_latest_snapshot_id": agenda.get("latest_snapshot_id", ""),
            "policy_result_count": len(policy_results),
            "output_contract": "observe-to-proposals",
        },
    )

    return {
        "ok": True,
        "status": "completed",
        "skill": normalized,
        "since": since,
        "observe_snapshot": observe_snapshot,
        "agenda": agenda,
        "policy_results": policy_results,
        "event": event,
        "brief": brief,
    }


def normalize_skill_name(skill: str) -> str:
    return (skill or "").strip().lower().replace("_", "-")


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
