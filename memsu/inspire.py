from __future__ import annotations

from pathlib import Path
from typing import Any

from .paths import default_inspire_dir, default_inspire_path


DEFAULT_INSPIRE = """# memSu Observation Inspire

This file is user-owned. Edit it to tell memSu's observation agent what local
work matters, which directories are important, and which places should stay out
of routine observation.

When observing local work, pay attention to:

- what project lines I have been working on recently
- newly installed, removed, active, or abandoned local agents and AI tools
- repeated workflows that may deserve a skill or automation
- project rules, preferences, decisions, and corrections that may deserve memory
- contradictions between old memory and current local evidence

Important local places:

- Add project roots or directories that should be considered likely work areas.
- Add directories that are low-value or private and should usually be skipped.
- Describe tools or apps whose install/uninstall/activity state matters.

Privacy:

- Do not read credentials, cookies, tokens, private keys, account secrets, or
  private chat bodies unless I explicitly grant that scope.
- Prefer metadata before content.
- Separate facts, inferences, and unknowns.
- Attach evidence to important claims.
"""


def ensure_inspire_files(*, overwrite: bool = False) -> dict[str, Any]:
    path = default_inspire_path()
    inspire_dir = default_inspire_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
    inspire_dir.mkdir(parents=True, exist_ok=True)

    created = False
    if overwrite or not path.exists():
        path.write_text(DEFAULT_INSPIRE, encoding="utf-8")
        created = True

    return {
        "inspire_path": str(path),
        "inspire_dir": str(inspire_dir),
        "created": created,
        "user_editable": True,
    }


def inspire_status() -> dict[str, Any]:
    path = default_inspire_path()
    inspire_dir = default_inspire_dir()
    return {
        "inspire_path": str(path),
        "inspire_dir": str(inspire_dir),
        "exists": path.exists(),
        "dir_exists": inspire_dir.exists(),
        "user_editable": True,
    }


def read_inspire() -> dict[str, Any]:
    status = inspire_status()
    path = Path(status["inspire_path"])
    content = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    return {**status, "content": content}
