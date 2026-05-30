from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .paths import default_observe_dir
from .inspire import inspire_status
from .store import MemSuStore


TZ_NAME = "Asia/Shanghai"
TZ_FALLBACK = timezone(timedelta(hours=8), TZ_NAME)
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


def local_timezone():
    try:
        return ZoneInfo(TZ_NAME)
    except ZoneInfoNotFoundError:
        return TZ_FALLBACK


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
    session_summaries: list[str] | None = None


def run_observe(
    store: MemSuStore | None = None,
    *,
    evidence_home: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    store = store or MemSuStore()
    store.init()
    tz = local_timezone()
    local_now = now or datetime.now(tz)
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=tz)
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
        "inspire": inspire_status(),
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
    facts = [f"OpenClaw 根目录存在，发现 {len(workspaces)} 个 workspace 目录。"]
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
    session_summaries: list[str] = []
    facts.append(f"OpenClaw 最近 24 小时 observe/memory 元数据文件数：{recent_count}。")
    inferred = []
    if recent_count:
        inferred.append("OpenClaw 看起来最近有 workspace observe 或 memory 活动。")
    unknown = []
    if not workspaces:
        unknown.append("未发现 OpenClaw workspace-* 目录。")
    summary = f"{len(workspaces)} 个 workspace；最近 24 小时 {recent_count} 个 observe/memory 文件。"
    return SourceReport(
        name="OpenClaw",
        found=True,
        summary=summary,
        known=facts[:8],
        inferred=inferred,
        unknown=unknown,
        sources=trim_sources(sources, root),
        recent_count=recent_count,
        sensitive_skipped=sensitive_skipped,
        session_summaries=session_summaries,
    )


def read_codex(home: Path, cutoff: datetime) -> SourceReport:
    root = home / ".codex"
    if not root.exists():
        return missing_report("Codex", root)

    sources: list[str] = []
    facts = ["Codex 根目录存在。"]
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

    facts.append(f"Codex 最近 24 小时 metadata/summary 文件数：{recent_count}。")
    session_summaries = collect_codex_session_summaries(root, cutoff, limit=6)
    if session_summaries:
        facts.append(f"Codex 已提取 {len(session_summaries)} 条最近会话摘要。")
    inferred = []
    if recent_count:
        inferred.append("基于 session 或 memory 元数据时间戳，Codex 最近看起来活跃。")
    unknown = []
    if not (root / "session_index.jsonl").exists():
        unknown.append("未发现 Codex session_index.jsonl。")
    summary = f"最近 24 小时 {recent_count} 个 session/history/summary 元数据文件。"
    return SourceReport(
        name="Codex",
        found=True,
        summary=summary,
        known=facts[:8],
        inferred=inferred,
        unknown=unknown,
        sources=trim_sources(sources, root),
        recent_count=recent_count,
        sensitive_skipped=sensitive_skipped,
        session_summaries=session_summaries,
    )


def read_recent_tree(root: Path, name: str, cutoff: datetime) -> SourceReport:
    if not root.exists():
        return missing_report(name, root)
    recent, skipped = recent_files_under(root, cutoff, limit=120)
    session_summaries = collect_gemini_session_summaries(root, cutoff, limit=5) if name == "Gemini" else []
    facts = [
        f"{name} 根目录存在。",
        f"{name} 最近 24 小时非敏感文件数：{len(recent)}。",
    ]
    inferred = []
    if recent:
        inferred.append(f"基于文件时间戳，{name} 最近看起来活跃。")
    if session_summaries:
        inferred.append(f"{name} 最近会话中可提取到 {len(session_summaries)} 条摘要。")
    unknown = []
    if skipped:
        unknown.append(f"{name} 有 {skipped} 个看起来敏感的路径已跳过。")
    return SourceReport(
        name=name,
        found=True,
        summary=f"最近 24 小时 {len(recent)} 个非敏感文件。",
        known=facts,
        inferred=inferred,
        unknown=unknown,
        sources=trim_sources([str(path) for path in recent[:10]], root),
        recent_count=len(recent),
        sensitive_skipped=skipped,
        session_summaries=session_summaries,
    )


