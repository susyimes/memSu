from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .paths import default_observe_dir
from .store import MemSuStore


TZ_NAME = "Asia/Shanghai"
SENSITIVE_NAME_RE = re.compile(
    r"(^|[._-])("
    r"auth|oauth|credentials?|creds?|cookies?|passwords?|secrets?|tokens?|"
    r"api[_-]?keys?|private[_-]?keys?"
    r")([._-]|$)|"
    r"(^|[._-])keys?([._-]|$)|"
    r"(^|[._-])\.?env([._-]|$)|"
    r"(id_rsa|id_dsa|id_ecdsa|id_ed25519|\.pem$|\.p12$|\.pfx$)",
    re.IGNORECASE,
)


@dataclass
class SourceReport:
    name: str
    found: bool
    summary: str
    known: list[str]
    inferred: list[str]
    unknown: list[str]
    sources: list[str]
    recent_count: int = 0
    sensitive_skipped: int = 0


def run_observe(
    store: MemSuStore | None = None,
    *,
    evidence_home: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    store = store or MemSuStore()
    store.init()
    local_now = now or datetime.now(ZoneInfo(TZ_NAME))
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=ZoneInfo(TZ_NAME))
    evidence_root = Path(evidence_home).expanduser().resolve() if evidence_home else Path.home()

    reports = collect_source_reports(evidence_root, local_now)
    health = store.health()
    snapshot = compose_snapshot(reports, health, local_now)
    observe_path = daily_observe_path(local_now)
    append_snapshot_markdown(observe_path, snapshot)

    recorded = store.record_observation_snapshot(
        local_date=snapshot["local_date"],
        local_time=snapshot["local_time"],
        timezone_name=TZ_NAME,
        current_picture=snapshot["current_picture"],
        known=snapshot["known"],
        inferred=snapshot["inferred"],
        unknown=snapshot["unknown"],
        agent_usage=snapshot["agent_usage"],
        support_opportunity=snapshot["support_opportunity"],
        sources=snapshot["sources"],
        observe_path=str(observe_path),
        metadata={"evidence_home": str(evidence_root)},
    )
    recorded["observe_path"] = str(observe_path)
    return recorded


def observe_doctor(store: MemSuStore | None = None) -> dict[str, Any]:
    store = store or MemSuStore()
    store.init()
    observe_dir = default_observe_dir()
    observe_dir.mkdir(parents=True, exist_ok=True)
    health = store.health()
    return {
        "ok": True,
        "mode": "cli-first",
        "service_required": False,
        "observe_dir": str(observe_dir),
        "db_path": str(store.db_path),
        "schema_version": health["schema_version"],
    }


def collect_source_reports(evidence_home: Path, local_now: datetime) -> list[SourceReport]:
    cutoff = local_now - timedelta(hours=24)
    return [
        read_openclaw(evidence_home, cutoff),
        read_codex(evidence_home, cutoff),
        read_recent_tree(evidence_home / ".claude", "Claude", cutoff),
        read_recent_tree(evidence_home / ".gemini", "Gemini", cutoff),
        read_hermes(evidence_home, cutoff),
    ]


def read_openclaw(home: Path, cutoff: datetime) -> SourceReport:
    root = home / ".openclaw"
    if not root.exists():
        return missing_report("OpenClaw", root)

    workspaces = sorted(path for path in root.glob("workspace-*") if path.is_dir())
    recent_files: list[Path] = []
    sensitive_skipped = 0
    facts = [f"OpenClaw root exists with {len(workspaces)} workspace directories."]
    sources = [str(root)]
    for workspace in workspaces[:8]:
        for child in [workspace / "AGENT_LINKS.md", workspace / "MEMORY.md"]:
            if child.exists():
                sources.append(str(child))
        for subdir_name in ["observe", "memory"]:
            recent, skipped = recent_files_under(workspace / subdir_name, cutoff, limit=40)
            recent_files.extend(recent)
            sensitive_skipped += skipped

    runs_db = root / "tasks" / "runs.sqlite"
    if runs_db.exists():
        sources.append(str(runs_db))
        facts.append(openclaw_runs_fact(runs_db))

    recent_count = len(recent_files)
    facts.append(f"OpenClaw recent observe/memory metadata files: {recent_count}.")
    inferred = []
    if recent_count:
        inferred.append("OpenClaw appears to have recent workspace observation or memory activity.")
    unknown = []
    if not workspaces:
        unknown.append("No OpenClaw workspace-* directories were found.")
    summary = f"{len(workspaces)} workspaces; {recent_count} recent observe/memory files."
    return SourceReport(
        name="OpenClaw",
        found=True,
        summary=summary,
        known=facts[:6],
        inferred=inferred,
        unknown=unknown,
        sources=trim_sources(sources, root),
        recent_count=recent_count,
        sensitive_skipped=sensitive_skipped,
    )


