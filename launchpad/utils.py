from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os
import tomllib


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(read_text(path))


def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()