def read_hermes(home: Path, cutoff: datetime) -> SourceReport:
    root = resolve_hermes_root(home)
    if not root.exists():
        return missing_report("Hermes", root)
    recent, skipped = recent_files_under(root, cutoff, limit=80)
    skills_dir = root / "skills"
    skill_count = len([path for path in skills_dir.iterdir() if path.is_dir()]) if skills_dir.exists() else 0
    facts = [
        "Hermes 根目录存在。",
        f"Hermes skill 目录数：{skill_count}。",
        f"Hermes 最近 24 小时非敏感文件数：{len(recent)}。",
    ]
    if (root / "config.yaml").exists():
        facts.append("Hermes config 存在；未读取内容。")
    inferred = []
    if recent:
        inferred.append("基于本地文件时间戳，Hermes 最近看起来活跃。")
    unknown = []
    if skipped:
        unknown.append(f"Hermes 有 {skipped} 个看起来敏感的路径已跳过。")
    return SourceReport(
        name="Hermes",
        found=True,
        summary=f"最近 24 小时 {len(recent)} 个文件；{skill_count} 个 skills。",
        known=facts,
        inferred=inferred,
        unknown=unknown,
        sources=trim_sources([str(path) for path in recent[:10]], root),
        recent_count=len(recent),
        sensitive_skipped=skipped,
    )



def collect_codex_session_summaries(root: Path, cutoff: datetime, *, limit: int) -> list[str]:
    candidates: list[Path] = []
    for subdir_name in ["sessions", "archived_sessions"]:
        recent, _ = recent_files_under(root / subdir_name, cutoff, limit=40)
        candidates.extend(path for path in recent if path.suffix.lower() == ".jsonl")
    summary_dir = root / "memories" / "rollout_summaries"
    recent_summary_files, _ = recent_files_under(summary_dir, cutoff, limit=20)
    candidates.extend(path for path in recent_summary_files if path.suffix.lower() in {".md", ".txt"})
    candidates = sorted(set(candidates), key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True)

    summaries: list[str] = []
    for path in candidates:
        if is_sensitive_path(path):
            continue
        summary = summarize_codex_file(path)
        if summary:
            summaries.append(summary)
        if len(summaries) >= limit:
            break
    return summaries


def summarize_codex_file(path: Path) -> str:
    if path.suffix.lower() == ".jsonl":
        return summarize_codex_jsonl(path)
    return summarize_summary_markdown(path, "rollout summary")


def summarize_codex_jsonl(path: Path) -> str:
    cwd = ""
    user_messages: list[str] = []
    assistant_messages: list[str] = []
    try:
        handle = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return ""
    with handle:
        for index, line in enumerate(handle):
            if index > 5000:
                break
            try:
                payload = json.loads(line).get("payload") or {}
            except (json.JSONDecodeError, AttributeError):
                continue
            if not isinstance(payload, dict):
                continue
            if not cwd and payload.get("cwd"):
                cwd = str(payload.get("cwd"))
            role = str(payload.get("role") or "")
            if role not in {"user", "assistant"}:
                continue
            text = extract_payload_text(payload)
            if not is_human_signal(text):
                continue
            if role == "user":
                user_messages.append(text)
            else:
                assistant_messages.append(text)
    if not user_messages and not assistant_messages:
        return ""
    label = session_label_from_path(path)
    parts = [label]
    if cwd:
        parts.append(f"cwd={Path(cwd).name}")
    if user_messages:
        parts.append("用户：" + compact_text(user_messages[-1], 120))
    if assistant_messages:
        parts.append("结果：" + compact_text(assistant_messages[-1], 160))
    return "；".join(parts)


