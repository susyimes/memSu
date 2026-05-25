from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

try:
    from agent.memory_provider import MemoryProvider
except Exception:
    class MemoryProvider:  # type: ignore[no-redef]
        pass


RECALL_SCHEMA = {
    "name": "memsu_recall",
    "description": "Search memSu for scoped local memory across Hermes and other agents.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to recall."},
            "scope": {"type": "string", "description": "Optional memory scope."},
            "limit": {"type": "integer", "description": "Maximum results.", "default": 5},
        },
        "required": ["query"],
    },
}

RETAIN_SCHEMA = {
    "name": "memsu_retain",
    "description": "Save durable scoped memory in memSu.",
    "parameters": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Memory content to retain."},
            "type": {
                "type": "string",
                "description": "Memory type.",
                "enum": [
                    "preference",
                    "project_rule",
                    "fact",
                    "decision",
                    "workflow_lesson",
                    "failure_pattern",
                    "skill_candidate",
                    "note",
                ],
            },
            "scope": {"type": "string", "description": "Memory scope."},
            "confidence": {"type": "number", "description": "0.0 to 1.0 confidence."},
            "salience": {"type": "number", "description": "0.0 to 1.0 salience."},
        },
        "required": ["content"],
    },
}

AUDIT_SCHEMA = {
    "name": "memsu_audit",
    "description": "List current memSu memory items for review.",
    "parameters": {
        "type": "object",
        "properties": {
            "scope": {"type": "string", "description": "Optional scope filter."},
            "status": {"type": "string", "description": "Status filter.", "default": "active"},
            "limit": {"type": "integer", "description": "Maximum results.", "default": 50},
        },
        "required": [],
    },
}

FORGET_SCHEMA = {
    "name": "memsu_forget",
    "description": "Archive a memSu memory item. Use only when the user asks to forget or correct memory.",
    "parameters": {
        "type": "object",
        "properties": {
            "item_id": {"type": "string", "description": "Memory item id."},
            "reason": {"type": "string", "description": "Optional reason."},
        },
        "required": ["item_id"],
    },
}

REFLECT_SCHEMA = {
    "name": "memsu_reflect",
    "description": "Record a reflection event for later memSu maintenance. Does not perform external actions.",
    "parameters": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Reflection or maintenance note."},
            "scope": {"type": "string", "description": "Optional scope."},
        },
        "required": ["content"],
    },
}

EXTRACT_SCHEMA = {
    "name": "memsu_extract",
    "description": "Extract pending memory candidates from recent memSu events without auto-accepting them.",
    "parameters": {
        "type": "object",
        "properties": {
            "event_id": {"type": "string", "description": "Optional event id."},
            "limit": {"type": "integer", "description": "Maximum events to inspect.", "default": 50},
        },
        "required": [],
    },
}

CANDIDATES_SCHEMA = {
    "name": "memsu_candidates",
    "description": "List pending, accepted, or rejected memSu memory candidates.",
    "parameters": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "Candidate status.", "default": "pending"},
            "scope": {"type": "string", "description": "Optional scope filter."},
            "limit": {"type": "integer", "description": "Maximum results.", "default": 50},
        },
        "required": [],
    },
}

ACCEPT_CANDIDATE_SCHEMA = {
    "name": "memsu_accept_candidate",
    "description": "Accept a pending memSu memory candidate and promote it to long-term memory.",
    "parameters": {
        "type": "object",
        "properties": {
            "candidate_id": {"type": "string", "description": "Candidate id."},
        },
        "required": ["candidate_id"],
    },
}

REJECT_CANDIDATE_SCHEMA = {
    "name": "memsu_reject_candidate",
    "description": "Reject a pending memSu memory candidate with an optional reason.",
    "parameters": {
        "type": "object",
        "properties": {
            "candidate_id": {"type": "string", "description": "Candidate id."},
            "reason": {"type": "string", "description": "Reason for rejecting the candidate."},
        },
        "required": ["candidate_id"],
    },
}

POLICY_CHECK_SCHEMA = {
    "name": "memsu_policy_check",
    "description": "Evaluate a proposed proactive action against memSu L0-L4 policy.",
    "parameters": {
        "type": "object",
        "properties": {
            "action_type": {"type": "string", "description": "Action type, such as suggestion, file_edit, send_message, or credential_capture."},
            "description": {"type": "string", "description": "Short action description."},
            "sensitivity": {"type": "string", "description": "normal, private, secret, or credential.", "default": "normal"},
            "metadata": {"type": "object", "description": "Optional structured metadata."},
        },
        "required": ["action_type"],
    },
}

