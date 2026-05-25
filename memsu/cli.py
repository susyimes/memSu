from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .adapters import (
    ingest_codex_transcript,
    record_shell_command,
    record_workflow_result,
    snapshot_git_repo,
)
from .paths import default_db_path, default_policy_path, memsu_home
from .server import run_server
from .store import EVENT_TYPES, MEMORY_TYPES, MemSuStore


DEFAULT_POLICY = """# memSu default policy
risk_levels:
  L0: automatic_internal_maintenance
  L1: automatic_passive_recall
  L2: proactive_suggestions
  L3: user_confirmation_required
  L4: forbidden_or_restricted

defaults:
  proactive_external_actions: false
  cross_agent_sensitive_sharing: false
  hard_delete_without_confirmation: false
  suggestion_cooldown_seconds: 300
  quiet_hours_active: false
"""


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def ensure_policy_file() -> None:
    path = default_policy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(DEFAULT_POLICY, encoding="utf-8")


def cmd_init(args: argparse.Namespace) -> int:
    store = MemSuStore(args.db)
    store.init()
    ensure_policy_file()
    print_json({"ok": True, "db_path": str(store.db_path), "home": str(memsu_home())})
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    store = MemSuStore(args.db)
    store.init()
    event = store.append_event(
        source_agent="doctor",
        source_type="self_test",
        actor="system",
        event_type="workflow_result",
        content="memSu doctor event append smoke test",
        metadata={"doctor": True},
    )
    memory = store.retain_memory(
        "memSu doctor recall smoke test memory",
        type="note",
        scope="doctor",
        source_event_ids=[event["event_id"]],
    )
    recall = store.recall("doctor recall", scope="doctor", limit=3)
    health = store.health()
    ok = bool(recall)
    print_json(
        {
            "ok": ok,
            "health": health,
            "event": event,
            "memory": memory,
            "recall_count": len(recall),
            "policy_path": str(default_policy_path()),
        }
    )
    return 0 if ok else 1


def cmd_event_append(args: argparse.Namespace) -> int:
    metadata = json.loads(args.metadata) if args.metadata else {}
    artifact_refs = json.loads(args.artifact_refs) if args.artifact_refs else []
    result = MemSuStore(args.db).append_event(
        source_agent=args.source_agent,
        source_type=args.source_type,
        actor=args.actor,
        event_type=args.event_type,
        content=args.content,
        workspace=args.workspace,
        repo=args.repo,
        cwd=args.cwd,
        thread_id=args.thread_id,
        task_id=args.task_id,
        content_ref=args.content_ref,
        artifact_refs=artifact_refs,
        sensitivity=args.sensitivity,
        metadata=metadata,
    )
    print_json(result)
    return 0


def cmd_event_list(args: argparse.Namespace) -> int:
    print_json({"events": MemSuStore(args.db).list_events(limit=args.limit)})
    return 0


def cmd_adapter_shell(args: argparse.Namespace) -> int:
    result = record_shell_command(
        MemSuStore(args.db),
        command=args.command,
        cwd=args.cwd,
        exit_code=args.exit_code,
        stdout=args.stdout,
        stderr=args.stderr,
        duration_ms=args.duration_ms,
        workspace=args.workspace,
        repo=args.repo,
        task_id=args.task_id,
        sensitivity=args.sensitivity,
    )
    print_json(result)
    return 0


def cmd_adapter_git(args: argparse.Namespace) -> int:
    result = snapshot_git_repo(
        MemSuStore(args.db),
        repo_path=args.repo_path,
        workspace=args.workspace,
        sensitivity=args.sensitivity,
    )
    print_json(result)
    return 0


def cmd_adapter_codex(args: argparse.Namespace) -> int:
    result = ingest_codex_transcript(
        MemSuStore(args.db),
        path=args.path,
        workspace=args.workspace,
        repo=args.repo,
        thread_id=args.thread_id,
        sensitivity=args.sensitivity,
    )
    print_json(result)
    return 0


def cmd_adapter_workflow(args: argparse.Namespace) -> int:
    artifact_refs = json.loads(args.artifact_refs) if args.artifact_refs else []
    result = record_workflow_result(
        MemSuStore(args.db),
        name=args.name,
        status=args.status,
        summary=args.summary,
        workspace=args.workspace,
        repo=args.repo,
        cwd=args.cwd,
        task_id=args.task_id,
        artifact_refs=artifact_refs,
        sensitivity=args.sensitivity,
    )
    print_json(result)
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    result = MemSuStore(args.db).extract_candidates(
        event_id=args.event_id,
        limit=args.limit,
        auto_accept=args.auto_accept,
    )
    print_json(result)
    return 0


