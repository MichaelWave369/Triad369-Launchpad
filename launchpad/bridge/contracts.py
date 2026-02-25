from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..apps.registry import AppConfig


@dataclass
class Capsule:
    name: str
    repo_url: str
    stack: str
    entrypoints: list[str]
    recommended_ports: list[int]
    tags: list[str]
    capabilities: list[str]
    capsule_mode: str
    health_path: str


def capsule_from_app(app: AppConfig, detected_stack: str | None = None) -> dict[str, Any]:
    stack = detected_stack or app.stack_hint or app.app_type or "unknown"
    entrypoints: list[str] = []
    if app.python_entrypoint:
        entrypoints.append(app.python_entrypoint)
    if app.start_cmd:
        entrypoints.append(app.start_cmd)

    tags = ["launchpad", "369", stack]
    capabilities: list[str] = ["pack", "capsule"]
    if app.capsule_mode == "http":
        capabilities.append("health")
    if app.capsule_mode == "wip":
        capabilities.append("wip")

    cap = Capsule(
        name=app.name,
        repo_url=app.repo_url,
        stack=stack,
        entrypoints=entrypoints,
        recommended_ports=[app.default_port, app.port_max],
        tags=tags,
        capabilities=capabilities,
        capsule_mode=app.capsule_mode,
        health_path=app.health_path,
    )
    return asdict(cap)
