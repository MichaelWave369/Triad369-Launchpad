from __future__ import annotations

from pathlib import Path
import zipfile


def zip_dir(source_dir: Path, zip_path: Path) -> Path:
    source_dir = source_dir.resolve()
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in source_dir.rglob("*"):
            if p.is_dir():
                continue
            rel = p.relative_to(source_dir)
            z.write(p, arcname=str(rel))
    return zip_path