def cmd_candidate_list(args: argparse.Namespace) -> int:
    result = MemSuStore(args.db).list_candidates(
        status=args.status,
        scope=args.scope,
        limit=args.limit,
    )
    print_json({"candidates": result})
    return 0


def cmd_candidate_accept(args: argparse.Namespace) -> int:
    result = MemSuStore(args.db).accept_candidate(args.candidate_id)
    print_json(result)
    return 0


def cmd_candidate_reject(args: argparse.Namespace) -> int:
    result = MemSuStore(args.db).reject_candidate(
        args.candidate_id,
        reason=args.reason,
    )
    print_json(result)
    return 0


def cmd_policy_evaluate(args: argparse.Namespace) -> int:
    metadata = json.loads(args.metadata) if args.metadata else {}
    result = MemSuStore(args.db).evaluate_policy(
        action_type=args.action_type,
        description=args.description,
        sensitivity=args.sensitivity,
        metadata=metadata,
    )
    print_json(result)
    return 0


def cmd_policy_proposals(args: argparse.Namespace) -> int:
    result = MemSuStore(args.db).list_action_proposals(
        status=args.status,
        limit=args.limit,
    )
    print_json({"proposals": result})
    return 0


def cmd_policy_decide(args: argparse.Namespace) -> int:
    result = MemSuStore(args.db).decide_action_proposal(
        args.proposal_id,
        decision=args.decision,
        reason=args.reason,
    )
    print_json(result)
    return 0


def cmd_policy_events(args: argparse.Namespace) -> int:
    result = MemSuStore(args.db).list_policy_events(limit=args.limit)
    print_json({"events": result})
    return 0


def cmd_curator_run(args: argparse.Namespace) -> int:
    result = MemSuStore(args.db).run_curator(
        stale_days=args.stale_days,
        stale_salience_threshold=args.stale_salience_threshold,
    )
    print_json(result)
    return 0


def cmd_curator_summaries(args: argparse.Namespace) -> int:
    result = MemSuStore(args.db).list_memory_summaries(
        scope=args.scope,
        kind=args.kind,
        limit=args.limit,
    )
    print_json({"summaries": result})
    return 0


def cmd_curator_conflicts(args: argparse.Namespace) -> int:
    result = MemSuStore(args.db).list_conflict_reviews(
        status=args.status,
        limit=args.limit,
    )
    print_json({"conflicts": result})
    return 0


def cmd_curator_runs(args: argparse.Namespace) -> int:
    result = MemSuStore(args.db).list_curator_runs(limit=args.limit)
    print_json({"runs": result})
    return 0


def cmd_retain(args: argparse.Namespace) -> int:
    metadata = json.loads(args.metadata) if args.metadata else {}
    result = MemSuStore(args.db).retain_memory(
        args.content,
        type=args.type,
        scope=args.scope,
        confidence=args.confidence,
        salience=args.salience,
        source_event_ids=args.source_event_id or [],
        metadata=metadata,
    )
    print_json(result)
    return 0


