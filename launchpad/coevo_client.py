from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx

from .utils import env


@dataclass
class CoEvoAuth:
    base_url: str
    token: str


class CoEvoClient:
    """Minimal CoEvo API client.

    Uses endpoints that exist in the CoEvo server today:
      - POST /api/auth/login
      - GET  /api/boards
      - POST /api/boards/{board_id}/threads
      - POST /api/threads/{thread_id}/posts
      - POST /api/artifacts/upload
      - POST /api/artifacts/{artifact_id}/attach/thread/{thread_id}
      - POST /api/repos
    """

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token

    @classmethod
    def from_env(cls, base_url_override: Optional[str] = None) -> "CoEvoClient":
        base_url = (base_url_override or env("COEVO_BASE_URL", "http://localhost:8000")).strip()
        token = env("COEVO_TOKEN", "")
        if not token:
            handle = env("COEVO_HANDLE")
            password = env("COEVO_PASSWORD")
            if not handle or not password:
                raise RuntimeError("Missing COEVO_TOKEN or (COEVO_HANDLE + COEVO_PASSWORD).")
            token = login(base_url, handle, password)
        return cls(base_url, token)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def list_boards(self) -> list[dict[str, Any]]:
        r = httpx.get(f"{self.base_url}/api/boards", headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def find_board_id(self, slug: str) -> int:
        boards = self.list_boards()
        for b in boards:
            if b.get("slug") == slug:
                return int(b["id"])
        # fallback: first board
        if not boards:
            raise RuntimeError("No boards found in CoEvo.")
        return int(boards[0]["id"])

    def create_thread(self, board_id: int, title: str) -> dict[str, Any]:
        r = httpx.post(
            f"{self.base_url}/api/boards/{board_id}/threads",
            headers=self._headers(),
            json={"title": title},
            timeout=45,
        )
        r.raise_for_status()
        return r.json()


    def get_thread(self, thread_id: int) -> dict[str, Any]:
        r = httpx.get(
            f"{self.base_url}/api/threads/{thread_id}",
            headers=self._headers(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def list_thread_posts(self, thread_id: int) -> list[dict[str, Any]]:
        r = httpx.get(
            f"{self.base_url}/api/threads/{thread_id}/posts",
            headers=self._headers(),
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    def create_post(self, thread_id: int, content_md: str) -> dict[str, Any]:
        r = httpx.post(
            f"{self.base_url}/api/threads/{thread_id}/posts",
            headers=self._headers(),
            json={"content_md": content_md},
            timeout=45,
        )
        r.raise_for_status()
        return r.json()

    def upload_artifact(self, zip_path: Path) -> dict[str, Any]:
        with zip_path.open("rb") as f:
            files = {"file": (zip_path.name, f, "application/zip")}
            r = httpx.post(
                f"{self.base_url}/api/artifacts/upload",
                headers=self._headers(),
                files=files,
                timeout=120,
            )
        r.raise_for_status()
        return r.json()

    def attach_artifact_to_thread(self, artifact_id: int, thread_id: int) -> dict[str, Any]:
        r = httpx.post(
            f"{self.base_url}/api/artifacts/{artifact_id}/attach/thread/{thread_id}",
            headers=self._headers(),
            timeout=45,
        )
        r.raise_for_status()
        return r.json()

    def add_repo_link(self, url: str, title: str = "", description: str = "", tags: Optional[list[str]] = None) -> dict[str, Any]:
        tags = tags or []
        r = httpx.post(
            f"{self.base_url}/api/repos",
            headers=self._headers(),
            json={"url": url, "title": title, "description": description, "tags": tags},
            timeout=45,
        )
        r.raise_for_status()
        return r.json()


def login(base_url: str, handle: str, password: str) -> str:
    r = httpx.post(
        f"{base_url.rstrip('/')}/api/auth/login",
        json={"handle": handle, "password": password},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Login succeeded but no access_token returned.")
    return token
