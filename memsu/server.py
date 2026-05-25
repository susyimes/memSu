from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

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
        write_json(self, 404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        try:
            body = read_json(self)
            if self.path == "/events":
                result = self.store.append_event(**body)
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
            write_json(self, 404, {"ok": False, "error": "not found"})
        except Exception as exc:
            write_json(self, 400, {"ok": False, "error": str(exc)})


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    MemSuHandler.store.init()
    server = ThreadingHTTPServer((host, port), MemSuHandler)
    print(f"memSu service listening on http://{host}:{port}", flush=True)
    server.serve_forever()