def cmd_recall(args: argparse.Namespace) -> int:
    result = MemSuStore(args.db).recall(args.query, scope=args.scope, limit=args.limit)
    print_json({"memories": result})
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    result = MemSuStore(args.db).audit(
        scope=args.scope, status=args.status, limit=args.limit
    )
    print_json({"memories": result})
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    result = MemSuStore(args.db).forget(args.item_id, reason=args.reason)
    print_json(result)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    run_server(host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memsu", description="memSu local memory supervisor")
    parser.add_argument("--db", default=None, help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize local memSu storage")
    p_init.set_defaults(func=cmd_init)

    p_doctor = sub.add_parser("doctor", help="Run a local smoke test")
    p_doctor.set_defaults(func=cmd_doctor)

    p_serve = sub.add_parser("serve", help="Run the local HTTP service")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.set_defaults(func=cmd_serve)

    p_event = sub.add_parser("event", help="Event log operations")
    event_sub = p_event.add_subparsers(dest="event_command", required=True)
    p_event_append = event_sub.add_parser("append", help="Append an observation event")
    p_event_append.add_argument("--source-agent", required=True)
    p_event_append.add_argument("--source-type", default="manual")
    p_event_append.add_argument("--actor", default="user")
    p_event_append.add_argument("--event-type", choices=sorted(EVENT_TYPES), default="workflow_result")
    p_event_append.add_argument("--content", default="")
    p_event_append.add_argument("--workspace", default="")
    p_event_append.add_argument("--repo", default="")
    p_event_append.add_argument("--cwd", default="")
    p_event_append.add_argument("--thread-id", default="")
    p_event_append.add_argument("--task-id", default="")
    p_event_append.add_argument("--content-ref", default="")
    p_event_append.add_argument("--artifact-refs", default="")
    p_event_append.add_argument("--sensitivity", default="normal")
    p_event_append.add_argument("--metadata", default="")
    p_event_append.set_defaults(func=cmd_event_append)

    p_event_list = event_sub.add_parser("list", help="List recent events")
    p_event_list.add_argument("--limit", type=int, default=20)
    p_event_list.set_defaults(func=cmd_event_list)

    p_adapter = sub.add_parser("adapter", help="Record structured observations from local tools")
    adapter_sub = p_adapter.add_subparsers(dest="adapter_command", required=True)

    p_adapter_shell = adapter_sub.add_parser("shell", help="Record a shell command result")
    p_adapter_shell.add_argument("--command", required=True)
    p_adapter_shell.add_argument("--cwd", default="")
    p_adapter_shell.add_argument("--exit-code", type=int, default=0)
    p_adapter_shell.add_argument("--stdout", default="")
    p_adapter_shell.add_argument("--stderr", default="")
    p_adapter_shell.add_argument("--duration-ms", type=int, default=None)
    p_adapter_shell.add_argument("--workspace", default="")
    p_adapter_shell.add_argument("--repo", default="")
    p_adapter_shell.add_argument("--task-id", default="")
    p_adapter_shell.add_argument("--sensitivity", default="normal")
    p_adapter_shell.set_defaults(func=cmd_adapter_shell)

    p_adapter_git = adapter_sub.add_parser("git", help="Record a git repository snapshot")
    p_adapter_git.add_argument("--repo-path", default=".")
    p_adapter_git.add_argument("--workspace", default="")
    p_adapter_git.add_argument("--sensitivity", default="normal")
    p_adapter_git.set_defaults(func=cmd_adapter_git)

    p_adapter_codex = adapter_sub.add_parser("codex", help="Ingest a Codex transcript file")
    p_adapter_codex.add_argument("path")
    p_adapter_codex.add_argument("--workspace", default="")
    p_adapter_codex.add_argument("--repo", default="")
    p_adapter_codex.add_argument("--thread-id", default="")
    p_adapter_codex.add_argument("--sensitivity", default="normal")
    p_adapter_codex.set_defaults(func=cmd_adapter_codex)

    p_adapter_workflow = adapter_sub.add_parser("workflow", help="Record a workflow result")
    p_adapter_workflow.add_argument("--name", required=True)
    p_adapter_workflow.add_argument("--status", required=True)
    p_adapter_workflow.add_argument("--summary", required=True)
    p_adapter_workflow.add_argument("--workspace", default="")
    p_adapter_workflow.add_argument("--repo", default="")
    p_adapter_workflow.add_argument("--cwd", default="")
    p_adapter_workflow.add_argument("--task-id", default="")
    p_adapter_workflow.add_argument("--artifact-refs", default="")
    p_adapter_workflow.add_argument("--sensitivity", default="normal")
    p_adapter_workflow.set_defaults(func=cmd_adapter_workflow)

    p_extract = sub.add_parser("extract", help="Extract pending memory candidates from events")
    p_extract.add_argument("--event-id", default="")
    p_extract.add_argument("--limit", type=int, default=50)
    p_extract.add_argument("--auto-accept", action="store_true")
    p_extract.set_defaults(func=cmd_extract)

    p_candidate = sub.add_parser("candidate", help="Memory candidate operations")
    candidate_sub = p_candidate.add_subparsers(dest="candidate_command", required=True)

    p_candidate_list = candidate_sub.add_parser("list", help="List memory candidates")
    p_candidate_list.add_argument("--status", default="pending")
    p_candidate_list.add_argument("--scope", default="")
    p_candidate_list.add_argument("--limit", type=int, default=50)
    p_candidate_list.set_defaults(func=cmd_candidate_list)

    p_candidate_accept = candidate_sub.add_parser("accept", help="Accept a memory candidate")
    p_candidate_accept.add_argument("candidate_id")
    p_candidate_accept.set_defaults(func=cmd_candidate_accept)

    p_candidate_reject = candidate_sub.add_parser("reject", help="Reject a memory candidate")
    p_candidate_reject.add_argument("candidate_id")
    p_candidate_reject.add_argument("--reason", default="")
    p_candidate_reject.set_defaults(func=cmd_candidate_reject)

    p_policy = sub.add_parser("policy", help="Evaluate and review proactive action policy")
    policy_sub = p_policy.add_subparsers(dest="policy_command", required=True)

    p_policy_eval = policy_sub.add_parser("evaluate", help="Evaluate a proposed action")
    p_policy_eval.add_argument("--action-type", required=True)
    p_policy_eval.add_argument("--description", default="")
    p_policy_eval.add_argument("--sensitivity", default="normal")
    p_policy_eval.add_argument("--metadata", default="")
    p_policy_eval.set_defaults(func=cmd_policy_evaluate)

    p_policy_proposals = policy_sub.add_parser("proposals", help="List action proposals")
    p_policy_proposals.add_argument("--status", default="")
    p_policy_proposals.add_argument("--limit", type=int, default=50)
    p_policy_proposals.set_defaults(func=cmd_policy_proposals)

    p_policy_decide = policy_sub.add_parser("decide", help="Approve or reject an action proposal")
    p_policy_decide.add_argument("proposal_id")
    p_policy_decide.add_argument("--decision", required=True, choices=["approve", "reject"])
    p_policy_decide.add_argument("--reason", default="")
    p_policy_decide.set_defaults(func=cmd_policy_decide)

    p_policy_events = policy_sub.add_parser("events", help="List policy events")
    p_policy_events.add_argument("--limit", type=int, default=50)
    p_policy_events.set_defaults(func=cmd_policy_events)

    p_curator = sub.add_parser("curator", help="Run and inspect memory curator jobs")
    curator_sub = p_curator.add_subparsers(dest="curator_command", required=True)

    p_curator_run = curator_sub.add_parser("run", help="Run memory curation")
    p_curator_run.add_argument("--stale-days", type=int, default=90)
    p_curator_run.add_argument("--stale-salience-threshold", type=float, default=0.3)
    p_curator_run.set_defaults(func=cmd_curator_run)

    p_curator_summaries = curator_sub.add_parser("summaries", help="List memory summaries")
    p_curator_summaries.add_argument("--scope", default="")
    p_curator_summaries.add_argument("--kind", default="")
    p_curator_summaries.add_argument("--limit", type=int, default=50)
    p_curator_summaries.set_defaults(func=cmd_curator_summaries)

    p_curator_conflicts = curator_sub.add_parser("conflicts", help="List conflict reviews")
    p_curator_conflicts.add_argument("--status", default="open")
    p_curator_conflicts.add_argument("--limit", type=int, default=50)
    p_curator_conflicts.set_defaults(func=cmd_curator_conflicts)

    p_curator_runs = curator_sub.add_parser("runs", help="List curator runs")
    p_curator_runs.add_argument("--limit", type=int, default=20)
    p_curator_runs.set_defaults(func=cmd_curator_runs)

    p_retain = sub.add_parser("retain", help="Retain a memory item")
    p_retain.add_argument("content")
    p_retain.add_argument("--type", choices=sorted(MEMORY_TYPES), default="note")
    p_retain.add_argument("--scope", default="global_user")
    p_retain.add_argument("--confidence", type=float, default=0.7)
    p_retain.add_argument("--salience", type=float, default=0.5)
    p_retain.add_argument("--source-event-id", action="append")
    p_retain.add_argument("--metadata", default="")
    p_retain.set_defaults(func=cmd_retain)

    p_recall = sub.add_parser("recall", help="Recall memories by keyword and scope")
    p_recall.add_argument("query")
    p_recall.add_argument("--scope", default="")
    p_recall.add_argument("--limit", type=int, default=5)
    p_recall.set_defaults(func=cmd_recall)

    p_audit = sub.add_parser("audit", help="List memory items")
    p_audit.add_argument("--scope", default="")
    p_audit.add_argument("--status", default="active")
    p_audit.add_argument("--limit", type=int, default=50)
    p_audit.set_defaults(func=cmd_audit)

    p_forget = sub.add_parser("forget", help="Archive a memory item")
    p_forget.add_argument("item_id")
    p_forget.add_argument("--reason", default="")
    p_forget.set_defaults(func=cmd_forget)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"memsu: {exc}", file=sys.stderr)
        return 1
