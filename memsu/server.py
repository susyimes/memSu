from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .adapters import (
    ingest_codex_transcript,
    record_shell_command,
    record_workflow_result,
    snapshot_git_repo,
)
from .store import MemSuStore


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def write_json(handler: BaseHTTPRequestHandler, status: int, payload: dict | list) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class MemSuHandler(BaseHTTPRequestHandler):
    store = MemSuStore()

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            write_json(self, 200, self.store.health())
            return
        if parsed.path == "/audit":
            params = parse_qs(parsed.query)
            result = self.store.audit(
                scope=params.get("scope", [""])[0],
                status=params.get("status", ["active"])[0],
                limit=int(params.get("limit", ["50"])[0]),
            )
            write_json(self, 200, {"memories": result})
            return
        if parsed.path == "/candidates":
            params = parse_qs(parsed.query)
            result = self.store.list_candidates(
                status=params.get("status", ["pending"])[0],
                scope=params.get("scope", [""])[0],
                limit=int(params.get("limit", ["50"])[0]),
            )
            write_json(self, 200, {"candidates": result})
            return
        if parsed.path == "/policy/proposals":
            params = parse_qs(parsed.query)
            result = self.store.list_action_proposals(
                status=params.get("status", [""])[0],
                limit=int(params.get("limit", ["50"])[0]),
            )
            write_json(self, 200, {"proposals": result})
            return
        if parsed.path == "/policy/events":
            params = parse_qs(parsed.query)
            result = self.store.list_policy_events(
                limit=int(params.get("limit", ["50"])[0]),
            )
            write_json(self, 200, {"events": result})
            return
        if parsed.path == "/curator/summaries":
            params = parse_qs(parsed.query)
            result = self.store.list_memory_summaries(
                scope=params.get("scope", [""])[0],
                kind=params.get("kind", [""])[0],
                limit=int(params.get("limit", ["50"])[0]),
            )
            write_json(self, 200, {"summaries": result})
            return
        if parsed.path == "/curator/conflicts":
            params = parse_qs(parsed.query)
            result = self.store.list_conflict_reviews(
                status=params.get("status", ["open"])[0],
                limit=int(params.get("limit", ["50"])[0]),
            )
            write_json(self, 200, {"conflicts": result})
            return
        if parsed.path == "/curator/runs":
            params = parse_qs(parsed.query)
            result = self.store.list_curator_runs(
                limit=int(params.get("limit", ["20"])[0]),
            )
            write_json(self, 200, {"runs": result})
            return
        write_json(self, 404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        try:
            body = read_json(self)
            if self.path == "/events":
                result = self.store.append_event(**body)
                write_json(self, 200, result)
                return
            if self.path == "/adapters/shell":
                result = record_shell_command(self.store, **body)
                write_json(self, 200, result)
                return
            if self.path == "/adapters/git":
                result = snapshot_git_repo(self.store, **body)
                write_json(self, 200, result)
                return
            if self.path == "/adapters/codex":
                result = ingest_codex_transcript(self.store, **body)
                write_json(self, 200, result)
                return
            if self.path == "/adapters/workflow":
                result = record_workflow_result(self.store, **body)
                write_json(self, 200, result)
                return
            if self.path == "/retain":
                content = body.pop("content")
                result = self.store.retain_memory(content, **body)
                write_json(self, 200, result)
                return
            if self.path == "/recall":
                query = body.get("query", "")
                result = self.store.recall(
                    query,
                    scope=body.get("scope", ""),
                    limit=int(body.get("limit", 5)),
                )
                write_json(self, 200, {"memories": result})
                return
            if self.path == "/forget":
                result = self.store.forget(
                    body.get("item_id", ""), reason=body.get("reason", "")
                )
                write_json(self, 200, result)
                return
            if self.path == "/extract":
                result = self.store.extract_candidates(
                    event_id=body.get("event_id", ""),
                    limit=int(body.get("limit", 50)),
                    auto_accept=bool(body.get("auto_accept", False)),
                )
                write_json(self, 200, result)
                return
            if self.path == "/candidates/accept":
                result = self.store.accept_candidate(body.get("candidate_id", ""))
                write_json(self, 200, result)
                return
            if self.path == "/candidates/reject":
                result = self.store.reject_candidate(
                    body.get("candidate_id", ""), reason=body.get("reason", "")
                )
                write_json(self, 200, result)
                return
            if self.path == "/policy/evaluate":
                result = self.store.evaluate_policy(
                    action_type=body.get("action_type", ""),
                    description=body.get("description", ""),
                    sensitivity=body.get("sensitivity", "normal"),
                    metadata=body.get("metadata") or {},
                )
                write_json(self, 200, result)
                return
            if self.path == "/policy/decide":
                result = self.store.decide_action_proposal(
                    body.get("proposal_id", ""),
                    decision=body.get("decision", ""),
                    reason=body.get("reason", ""),
                )
                write_json(self, 200, result)
                return
            if self.path == "/curator/run":
                result = self.store.run_curator(
                    stale_days=int(body.get("stale_days", 90)),
                    stale_salience_threshold=float(body.get("stale_salience_threshold", 0.3)),
                )
                write_json(self, 200, result)
                return
            write_json(self, 404, {"ok": False, "error": "not found"})
        except Exception as exc:
            write_json(self, 400, {"ok": False, "error": str(exc)})


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    MemSuHandler.store.init()
    server = ThreadingHTTPServer((host, port), MemSuHandler)
    print(f"memSu service listening on http://{host}:{port}", flush=True)
    server.serve_forever()
