from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .observe import local_timezone
from .paths import memsu_home
from .store import MemSuStore, stable_hash, utc_now


ADVANCE_WORKFLOW_NAME = "advance-agenda"


def run_advance_agenda(
    store: MemSuStore | None = None,
    *,
    limit: int = 5,
    record: bool = True,
) -> dict[str, Any]:
    store = store or MemSuStore()
    store.init()
    limit = max(1, min(limit, 5))
    context = collect_agenda_context(store)
    worklines = detect_worklines(context, limit=limit)
    opportunities = generate_opportunities(store, context, worklines)
    policy_summary = summarize_policy(opportunities)
    brief = render_agenda_brief(worklines, opportunities, context, policy_summary)
    brief_path = append_agenda_brief(brief)
    event = None
    if record:
        event = record_agenda_event(
            store,
            brief=brief,
            brief_path=brief_path,
            worklines=worklines,
            opportunities=opportunities,
            policy_summary=policy_summary,
            context=context,
        )
    return {
        "ok": True,
        "mode": "agenda",
        "brief_path": str(brief_path),
        "worklines": worklines,
        "opportunities": opportunities,
        "policy_summary": policy_summary,
        "input_counts": input_counts(context),
        "event": event,
    }


def collect_agenda_context(store: MemSuStore) -> dict[str, Any]:
    return {
        "snapshots": store.list_observation_snapshots(limit=5),
        "findings": store.list_observation_findings(limit=20),
        "candidates": store.list_candidates(status="pending", limit=20),
        "conflicts": store.list_conflict_reviews(status="open", limit=20),
        "summaries": store.list_memory_summaries(limit=20),
        "events": store.list_events(limit=40),
    }


def detect_worklines(context: dict[str, Any], *, limit: int = 5) -> list[dict[str, Any]]:
    worklines: list[dict[str, Any]] = []
    candidates = context["candidates"]
    conflicts = context["conflicts"]
    snapshots = context["snapshots"]
    findings = context["findings"]
    summaries = context["summaries"]
    events = context["events"]

    if candidates:
        scopes = Counter(candidate.get("scope") or "unspecified" for candidate in candidates)
        top_scope, top_count = scopes.most_common(1)[0]
        worklines.append(
            make_workline(
                title="Review pending memory candidates",
                scope=top_scope,
                confidence=0.95,
                summary=f"{len(candidates)} pending memory candidates need review; strongest scope is {top_scope}.",
                facts=[
                    f"{len(candidates)} pending candidates are present.",
                    f"{top_count} pending candidates belong to {top_scope}.",
                ],
                unknowns=["Which candidates should become durable memory is still user-reviewed."],
                evidence=[
                    evidence_ref("candidate", candidate["candidate_id"], candidate["content"])
                    for candidate in candidates[:5]
                ],
                priority=100,
            )
        )

    if conflicts:
        worklines.append(
            make_workline(
                title="Resolve open memory conflicts",
                scope="memory:conflicts",
                confidence=0.9,
                summary=f"{len(conflicts)} conflict reviews are open.",
                facts=[f"{len(conflicts)} conflict reviews are open."],
                unknowns=["The correct memory version needs review before conflict closure."],
                evidence=[
                    evidence_ref("conflict", conflict["review_id"], conflict.get("reason") or "")
                    for conflict in conflicts[:5]
                ],
                priority=95,
            )
        )

    worklines.extend(detect_codex_worklines(snapshots))
    worklines.extend(detect_git_worklines(events))
    worklines.extend(detect_finding_worklines(findings))
    worklines.extend(detect_summary_worklines(summaries))

    if snapshots and not worklines:
        latest = snapshots[0]
        worklines.append(
            make_workline(
                title="Keep the observation loop healthy",
                scope="system:observe",
                confidence=0.6,
                summary=latest.get("support_opportunity") or "Latest observation snapshot is available.",
                facts=trim_strings(latest.get("current_picture", []), 3),
                unknowns=trim_strings(latest.get("unknown", []), 3),
                evidence=[
                    evidence_ref("snapshot", latest["snapshot_id"], latest.get("support_opportunity", ""))
                ],
                priority=40,
            )
        )

    deduped = dedupe_worklines(worklines)
    deduped.sort(key=lambda item: (-item["priority"], -item["confidence"], item["title"]))
    for item in deduped:
        item.pop("priority", None)
    return deduped[:limit]


