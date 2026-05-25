from __future__ import annotations

import json
import sys
from typing import Any

from .store import utc_now


def log_event(event: str, **fields: Any) -> None:
    payload = {
        "timestamp": utc_now(),
        "event": event,
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr, flush=True)

