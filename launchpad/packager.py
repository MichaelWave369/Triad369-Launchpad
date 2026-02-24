from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
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


def _sha256_reader(reader: Any) -> str:
    h = hashlib.sha256()
    while True:
        chunk = reader.read(8192)
        if not chunk:
            break
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


def read_manifest(source_dir: Path) -> dict[str, Any]:
    path = source_dir / MANIFEST_FILE_NAME
    return json.loads(path.read_text(encoding="utf-8"))


def verify_manifest_dir(source_dir: Path) -> tuple[bool, list[str]]:
    source_dir = source_dir.resolve()
    manifest = read_manifest(source_dir)
    files = manifest.get("files", [])
    if not isinstance(files, list):
        return False, ["Invalid manifest: files must be a list"]

    errors: list[str] = []
    for row in files:
        if not isinstance(row, dict):
            errors.append("Invalid manifest row")
            continue
        rel = str(row.get("path", ""))
        expected = str(row.get("sha256", ""))
        path = source_dir / rel
        if not path.exists() or not path.is_file():
            errors.append(f"Missing file: {rel}")
            continue
        actual = _sha256_file(path)
        if actual != expected:
            errors.append(f"Hash mismatch: {rel}")
    return len(errors) == 0, errors


def verify_manifest_zip(zip_path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    with zipfile.ZipFile(zip_path, "r") as z:
        try:
            manifest_data = z.read(MANIFEST_FILE_NAME)
        except KeyError:
            return False, [f"Missing {MANIFEST_FILE_NAME} in zip"]

        manifest = json.loads(manifest_data.decode("utf-8"))
        files = manifest.get("files", [])
        if not isinstance(files, list):
            return False, ["Invalid manifest: files must be a list"]

        for row in files:
            if not isinstance(row, dict):
                errors.append("Invalid manifest row")
                continue
            rel = str(row.get("path", ""))
            expected = str(row.get("sha256", ""))
            try:
                with z.open(rel, "r") as f:
                    actual = _sha256_reader(f)
            except KeyError:
                errors.append(f"Missing file in zip: {rel}")
                continue
            if actual != expected:
                errors.append(f"Hash mismatch in zip: {rel}")

    return len(errors) == 0, errors


def zip_dir(source_dir: Path, zip_path: Path) -> Path:
    source_dir = source_dir.resolve()
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(source_dir.rglob("*")):
            if p.is_dir():
                continue
            rel = p.relative_to(source_dir)
            z.write(p, arcname=str(rel))
    return zip_path