def detect_codex_worklines(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple[dict[str, Any], str]]] = defaultdict(list)
    active_snapshots: list[dict[str, Any]] = []
    seen_summaries: set[str] = set()
    for snapshot in snapshots:
        usage = snapshot.get("agent_usage", {})
        if "Codex" in usage and "0 个" not in str(usage.get("Codex", "")):
            active_snapshots.append(snapshot)
        summaries = (snapshot.get("sources", {}).get("session_summaries", {}) or {}).get("Codex", [])
        for summary in summaries:
            if summary in seen_summaries:
                continue
            seen_summaries.add(summary)
            cwd = extract_cwd(summary) or "Codex"
            grouped[cwd].append((snapshot, summary))

    worklines: list[dict[str, Any]] = []
    for cwd, entries in grouped.items():
        latest_snapshot = entries[0][0]
        has_project_cwd = cwd != "Codex"
        title = (
            f"Continue {cwd} work from Codex sessions"
            if has_project_cwd
            else "Review recent Codex session summaries"
        )
        summary = (
            f"{len(entries)} recent Codex session summaries point at {cwd}."
            if has_project_cwd
            else f"{len(entries)} recent Codex session summaries did not expose a project cwd."
        )
        worklines.append(
            make_workline(
                title=title,
                scope=f"project:{cwd}" if has_project_cwd else "agent:Codex",
                confidence=min(0.9, 0.55 + 0.1 * len(entries)) if has_project_cwd else 0.55,
                summary=summary,
                facts=trim_strings([entry[1] for entry in entries], 3),
                unknowns=trim_strings(latest_snapshot.get("unknown", []), 2),
                evidence=[
                    evidence_ref("snapshot", latest_snapshot["snapshot_id"], entries[0][1])
                ],
                priority=(80 + min(10, len(entries))) if has_project_cwd else 45,
            )
        )

    if active_snapshots and not grouped:
        latest = active_snapshots[0]
        worklines.append(
            make_workline(
                title="Continue active Codex work",
                scope="agent:Codex",
                confidence=0.7,
                summary=str(latest.get("agent_usage", {}).get("Codex", "")),
                facts=trim_strings(latest.get("current_picture", []), 3),
                unknowns=trim_strings(latest.get("unknown", []), 2),
                evidence=[evidence_ref("snapshot", latest["snapshot_id"], "Codex active in latest snapshot.")],
                priority=70,
            )
        )
    return worklines


