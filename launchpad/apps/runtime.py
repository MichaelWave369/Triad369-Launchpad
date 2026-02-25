from __future__ import annotations

from pathlib import Path
from typing import Any
import json


def load_runtime(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"apps": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"apps": {}}
        data.setdefault("apps", {})
        return data
    except Exception:
        return {"apps": {}}


def save_runtime(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
