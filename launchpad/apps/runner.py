from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shlex
import socket
import subprocess
from typing import Any

from .runtime import load_runtime, save_runtime


def is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def allocate_port(start: int, end: int, used: set[int] | None = None) -> int:
    used = used or set()
    for p in range(start, end + 1):
        if p in used:
            continue
        if is_port_free(p):
            return p
    raise RuntimeError(f"No free ports in range {start}-{end}")


def start_process(command: str, cwd: Path, log_path: Path, env: dict[str, str] | None = None) -> subprocess.Popen[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    f = log_path.open("a", encoding="utf-8")
    return subprocess.Popen(
        shlex.split(command),
        cwd=str(cwd),
        env=env,
        stdout=f,
        stderr=subprocess.STDOUT,
        text=True,
    )


def update_runtime_running(runtime_path: Path, app_name: str, payload: dict[str, Any]) -> None:
    rt = load_runtime(runtime_path)
    rt.setdefault("apps", {})
    rt["apps"][app_name] = payload
    save_runtime(runtime_path, rt)


def mark_stopped(runtime_path: Path, app_name: str) -> None:
    rt = load_runtime(runtime_path)
    info = rt.get("apps", {}).get(app_name)
    if isinstance(info, dict):
        info["stopped_at"] = datetime.now(timezone.utc).isoformat()
        info["running"] = False
    save_runtime(runtime_path, rt)
