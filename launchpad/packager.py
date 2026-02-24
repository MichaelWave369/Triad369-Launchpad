from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile


MANIFEST_FILE_NAME = "artifact.manifest.json"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(
    source_dir: Path,
    *,
    project_name: str,
    target: str,
    prompt: str,
    generated_at: str | None = None,
) -> dict[str, object]:
    source_dir = source_dir.resolve()
    ts = generated_at or datetime.now(timezone.utc).isoformat()

    files: list[dict[str, str]] = []
    for p in sorted(source_dir.rglob("*")):
        if p.is_dir():
            continue
        rel = str(p.relative_to(source_dir))
        if rel == MANIFEST_FILE_NAME:
            continue
        files.append({"path": rel, "sha256": _sha256_file(p)})

    return {
        "project_name": project_name,
        "target": target,
        "prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
        "timestamp": ts,
        "files": files,
    }


def write_manifest(source_dir: Path, manifest: dict[str, object]) -> Path:
    manifest_path = source_dir / MANIFEST_FILE_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


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