def collect_gemini_session_summaries(root: Path, cutoff: datetime, *, limit: int) -> list[str]:
    summaries: list[str] = []
    logs_path = root / "tmp" / "susyi" / "logs.json"
    if logs_path.exists() and not is_sensitive_path(logs_path):
        summaries.extend(summarize_gemini_logs(logs_path, cutoff, limit=limit))
    recent, _ = recent_files_under(root / "antigravity", cutoff, limit=80)
    for path in recent:
        if len(summaries) >= limit:
            break
        if path.name.endswith(".metadata.json"):
            summary = summarize_gemini_artifact_metadata(path)
            if summary:
                summaries.append(summary)
    return summaries[:limit]


def summarize_gemini_logs(path: Path, cutoff: datetime, *, limit: int) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    sessions: dict[str, list[dict[str, Any]]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        session_id = str(item.get("sessionId") or "unknown")
        sessions.setdefault(session_id, []).append(item)
    results: list[str] = []
    for session_id, items in sorted(sessions.items(), key=lambda pair: str(pair[1][-1].get("timestamp", "")), reverse=True):
        texts = [str(item.get("message") or "") for item in items if item.get("message")]
        if not texts:
            continue
        results.append(f"session {session_id[:8]}；最近消息：{compact_text(texts[-1], 180)}")
        if len(results) >= limit:
            break
    return results


def summarize_gemini_artifact_metadata(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return ""
    summary = str(payload.get("summary") or "") if isinstance(payload, dict) else ""
    if not summary:
        return ""
    return f"artifact {path.stem.replace('.md.metadata', '')}；摘要：{compact_text(summary, 180)}"


def summarize_summary_markdown(path: Path, label: str) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = [line.strip("# -\t ") for line in text.splitlines() if line.strip()]
    signal = next((line for line in lines if not line.lower().startswith(("updated_at:", "cwd:", "rollout_path:"))), "")
    if not signal:
        signal = path.stem
    return f"{label} {path.stem}；{compact_text(signal, 180)}"


def extract_payload_text(payload: dict[str, Any]) -> str:
    content = payload.get("content") or payload.get("message") or payload.get("text") or ""
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        content = " ".join(parts)
    return str(content)


def is_human_signal(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 8:
        return False
    lowered = stripped.lower()
    noisy_prefixes = (
        "<permissions instructions>",
        "<app-context>",
        "# agents.md instructions",
        "# coding agent guidelines",
    )
    return not any(lowered.startswith(prefix) for prefix in noisy_prefixes)


def session_label_from_path(path: Path) -> str:
    stem = path.stem
    match = re.search(r"rollout-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})", stem)
    if match:
        raw = match.group(1)
        date_part, time_part = raw.split("T", 1)
        return f"{date_part} {time_part.replace('-', ':')}"
    return stem[:32]


def compact_text(value: str, limit: int) -> str:
    return sanitize_line(value, limit=limit)

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
        f"memSu store 当前有 {health['event_count']} 条 events、{health['active_memory_count']} 条 active memories、{health['pending_candidate_count']} 条 pending candidates。",
        f"检测到 {len(found)} 个已配置来源根目录，其中 {len(active)} 个来源有最近元数据。",
    ]
    if active:
        current_picture.append(
            "最近活动元数据最明显的来源是 "
            + ", ".join(report.name for report in active[:4])
            + "。"
        )
    else:
        current_picture.append("最近 24 小时未检测到来源活动元数据。")
    current_picture.append("观察模式仍是 CLI-first；不需要 memSu 常驻服务。")

    known: list[str] = []
    inferred: list[str] = []
    unknown: list[str] = []
    agent_usage: dict[str, str] = {}
    session_summaries: list[str] = []
    sources: dict[str, Any] = {
        "read_sources": {},
        "session_summaries": {},
        "sensitive_skipped_count": sum(report.sensitive_skipped for report in reports),
    }
    for report in reports:
        agent_usage[report.name] = report.summary
        known.extend(report.known)
        inferred.extend(report.inferred)
        unknown.extend(report.unknown)
        sources["read_sources"][report.name] = report.sources
        if report.session_summaries:
            source_summaries = trim_list(report.session_summaries, 8)
            sources["session_summaries"][report.name] = source_summaries
            session_summaries.extend(f"{report.name}: {item}" for item in source_summaries)

    if session_summaries:
        current_picture.append(f"已提取 {len(session_summaries)} 条最近 agent 会话摘要；不再只记录会话数量。")
    if not unknown:
        unknown.append("未检测到明确的观察缺口。")
    if sources["sensitive_skipped_count"]:
        known.append(
            f"按路径名跳过 {sources['sensitive_skipped_count']} 个看起来敏感的路径。"
        )

    support_opportunity = "无"
    pending = int(health.get("pending_candidate_count", 0))
    if pending:
        support_opportunity = f"请 review {pending} 条 pending memory candidates。"
    elif active:
        support_opportunity = "如果最明显的重复近期工作流继续出现，可考虑将其沉淀为明确的 memSu adapter 或 Hermes skill。"

    return {
        "local_date": local_now.strftime("%Y-%m-%d"),
        "local_time": local_now.strftime("%H:%M"),
        "timezone": TZ_NAME,
        "current_picture": trim_list(current_picture, 6),
        "known": trim_list(known, 10),
        "inferred": trim_list(inferred, 6),
        "unknown": trim_list(unknown, 6),
        "session_summaries": trim_list(session_summaries, 10),
        "agent_usage": agent_usage,
        "support_opportunity": support_opportunity,
        "sources": sources,
    }


def daily_observe_path(local_now: datetime) -> Path:
    return default_observe_dir() / f"{local_now.strftime('%Y-%m-%d')}.md"


def append_snapshot_markdown(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"# memSu 观察 {snapshot['local_date']}\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n")
        handle.write(render_snapshot_markdown(snapshot))
        handle.write("\n")


def render_snapshot_markdown(snapshot: dict[str, Any]) -> str:
    lines = [f"## 快照 {snapshot['local_time']}", ""]
    lines.extend(render_section("当前图景", snapshot["current_picture"]))
    lines.extend(render_section("已确认", snapshot["known"]))
    lines.extend(render_section("推断", snapshot["inferred"]))
    lines.extend(render_section("未知", snapshot["unknown"]))
    lines.extend(render_section("最近 Agent 会话摘要", snapshot.get("session_summaries", [])))
    usage = [f"{name}: {summary}" for name, summary in snapshot["agent_usage"].items()]
    lines.extend(render_section("各来源 Agent 使用情况", usage))
    lines.extend(render_section("支持建议", [snapshot["support_opportunity"]]))
    return "\n".join(lines)


def render_section(title: str, items: list[str]) -> list[str]:
    lines = [f"### {title}"]
    if not items:
        lines.append("- 无")
    else:
        lines.extend(f"- {sanitize_line(item)}" for item in items)
    lines.append("")
    return lines


def missing_report(name: str, root: Path) -> SourceReport:
    return SourceReport(
        name=name,
        found=False,
        summary="未发现",
        known=[],
        inferred=[],
        unknown=[f"未在 {root.name} 发现 {name} 根目录。"],
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
        return f"{label} 存在，但无法读取元数据。"
    modified = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="minutes")
    return f"{label} 存在；修改时间 {modified}；大小 {stat.st_size} 字节。"


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
        return "OpenClaw runs.sqlite 存在，但无法读取元数据。"
    return f"OpenClaw runs.sqlite 存在，包含 {tables} 张表。"


def trim_list(items: list[str], limit: int) -> list[str]:
    return [sanitize_line(item) for item in items[:limit]]


def sanitize_line(value: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:limit]
