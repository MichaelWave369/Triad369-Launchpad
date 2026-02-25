from __future__ import annotations

from pathlib import Path

DEFAULT_EXCLUDES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".next",
    ".turbo",
    ".cache",
    ".pytest_cache",
    "dist",
    "build",
    "coverage",
    "*.db",
    "*.sqlite",
}


def should_exclude(rel_path: str, include_build_output: bool = False) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    for p in parts:
        if p in {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".turbo", ".cache"}:
            return True
        if not include_build_output and p in {"dist", "build", ".next"}:
            return True
    name = parts[-1] if parts else ""
    if name.endswith(".db") or name.endswith(".sqlite"):
        return True
    return False
