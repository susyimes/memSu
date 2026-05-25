from __future__ import annotations

import os
from pathlib import Path


def memsu_home() -> Path:
    configured = os.environ.get("MEMSU_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".memsu").resolve()


def default_db_path() -> Path:
    return memsu_home() / "memsu.db"


def default_policy_path() -> Path:
    return memsu_home() / "policy.yaml"