def read_codex(home: Path, cutoff: datetime) -> SourceReport:
    root = home / ".codex"
    if not root.exists():
        return missing_report("Codex", root)

    sources: list[str] = []
    facts = ["Codex root exists."]
    recent_count = 0
    sensitive_skipped = 0
    for file_name in ["session_index.jsonl", "history.jsonl"]:
        path = root / file_name
        if path.exists():
            sources.append(str(path))
            facts.append(file_metadata_fact(path, f"Codex {file_name}"))

    for subdir_name in [
        "sessions",
        "archived_sessions",
        "memories/rollout_summaries",
        "automations",
    ]:
        recent, skipped = recent_files_under(root / subdir_name, cutoff, limit=80)
        recent_count += len(recent)
        sensitive_skipped += skipped
        sources.extend(str(path) for path in recent[:8])

    facts.append(f"Codex recent metadata/summary files in the last 24h: {recent_count}.")
    inferred = []
    if recent_count:
        inferred.append("Codex appears active recently based on session or memory metadata timestamps.")
    unknown = []
    if not (root / "session_index.jsonl").exists():
        unknown.append("Codex session_index.jsonl was not found.")
    summary = f"{recent_count} recent session/history/summary metadata files."
    return SourceReport(
        name="Codex",
        found=True,
        summary=summary,
        known=facts[:6],
        inferred=inferred,
        unknown=unknown,
        sources=trim_sources(sources, root),
        recent_count=recent_count,
        sensitive_skipped=sensitive_skipped,
    )


def read_recent_tree(root: Path, name: str, cutoff: datetime) -> SourceReport:
    if not root.exists():
        return missing_report(name, root)
    recent, skipped = recent_files_under(root, cutoff, limit=120)
    facts = [
        f"{name} root exists.",
        f"{name} recent non-sensitive files in the last 24h: {len(recent)}.",
    ]
    inferred = []
    if recent:
        inferred.append(f"{name} appears active recently based on file timestamps.")
    unknown = []
    if skipped:
        unknown.append(f"{name} has {skipped} sensitive-looking paths that were skipped.")
    return SourceReport(
        name=name,
        found=True,
        summary=f"{len(recent)} recent non-sensitive files.",
        known=facts,
        inferred=inferred,
        unknown=unknown,
        sources=trim_sources([str(path) for path in recent[:10]], root),
        recent_count=len(recent),
        sensitive_skipped=skipped,
    )


def read_hermes(home: Path, cutoff: datetime) -> SourceReport:
    root = resolve_hermes_root(home)
    if not root.exists():
        return missing_report("Hermes", root)
    recent, skipped = recent_files_under(root, cutoff, limit=80)
    skills_dir = root / "skills"
    skill_count = len([path for path in skills_dir.iterdir() if path.is_dir()]) if skills_dir.exists() else 0
    facts = [
        "Hermes root exists.",
        f"Hermes skill directories: {skill_count}.",
        f"Hermes recent non-sensitive files in the last 24h: {len(recent)}.",
    ]
    if (root / "config.yaml").exists():
        facts.append("Hermes config exists; content was not read.")
    inferred = []
    if recent:
        inferred.append("Hermes appears active recently based on local file timestamps.")
    unknown = []
    if skipped:
        unknown.append(f"Hermes has {skipped} sensitive-looking paths that were skipped.")
    return SourceReport(
        name="Hermes",
        found=True,
        summary=f"{len(recent)} recent files; {skill_count} skills.",
        known=facts,
        inferred=inferred,
        unknown=unknown,
        sources=trim_sources([str(path) for path in recent[:10]], root),
        recent_count=len(recent),
        sensitive_skipped=skipped,
    )


