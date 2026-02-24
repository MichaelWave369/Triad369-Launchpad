from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class AuditEvent:
    ts: str
    type: str
    payload: dict[str, Any]


class AuditLog:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "audit.jsonl"

    def write(self, event_type: str, payload: dict[str, Any]) -> None:
        evt = AuditEvent(
            ts=datetime.now(timezone.utc).isoformat(),
            type=event_type,
            payload=payload,
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(evt.__dict__, ensure_ascii=False) + "\n")
