from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal, Optional


Target = Literal["python", "web-backend", "javascript", "cpp", "csharp", "blueprint", "gdscript"]


class ProjectSpec(BaseModel):
    name: str = Field(default="hello369")
    prompt: str = Field(default="A tiny app that says hello.")
    target: Target = Field(default="python")
    mode: str = Field(default="automation")
    source_language: str = Field(default="english")

    # Launchpad behaviors
    pack_zip_name: str = Field(default="artifact.zip")
    coevo_board_slug: str = Field(default="dev")
    coevo_thread_title: Optional[str] = None
    repo_url: Optional[str] = None

    def resolved_title(self) -> str:
        return self.coevo_thread_title or f"{self.name} — Launchpad build"
