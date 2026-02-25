from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


def build_snapshot_image(*, out_path: Path, title: str, rows: list[str]) -> Path:
    width = 1200
    line_h = 28
    margin = 24
    height = max(320, margin * 2 + (len(rows) + 4) * line_h)

    img = Image.new("RGB", (width, height), color=(14, 18, 27))
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, width, 70), fill=(35, 53, 84))
    draw.text((margin, 20), title, fill=(255, 255, 255))
    draw.text((margin, 90), f"Generated: {datetime.now(timezone.utc).isoformat()}", fill=(175, 197, 230))

    y = 130
    for row in rows:
        draw.text((margin, y), row, fill=(228, 238, 255))
        y += line_h

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    return out_path


def snapshot_rows_from_runtime(apps: list[dict[str, Any]], runtime: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    rt_apps = runtime.get("apps", {}) if isinstance(runtime, dict) else {}
    for app in apps:
        name = str(app.get("name", "unknown"))
        repo = str(app.get("repo_url", ""))
        info = rt_apps.get(name, {}) if isinstance(rt_apps, dict) else {}
        running = bool(info.get("running", False))
        port = info.get("port", "-")
        rows.append(f"{name:18} running={running!s:5} port={port} repo={repo}")
    return rows
