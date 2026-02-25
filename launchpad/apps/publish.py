from __future__ import annotations

from pathlib import Path

from ..coevo_client import CoEvoClient


def publish_zip_to_coevo(*, zip_path: Path, title: str, board: str, summary: str, repo_url: str | None = None, tags: list[str] | None = None, base_url_override: str | None = None) -> dict[str, int | str]:
    client = CoEvoClient.from_env(base_url_override=base_url_override)
    board_id = client.find_board_id(board)
    thread = client.create_thread(board_id=board_id, title=title)
    thread_id = int(thread["id"])
    client.create_post(thread_id=thread_id, content_md=summary)
    art = client.upload_artifact(zip_path)
    art_id = int(art["id"])
    client.attach_artifact_to_thread(artifact_id=art_id, thread_id=thread_id)
    if repo_url:
        client.add_repo_link(url=repo_url, title=title, description="Launchpad Hub publish", tags=tags or ["369", "launchpad"])
    return {"thread_id": thread_id, "artifact_id": art_id}
