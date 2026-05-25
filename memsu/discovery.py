from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from . import __version__
from .paths import (
    default_capabilities_path,
    default_db_path,
    default_install_marker_path,
    default_observe_dir,
    default_policy_path,
    memsu_home,
)
from .store import SCHEMA_VERSION, MemSuStore


PLACEHOLDER_HOME = "${MEMSU_HOME:-~/.memsu}"
ENTRYPOINT = "python -m memsu"


def install_manifest() -> dict[str, Any]:
    return {
        "initialized": True,
        "version": __version__,
        "schema_version": SCHEMA_VERSION,
        "mode": "cli-first",
        "service_required": False,
        "home_env": "MEMSU_HOME",
        "entrypoint": ENTRYPOINT,
        "capabilities_path": f"{PLACEHOLDER_HOME}/capabilities.json",
    }


def capabilities_manifest() -> dict[str, Any]:
    return {
        "version": __version__,
        "mode": "cli-first",
        "service_required": False,
        "home_env": "MEMSU_HOME",
        "entrypoint": ENTRYPOINT,
        "interfaces": {
            "cli": True,
            "http_service": False,
        },
        "commands": {
            "status": f"{ENTRYPOINT} status",
            "doctor": f"{ENTRYPOINT} doctor",
            "recall": f"{ENTRYPOINT} recall",
            "retain": f"{ENTRYPOINT} retain",
            "event_append": f"{ENTRYPOINT} event append",
            "observe_run": f"{ENTRYPOINT} observe run",
            "candidate_list": f"{ENTRYPOINT} candidate list",
            "curator_run": f"{ENTRYPOINT} curator run",
            "policy_evaluate": f"{ENTRYPOINT} policy evaluate",
        },
        "paths": {
            "home": PLACEHOLDER_HOME,
            "db": f"{PLACEHOLDER_HOME}/memsu.db",
            "observe_dir": f"{PLACEHOLDER_HOME}/observe",
            "policy": f"{PLACEHOLDER_HOME}/policy.yaml",
            "capabilities": f"{PLACEHOLDER_HOME}/capabilities.json",
            "install_marker": f"{PLACEHOLDER_HOME}/install.json",
        },
    }


def ensure_discovery_files() -> dict[str, Any]:
    home = memsu_home()
    home.mkdir(parents=True, exist_ok=True)
    install_path = default_install_marker_path()
    capabilities_path = default_capabilities_path()
    write_json(install_path, install_manifest())
    write_json(capabilities_path, capabilities_manifest())
    return {
        "install_marker": str(install_path),
        "capabilities": str(capabilities_path),
    }


def status_payload(store: MemSuStore | None = None) -> dict[str, Any]:
    store = store or MemSuStore()
    db_path = store.db_path
    initialized = db_path.exists()
    marker_path = default_install_marker_path()
    capabilities_path = default_capabilities_path()
    policy_path = default_policy_path()
    observe_dir = default_observe_dir()
    schema_version = read_schema_version(db_path) if initialized else None

    return {
        "ok": initialized and schema_version == SCHEMA_VERSION,
        "initialized": initialized,
        "mode": "cli-first",
        "service_required": False,
        "entrypoint": ENTRYPOINT,
        "schema_version": schema_version,
        "expected_schema_version": SCHEMA_VERSION,
        "manifest_templates": {
            "home": PLACEHOLDER_HOME,
            "db": f"{PLACEHOLDER_HOME}/memsu.db",
            "observe_dir": f"{PLACEHOLDER_HOME}/observe",
            "policy": f"{PLACEHOLDER_HOME}/policy.yaml",
            "capabilities": f"{PLACEHOLDER_HOME}/capabilities.json",
            "install_marker": f"{PLACEHOLDER_HOME}/install.json",
        },
        "resolved_paths": {
            "home": str(memsu_home()),
            "db": str(db_path),
            "observe_dir": str(observe_dir),
            "policy": str(policy_path),
            "capabilities": str(capabilities_path),
            "install_marker": str(marker_path),
        },
        "files": {
            "db": db_path.exists(),
            "policy": policy_path.exists(),
            "capabilities": capabilities_path.exists(),
            "install_marker": marker_path.exists(),
            "observe_dir": observe_dir.exists(),
        },
    }


def read_schema_version(db_path: Path) -> int | None:
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    if not row or row[0] is None:
        return None
    return int(row[0])


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