POLICY_PROPOSALS_SCHEMA = {
    "name": "memsu_policy_proposals",
    "description": "List memSu action proposals, especially pending confirmations.",
    "parameters": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "Optional status filter."},
            "limit": {"type": "integer", "description": "Maximum results.", "default": 50},
        },
        "required": [],
    },
}


class MemSuMemoryProvider(MemoryProvider):
    def __init__(self):
        self._url = os.environ.get("MEMSU_URL", "http://127.0.0.1:8765").rstrip("/")
        self._session_id = ""
        self._agent_context = "primary"
        self._agent_identity = ""
        self._workspace = "hermes"

    @property
    def name(self) -> str:
        return "memsu"

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        self._agent_context = kwargs.get("agent_context", "primary")
        self._agent_identity = kwargs.get("agent_identity", "")
        self._workspace = kwargs.get("agent_workspace", "hermes")

    def system_prompt_block(self) -> str:
        return (
            "# memSu Memory\n"
            "Active. Use memsu_recall for scoped local memory, memsu_retain for durable facts, "
            "memsu_audit for review, memsu_candidates to review extracted candidates, "
            "memsu_policy_check before proactive actions, "
            "and memsu_forget only when the user asks to remove memory. "
            "Do not use memSu tools for high-risk external actions."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not query or len(query.strip()) < 3:
            return ""
        result = self._post(
            "/recall",
            {"query": query[:2000], "scope": self._default_scope(), "limit": 5},
            timeout=3,
        )
        memories = result.get("memories", []) if isinstance(result, dict) else []
        if not memories:
            return ""
        lines = ["## memSu Context"]
        for item in memories:
            lines.append(
                f"- [{item.get('type')}:{item.get('scope')}] "
                f"{item.get('content')} (id: {item.get('item_id')})"
            )
        return "\n".join(lines)

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        if self._agent_context != "primary":
            return
        content = f"User: {user_content[:4000]}\nAssistant: {assistant_content[:4000]}"
        result = self._post(
            "/events",
            {
                "source_agent": "hermes",
                "source_type": "conversation",
                "actor": "assistant",
                "event_type": "conversation_turn",
                "content": content,
                "workspace": self._workspace,
                "thread_id": session_id or self._session_id,
                "metadata": {
                    "agent_identity": self._agent_identity,
                    "scope": self._default_scope(),
                },
            },
            timeout=3,
        )
        event_id = result.get("event_id") if isinstance(result, dict) else ""
        if event_id:
            self._post("/extract", {"event_id": event_id, "auto_accept": False}, timeout=3)

    def on_memory_write(self, action, target, content, metadata=None) -> None:
        if action not in {"add", "replace"} or not content:
            return
        self._post(
            "/retain",
            {
                "content": str(content),
                "type": "note",
                "scope": self._default_scope(),
                "metadata": {
                    "source": "hermes_builtin_memory",
                    "target": target,
                    "action": action,
                    **(metadata or {}),
                },
            },
            timeout=3,
        )

    def on_delegation(self, task: str, result: str, *, child_session_id: str = "", **kwargs) -> None:
        self._post(
            "/events",
            {
                "source_agent": "hermes",
                "source_type": "delegation",
                "actor": "assistant",
                "event_type": "delegation_result",
                "content": f"Task: {task[:3000]}\nResult: {result[:3000]}",
                "workspace": self._workspace,
                "thread_id": self._session_id,
                "metadata": {"child_session_id": child_session_id},
            },
            timeout=3,
        )

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        self._post(
            "/events",
            {
                "source_agent": "hermes",
                "source_type": "compression",
                "actor": "system",
                "event_type": "session_summary",
                "content": f"Pre-compression message count: {len(messages)}",
                "workspace": self._workspace,
                "thread_id": self._session_id,
            },
            timeout=3,
        )
        return ""

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            RECALL_SCHEMA,
            RETAIN_SCHEMA,
            AUDIT_SCHEMA,
            FORGET_SCHEMA,
            REFLECT_SCHEMA,
            EXTRACT_SCHEMA,
            CANDIDATES_SCHEMA,
            ACCEPT_CANDIDATE_SCHEMA,
            REJECT_CANDIDATE_SCHEMA,
            POLICY_CHECK_SCHEMA,
            POLICY_PROPOSALS_SCHEMA,
        ]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        args = args or {}
        if tool_name == "memsu_recall":
            return json.dumps(
                self._post(
                    "/recall",
                    {
                        "query": args.get("query", ""),
                        "scope": args.get("scope") or self._default_scope(),
                        "limit": args.get("limit", 5),
                    },
                ),
                ensure_ascii=False,
            )
        if tool_name == "memsu_retain":
            payload = {
                "content": args.get("content", ""),
                "type": args.get("type", "note"),
                "scope": args.get("scope") or self._default_scope(),
                "confidence": args.get("confidence", 0.7),
                "salience": args.get("salience", 0.5),
                "metadata": {"source": "hermes_tool", "session_id": self._session_id},
            }
            return json.dumps(self._post("/retain", payload), ensure_ascii=False)
        if tool_name == "memsu_audit":
            query = (
                f"?scope={args.get('scope', '')}&status={args.get('status', 'active')}"
                f"&limit={args.get('limit', 50)}"
            )
            return json.dumps(self._get(f"/audit{query}"), ensure_ascii=False)
        if tool_name == "memsu_forget":
            return json.dumps(
                self._post(
                    "/forget",
                    {"item_id": args.get("item_id", ""), "reason": args.get("reason", "")},
                ),
                ensure_ascii=False,
            )
        if tool_name == "memsu_reflect":
            return json.dumps(
                self._post(
                    "/events",
                    {
                        "source_agent": "hermes",
                        "source_type": "reflection",
                        "actor": "assistant",
                        "event_type": "workflow_result",
                        "content": args.get("content", ""),
                        "workspace": self._workspace,
                        "thread_id": self._session_id,
                        "metadata": {"scope": args.get("scope") or self._default_scope()},
                    },
                ),
                ensure_ascii=False,
            )
        if tool_name == "memsu_extract":
            return json.dumps(
                self._post(
                    "/extract",
                    {
                        "event_id": args.get("event_id", ""),
                        "limit": args.get("limit", 50),
                        "auto_accept": False,
                    },
                ),
                ensure_ascii=False,
            )
        if tool_name == "memsu_candidates":
            query = urllib.parse.urlencode(
                {
                    "status": args.get("status", "pending"),
                    "scope": args.get("scope", ""),
                    "limit": args.get("limit", 50),
                }
            )
            return json.dumps(self._get(f"/candidates?{query}"), ensure_ascii=False)
        if tool_name == "memsu_accept_candidate":
            return json.dumps(
                self._post(
                    "/candidates/accept",
                    {"candidate_id": args.get("candidate_id", "")},
                ),
                ensure_ascii=False,
            )
        if tool_name == "memsu_reject_candidate":
            return json.dumps(
                self._post(
                    "/candidates/reject",
                    {
                        "candidate_id": args.get("candidate_id", ""),
                        "reason": args.get("reason", ""),
                    },
                ),
                ensure_ascii=False,
            )
        if tool_name == "memsu_policy_check":
            return json.dumps(
                self._post(
                    "/policy/evaluate",
                    {
                        "action_type": args.get("action_type", ""),
                        "description": args.get("description", ""),
                        "sensitivity": args.get("sensitivity", "normal"),
                        "metadata": args.get("metadata") or {},
                    },
                ),
                ensure_ascii=False,
            )
        if tool_name == "memsu_policy_proposals":
            query = urllib.parse.urlencode(
                {
                    "status": args.get("status", ""),
                    "limit": args.get("limit", 50),
                }
            )
            return json.dumps(self._get(f"/policy/proposals?{query}"), ensure_ascii=False)
        return json.dumps({"ok": False, "error": f"unknown tool: {tool_name}"})

    def _default_scope(self) -> str:
        if self._agent_identity:
            return f"hermes:{self._agent_identity}"
        return "hermes"

    def _post(self, path: str, payload: Dict[str, Any], timeout: int = 5) -> Dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self._url + path,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        return self._request(request, timeout=timeout)

    def _get(self, path: str, timeout: int = 5) -> Dict[str, Any]:
        request = urllib.request.Request(self._url + path, method="GET")
        return self._request(request, timeout=timeout)

    def _request(self, request: urllib.request.Request, timeout: int) -> Dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            return {"ok": False, "error": f"memSu service unavailable: {exc}"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def register(ctx):
    ctx.register_memory_provider(MemSuMemoryProvider())
