"""Registro sencillo de acciones en archivo JSON y consola."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict

LOG_FILE = Path(os.getenv("ACTION_LOG_PATH", "data/actions_log.json"))
_lock = Lock()


def log_action(channel: str, data: Dict[str, Any]) -> None:
    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "channel": channel,
        "data": data,
    }
    print(f"[{record['timestamp']}] {channel.upper()}: {data}")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    with _lock:
        existing = []
        if LOG_FILE.exists():
            try:
                existing = json.loads(LOG_FILE.read_text())
            except json.JSONDecodeError:
                existing = []
        existing.append(record)
        LOG_FILE.write_text(json.dumps(existing, indent=2))