def detect_git_worklines(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    worklines: list[dict[str, Any]] = []
    for event in events:
        if event.get("source_agent") != "git":
            continue
        metadata = event.get("metadata", {})
        repo = event.get("repo") or metadata.get("remote") or event.get("workspace") or "repository"
        status_short = str(metadata.get("status_short") or "")
        clean = not status_short.strip()
        priority = 75 if not clean else 55
        facts = [
            f"Git repo {repo} is on branch {metadata.get('branch', '') or 'unknown'}.",
            f"HEAD is {metadata.get('head', '') or 'unknown'}.",
            "Working tree is clean." if clean else "Working tree has uncommitted changes.",
        ]
        worklines.append(
            make_workline(
                title=f"Review Git state for {repo}",
                scope=f"repo:{repo}",
                confidence=0.75 if not clean else 0.6,
                summary=event.get("content", "").splitlines()[0] if event.get("content") else f"Git event for {repo}.",
                facts=facts,
                unknowns=[] if not clean else ["No next step is obvious from a clean Git snapshot alone."],
                evidence=[evidence_ref("event", event["event_id"], event.get("content", ""))],
                priority=priority,
            )
        )
    return worklines


def detect_finding_worklines(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for finding in findings[:5]:
        if finding.get("status") in {"closed", "rejected"}:
            continue
        scope = finding.get("scope") or "observation:findings"
        result.append(
            make_workline(
                title=f"Follow observation finding: {compact(finding.get('kind') or 'finding', 48)}",
                scope=scope,
                confidence=float(finding.get("confidence") or 0.5),
                summary=finding.get("claim") or "",
                facts=[finding.get("claim") or ""],
                unknowns=[],
                evidence=[
                    evidence_ref("finding", finding["finding_id"], finding.get("claim", ""))
                ],
                priority=50,
            )
        )
    return result


def detect_summary_worklines(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for summary in summaries[:5]:
        scope = summary.get("scope") or "memory:summaries"
        result.append(
            make_workline(
                title=f"Use memory summary for {scope}",
                scope=scope,
                confidence=0.55,
                summary=summary.get("summary") or "",
                facts=[summary.get("summary") or ""],
                unknowns=["Summary relevance depends on the next user task."],
                evidence=[
                    evidence_ref("summary", summary["summary_id"], summary.get("summary", ""))
                ],
                priority=35,
            )
        )
    return result


def generate_opportunities(
    store: MemSuStore,
    context: dict[str, Any],
    worklines: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    opportunities: list[dict[str, Any]] = []
    candidates = context["candidates"]
    conflicts = context["conflicts"]
    snapshots = context["snapshots"]
    top_workline = worklines[0] if worklines else None

    if candidates:
        opportunities.append(
            make_opportunity(
                kind="review_candidates",
                title="Review pending memory candidates",
                description=f"Review {len(candidates)} pending memory candidates and accept or reject durable items.",
                action_type="suggestion",
                workline_id=find_workline_id(worklines, "Review pending memory candidates"),
                evidence=[evidence_ref("candidate", item["candidate_id"], item["content"]) for item in candidates[:3]],
            )
        )

    opportunities.append(
        make_opportunity(
            kind="run_maintenance",
            title="Run the safe maintenance loop",
            description="Run observe, extract, curator, and optional vector rebuild as explicit maintenance.",
            action_type="maintenance",
            workline_id=top_workline["workline_id"] if top_workline else "",
            evidence=latest_snapshot_evidence(snapshots),
        )
    )

    if top_workline:
        opportunities.append(
            make_opportunity(
                kind="continue_workline",
                title=f"Next step for {top_workline['title']}",
                description=next_step_for_workline(top_workline),
                action_type="workflow_recommendation",
                workline_id=top_workline["workline_id"],
                evidence=top_workline["evidence"][:3],
            )
        )

    if should_suggest_skill(context, worklines):
        opportunities.append(
            make_opportunity(
                kind="create_skill_candidate",
                title="Consider a skill or adapter for repeated agent workflow",
                description="Recent agent activity appears repeated enough to consider a Hermes skill, memSu adapter, or documented workflow.",
                action_type="skill_recommendation",
                workline_id=top_workline["workline_id"] if top_workline else "",
                evidence=latest_snapshot_evidence(snapshots),
            )
        )

    if conflicts:
        opportunities.append(
            make_opportunity(
                kind="resolve_conflict",
                title="Resolve open memory conflicts",
                description=f"Inspect {len(conflicts)} open conflict reviews and decide which memory should remain active.",
                action_type="suggestion",
                workline_id=find_workline_id(worklines, "Resolve open memory conflicts"),
                evidence=[evidence_ref("conflict", item["review_id"], item.get("reason") or "") for item in conflicts[:3]],
            )
        )

    for opportunity in opportunities:
        policy = store.evaluate_policy(
            action_type=opportunity["action_type"],
            description=opportunity["description"],
            sensitivity="normal",
            metadata={
                "opportunity_kind": opportunity["kind"],
                "workline_id": opportunity.get("workline_id", ""),
                "source": "advance_agenda",
            },
        )
        opportunity["policy"] = policy
    return opportunities


def make_workline(
    *,
    title: str,
    scope: str,
    confidence: float,
    summary: str,
    facts: list[str],
    unknowns: list[str],
    evidence: list[dict[str, str]],
    priority: int,
) -> dict[str, Any]:
    return {
        "workline_id": "wl_" + stable_hash(title, scope)[:16],
        "title": title,
        "scope": scope,
        "status": "active",
        "confidence": round(float(confidence), 2),
        "summary": compact(summary, 280),
        "facts": trim_strings(facts, 5),
        "unknowns": trim_strings(unknowns, 5),
        "evidence": evidence[:8],
        "priority": priority,
    }


def make_opportunity(
    *,
    kind: str,
    title: str,
    description: str,
    action_type: str,
    workline_id: str = "",
    evidence: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "opportunity_id": "opp_" + stable_hash(kind, title, description, workline_id)[:16],
        "kind": kind,
        "title": title,
        "description": description,
        "action_type": action_type,
        "workline_id": workline_id,
        "evidence": evidence or [],
    }


def evidence_ref(kind: str, ref_id: str, summary: str) -> dict[str, str]:
    return {
        "type": kind,
        "ref": ref_id,
        "summary": compact(summary, 180),
    }


def latest_snapshot_evidence(snapshots: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not snapshots:
        return []
    snapshot = snapshots[0]
    return [evidence_ref("snapshot", snapshot["snapshot_id"], snapshot.get("support_opportunity", ""))]


def find_workline_id(worklines: list[dict[str, Any]], title: str) -> str:
    for workline in worklines:
        if workline["title"] == title:
            return workline["workline_id"]
    return ""


def should_suggest_skill(context: dict[str, Any], worklines: list[dict[str, Any]]) -> bool:
    for snapshot in context["snapshots"]:
        summaries = (snapshot.get("sources", {}).get("session_summaries", {}) or {}).get("Codex", [])
        if len(summaries) >= 3:
            return True
        usage = str(snapshot.get("agent_usage", {}).get("Codex", ""))
        match = re.search(r"(\d+)", usage)
        if match and int(match.group(1)) >= 10:
            return True
    return any("workflow" in workline["title"].lower() for workline in worklines)


def next_step_for_workline(workline: dict[str, Any]) -> str:
    if workline["title"] == "Review pending memory candidates":
        return "Open the pending candidates and accept only durable, scoped, non-sensitive memories."
    if workline["title"] == "Resolve open memory conflicts":
        return "Inspect conflict reviews and decide which memory item should stay active."
    if workline["scope"].startswith("repo:"):
        return "Inspect the Git state, decide whether tests or a commit are needed, and record the outcome."
    if workline["scope"].startswith("project:"):
        return "Prepare a short scoped context brief, then continue the smallest unfinished task in this project."
    return "Review the evidence for this workline and choose the smallest useful next action."


def summarize_policy(opportunities: list[dict[str, Any]]) -> dict[str, Any]:
    by_risk: Counter[str] = Counter()
    by_status: Counter[str] = Counter()
    for opportunity in opportunities:
        policy = opportunity.get("policy", {})
        by_risk[str(policy.get("risk_level", "unknown"))] += 1
        by_status[str(policy.get("status", "unknown"))] += 1
    return {
        "by_risk": dict(sorted(by_risk.items())),
        "by_status": dict(sorted(by_status.items())),
        "opportunity_count": len(opportunities),
    }


def render_agenda_brief(
    worklines: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
    context: dict[str, Any],
    policy_summary: dict[str, Any],
) -> str:
    local_now = datetime.now(local_timezone())
    lines = [
        f"## Agenda {local_now.strftime('%H:%M')}",
        "",
        "### 当前主线",
    ]
    lines.extend(render_workline_lines(worklines))
    lines.extend(["", "### 证据"])
    lines.extend(render_evidence_lines(worklines, context))
    lines.extend(["", "### 建议下一步"])
    lines.extend(render_opportunity_lines(opportunities, include_risks={"L2"}))
    lines.extend(["", "### 自动维护"])
    lines.extend(render_opportunity_lines(opportunities, include_risks={"L0", "L1"}))
    lines.extend(["", "### 待确认动作"])
    lines.extend(render_opportunity_lines(opportunities, include_risks={"L3"}))
    lines.extend(["", "### 未知"])
    lines.extend(render_unknown_lines(worklines, context))
    lines.extend(["", "### Policy Summary"])
    lines.append(f"- risks: {policy_summary.get('by_risk', {})}")
    lines.append(f"- statuses: {policy_summary.get('by_status', {})}")
    return "\n".join(lines) + "\n"


def render_workline_lines(worklines: list[dict[str, Any]]) -> list[str]:
    if not worklines:
        return ["- No active worklines detected from current memSu state."]
    return [
        f"- {item['title']} ({item['scope']}, confidence {item['confidence']})"
        for item in worklines
    ]


def render_evidence_lines(worklines: list[dict[str, Any]], context: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for workline in worklines[:5]:
        for fact in workline.get("facts", [])[:2]:
            lines.append(f"- {fact}")
    if not lines:
        counts = input_counts(context)
        lines.append(f"- Input counts: {counts}")
    return lines


def render_opportunity_lines(
    opportunities: list[dict[str, Any]],
    *,
    include_risks: set[str],
) -> list[str]:
    lines = []
    for item in opportunities:
        policy = item.get("policy", {})
        if policy.get("risk_level") not in include_risks:
            continue
        suffix = f"{policy.get('risk_level')} / {policy.get('status')}"
        lines.append(f"- {item['title']} ({suffix}): {item['description']}")
    return lines or ["- None."]


def render_unknown_lines(worklines: list[dict[str, Any]], context: dict[str, Any]) -> list[str]:
    unknowns: list[str] = []
    for workline in worklines:
        unknowns.extend(workline.get("unknowns", []))
    if not unknowns and context["snapshots"]:
        unknowns.extend(context["snapshots"][0].get("unknown", []))
    return [f"- {item}" for item in trim_strings(unknowns, 6)] or ["- No material unknowns detected."]


def append_agenda_brief(brief: str) -> Path:
    local_now = datetime.now(local_timezone())
    advance_dir = memsu_home() / "advance"
    advance_dir.mkdir(parents=True, exist_ok=True)
    path = advance_dir / f"{local_now.strftime('%Y-%m-%d')}.md"
    if not path.exists():
        path.write_text("# memSu 推进简报\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n")
        handle.write(brief)
    return path


def record_agenda_event(
    store: MemSuStore,
    *,
    brief: str,
    brief_path: Path,
    worklines: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
    policy_summary: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    content = "\n".join(
        [
            f"workflow: {ADVANCE_WORKFLOW_NAME}",
            "status: completed",
            f"generated_at: {utc_now()}",
            "summary:",
            compact(brief, 1200),
        ]
    )
    return store.append_event(
        source_agent="advance",
        source_type="agenda",
        actor="system",
        event_type="workflow_result",
        content=content,
        content_ref=str(brief_path),
        sensitivity="normal",
        metadata={
            "workflow": ADVANCE_WORKFLOW_NAME,
            "status": "completed",
            "worklines": worklines,
            "opportunities": opportunities,
            "policy_summary": policy_summary,
            "input_counts": input_counts(context),
        },
    )


def input_counts(context: dict[str, Any]) -> dict[str, int]:
    return {
        "snapshots": len(context.get("snapshots", [])),
        "findings": len(context.get("findings", [])),
        "candidates": len(context.get("candidates", [])),
        "conflicts": len(context.get("conflicts", [])),
        "summaries": len(context.get("summaries", [])),
        "events": len(context.get("events", [])),
    }


def dedupe_worklines(worklines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for workline in worklines:
        key = workline["workline_id"]
        existing = result.get(key)
        if not existing or workline["priority"] > existing["priority"]:
            result[key] = workline
    return list(result.values())


def extract_cwd(summary: str) -> str:
    match = re.search(r"cwd=([^；;]+)", summary)
    if not match:
        return ""
    return compact(match.group(1).strip(), 60)


def trim_strings(items: list[str], limit: int) -> list[str]:
    return [compact(item, 220) for item in items if str(item).strip()][:limit]


def compact(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip()
    if len(text) <= limit:
        return text
    return text[:limit]
