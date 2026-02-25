from __future__ import annotations

from pathlib import Path


def detect_stack(repo_dir: Path) -> str:
    if (repo_dir / "streamlit_app.py").exists():
        return "streamlit"
    if any((repo_dir / n).exists() for n in ["next.config.js", "next.config.mjs", "next.config.ts"]):
        return "next"
    if any((repo_dir / n).exists() for n in ["vite.config.js", "vite.config.ts", "vite.config.mjs"]):
        return "vite"
    if (repo_dir / "app" / "main.py").exists():
        return "fastapi"
    if (repo_dir / "pyproject.toml").exists() or (repo_dir / "requirements.txt").exists():
        return "python"
    if (repo_dir / "index.html").exists() and ((repo_dir / "app.js").exists() or (repo_dir / "main.js").exists()):
        return "static"
    return "unknown"


def detect_package_manager(repo_dir: Path) -> str:
    if (repo_dir / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (repo_dir / "package-lock.json").exists():
        return "npm"
    if (repo_dir / "yarn.lock").exists():
        return "yarn"
    return ""