def resolve_hermes_root(home: Path) -> Path:
    env_home = os.environ.get("HERMES_HOME")
    candidates: list[Path] = []
    if env_home:
        candidates.append(Path(env_home).expanduser())
    candidates.extend(
        [
            home / ".hermes",
            home / "AppData" / "Local" / "hermes",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def compose_snapshot(
    reports: list[SourceReport],
    health: dict[str, Any],
    local_now: datetime,
) -> dict[str, Any]:
    found = [report for report in reports if report.found]
    active = [report for report in reports if report.recent_count > 0]
    current_picture = [
        f"memSu store has {health['event_count']} events, {health['active_memory_count']} active memories, and {health['pending_candidate_count']} pending candidates.",
        f"Detected {len(found)} configured source roots and {len(active)} sources with recent metadata.",
    ]
    if active:
        current_picture.append(
            "Recent activity metadata is strongest in "
            + ", ".join(report.name for report in active[:4])
            + "."
        )
    else:
        current_picture.append("No recent source activity metadata was detected in the last 24h.")
    current_picture.append("Observation remains CLI-first; no resident memSu service is required.")

    known: list[str] = []
    inferred: list[str] = []
    unknown: list[str] = []
    agent_usage: dict[str, str] = {}
    sources: dict[str, Any] = {
        "read_sources": {},
        "sensitive_skipped_count": sum(report.sensitive_skipped for report in reports),
    }
    for report in reports:
        agent_usage[report.name] = report.summary
        known.extend(report.known)
        inferred.extend(report.inferred)
        unknown.extend(report.unknown)
        sources["read_sources"][report.name] = report.sources

    if not unknown:
        unknown.append("No explicit incomplete observation gaps were detected.")
    if sources["sensitive_skipped_count"]:
        known.append(
            f"Skipped {sources['sensitive_skipped_count']} sensitive-looking paths by name."
        )

    support_opportunity = "None"
    pending = int(health.get("pending_candidate_count", 0))
    if pending:
        support_opportunity = f"Review {pending} pending memory candidates."
    elif active:
        support_opportunity = "Convert the strongest repeated recent workflow into an explicit memSu adapter or skill only if it recurs."

    return {
        "local_date": local_now.strftime("%Y-%m-%d"),
        "local_time": local_now.strftime("%H:%M"),
        "timezone": TZ_NAME,
        "current_picture": trim_list(current_picture, 6),
        "known": trim_list(known, 10),
        "inferred": trim_list(inferred, 6),
        "unknown": trim_list(unknown, 6),
        "agent_usage": agent_usage,
        "support_opportunity": support_opportunity,
        "sources": sources,
    }


def daily_observe_path(local_now: datetime) -> Path:
    return default_observe_dir() / f"{local_now.strftime('%Y-%m-%d')}.md"


def append_snapshot_markdown(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"# memSu Observe {snapshot['local_date']}\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n")
        handle.write(render_snapshot_markdown(snapshot))
        handle.write("\n")


def render_snapshot_markdown(snapshot: dict[str, Any]) -> str:
    lines = [f"## Snapshot {snapshot['local_time']}", ""]
    lines.extend(render_section("Current picture", snapshot["current_picture"]))
    lines.extend(render_section("Known", snapshot["known"]))
    lines.extend(render_section("Inferred", snapshot["inferred"]))
    lines.extend(render_section("Unknown", snapshot["unknown"]))
    usage = [f"{name}: {summary}" for name, summary in snapshot["agent_usage"].items()]
    lines.extend(render_section("Agent usage by source", usage))
    lines.extend(render_section("Support opportunity", [snapshot["support_opportunity"]]))
    return "\n".join(lines)


def render_section(title: str, items: list[str]) -> list[str]:
    lines = [f"### {title}"]
    if not items:
        lines.append("- None")
    else:
        lines.extend(f"- {sanitize_line(item)}" for item in items)
    lines.append("")
    return lines


def missing_report(name: str, root: Path) -> SourceReport:
    return SourceReport(
        name=name,
        found=False,
        summary="not found",
        known=[],
        inferred=[],
        unknown=[f"{name} root not found at {root.name}."],
        sources=[],
    )


def recent_files_under(root: Path, cutoff: datetime, *, limit: int) -> tuple[list[Path], int]:
    if not root.exists():
        return [], 0
    recent: list[Path] = []
    sensitive_skipped = 0
    checked = 0
    for path in safe_rglob(root):
        checked += 1
        if checked > 2000:
            break
        if not path.is_file():
            continue
        if is_sensitive_path(path):
            sensitive_skipped += 1
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=cutoff.tzinfo)
        except OSError:
            continue
        if mtime >= cutoff:
            recent.append(path)
    recent.sort(key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True)
    return recent[:limit], sensitive_skipped


def safe_rglob(root: Path):
    try:
        yield from root.rglob("*")
    except OSError:
        return


def is_sensitive_path(path: Path) -> bool:
    return any(SENSITIVE_NAME_RE.search(part) for part in path.parts)


def trim_sources(sources: list[str], root: Path) -> list[str]:
    result: list[str] = []
    for source in sources[:20]:
        path = Path(source)
        try:
            result.append(str(path.relative_to(root)))
        except ValueError:
            result.append(str(path))
    return result


def file_metadata_fact(path: Path, label: str) -> str:
    try:
        stat = path.stat()
    except OSError:
        return f"{label} exists but metadata could not be read."
    modified = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="minutes")
    return f"{label} exists; modified {modified}; {stat.st_size} bytes."


def openclaw_runs_fact(path: Path) -> str:
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            tables = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
            ).fetchone()[0]
        finally:
            conn.close()
    except sqlite3.Error:
        return "OpenClaw runs.sqlite exists but metadata could not be read."
    return f"OpenClaw runs.sqlite exists with {tables} tables."


def trim_list(items: list[str], limit: int) -> list[str]:
    return [sanitize_line(item) for item in items[:limit]]


def sanitize_line(value: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:limit]
