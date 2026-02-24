from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from .audit import AuditLog
from .coevo_client import CoEvoClient
from .nevora_bridge import nevora_installed, scaffold_fallback, scaffold_with_nevora
from .packager import build_manifest, write_manifest, zip_dir
from .specs import ProjectSpec
from .utils import env, load_json, load_toml, write_text

app = typer.Typer(add_completion=False, help="Triad369 Launchpad — Spec → Generate → Ship")
console = Console()


def _config_root() -> Path:
    return Path(".triad369")


def _audit() -> AuditLog:
    return AuditLog(_config_root())


def _load_spec(path: Path) -> ProjectSpec:
    if path.suffix.lower() == ".toml":
        data = load_toml(path)
    elif path.suffix.lower() == ".json":
        data = load_json(path)
    else:
        raise typer.BadParameter("Spec must be .toml or .json")
    return ProjectSpec(**data)


def _load_config() -> dict[str, str]:
    cfg_path = _config_root() / "config.toml"
    if not cfg_path.exists():
        return {}
    data = load_toml(cfg_path)
    return {k: str(v) for k, v in data.items()}


def _resolve_setting(flag: Optional[str], env_name: str, config_key: str, default: str) -> str:
    if flag is not None:
        return flag
    ev = env(env_name, "")
    if ev:
        return ev
    cfg = _load_config()
    return cfg.get(config_key, default)


@app.command()
def init() -> None:
    """Initialize local Launchpad config (stored in .triad369/)."""
    root = _config_root()
    root.mkdir(parents=True, exist_ok=True)
    default = """# Triad369 Launchpad local config
coevo_base_url = "http://localhost:8000"
coevo_board_slug = "dev"

# If you don't set COEVO_TOKEN, set COEVO_HANDLE + COEVO_PASSWORD as env vars.
"""
    write_text(root / "config.toml", default)
    _audit().write("init", {"path": str(root / "config.toml")})
    console.print(Panel.fit("✅ Initialized .triad369/config.toml", title="triad369 init"))


@app.command()
def generate(
    spec: Optional[Path] = typer.Option(None, help="Path to a .toml or .json spec"),
    prompt: Optional[str] = typer.Option(None, help="Prompt (if not using --spec)"),
    target: str = typer.Option("python", help="Nevora target (python, web-backend, etc.)"),
    mode: str = typer.Option("automation", help="Nevora mode"),
    out: Optional[Path] = typer.Option(None, help="Output directory for scaffold"),
) -> None:
    """Generate a runnable scaffold (Nevora if available; fallback if not)."""
    if spec:
        s = _load_spec(spec)
        prompt = s.prompt
        target = s.target
        mode = s.mode
        if out is None:
            out = Path("build") / s.name
    else:
        if not prompt:
            raise typer.BadParameter("Provide --prompt or --spec")
        if out is None:
            out = Path("build/out")

    console.print(Panel.fit(f"Prompt: {prompt}\nTarget: {target}\nOut: {out}", title="generate"))

    if nevora_installed():
        res = scaffold_with_nevora(prompt=prompt, target=target, out_dir=out, mode=mode)
        console.print(f"[bold]Nevora:[/bold] {res.message[:4000]}")
    else:
        res = scaffold_fallback(prompt=prompt, out_dir=out)
        console.print(f"[yellow]Nevora not installed.[/yellow] {res.message}")

    _audit().write("generate", {"ok": res.ok, "out": str(res.output_dir), "target": target, "mode": mode})
    if not res.ok:
        raise typer.Exit(code=2)


@app.command()
def pack(
    in_dir: Path = typer.Option(..., "--in", help="Directory to zip"),
    zip_path: Path = typer.Option(Path("build/artifact.zip"), "--zip", help="Zip output path"),
    name: Optional[str] = typer.Option(None, "--name", help="Project name for manifest metadata"),
    target: str = typer.Option("python", "--target", help="Project target for manifest metadata"),
    prompt: str = typer.Option("", "--prompt", help="Prompt text for manifest hash metadata"),
) -> None:
    """Zip a scaffold directory into a single artifact and write artifact.manifest.json."""
    if not in_dir.exists() or not in_dir.is_dir():
        raise typer.BadParameter(f"Not a directory: {in_dir}")

    manifest = build_manifest(
        in_dir,
        project_name=name or in_dir.name,
        target=target,
        prompt=prompt,
    )
    manifest_path = write_manifest(in_dir, manifest)
    out = zip_dir(in_dir, zip_path)
    _audit().write("pack", {"in": str(in_dir), "zip": str(out), "manifest": str(manifest_path)})
    console.print(Panel.fit(f"✅ Manifest: {manifest_path}\n✅ Zipped {in_dir} → {out}", title="pack"))


@app.command("publish-coevo")
def publish_coevo(
    in_dir: Optional[Path] = typer.Option(None, "--in", help="Scaffold directory to zip + upload"),
    zip_path: Optional[Path] = typer.Option(None, "--zip", help="Zip artifact to upload (or auto-created from --in)"),
    title: str = typer.Option(..., "--title", help="Thread title"),
    board: Optional[str] = typer.Option(None, "--board", help="Board slug (dev/help/general)"),
    summary: str = typer.Option("Built with Triad369 Launchpad.", "--summary", help="Post body (markdown)"),
    repo_url: Optional[str] = typer.Option(None, "--repo-url", help="Optional repo link to add to CoEvo"),
    tags: str = typer.Option("369,launchpad", "--tags", help="Comma-separated tags for optional repo link"),
) -> None:
    """Create a CoEvo thread, upload artifact, attach it, and optionally add a repo link."""
    if in_dir is None and zip_path is None:
        raise typer.BadParameter("Provide --in or --zip")

    if in_dir is not None:
        if not in_dir.exists() or not in_dir.is_dir():
            raise typer.BadParameter(f"Not a directory: {in_dir}")
        if zip_path is None:
            zip_path = Path("build") / f"{in_dir.name}.zip"
        manifest = build_manifest(in_dir, project_name=in_dir.name, target="python", prompt="")
        write_manifest(in_dir, manifest)
        zip_dir(in_dir, zip_path)

    assert zip_path is not None
    if not zip_path.exists():
        raise typer.BadParameter(f"Missing zip: {zip_path}")

    board_slug = _resolve_setting(board, "COEVO_BOARD_SLUG", "coevo_board_slug", "dev")
    base_url = _resolve_setting(None, "COEVO_BASE_URL", "coevo_base_url", "http://localhost:8000")

    client = CoEvoClient.from_env(base_url_override=base_url)
    board_id = client.find_board_id(board_slug)
    thread = client.create_thread(board_id=board_id, title=title)
    thread_id = int(thread["id"])

    client.create_post(thread_id=thread_id, content_md=summary)

    art = client.upload_artifact(zip_path)
    art_id = int(art["id"])
    client.attach_artifact_to_thread(artifact_id=art_id, thread_id=thread_id)

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if repo_url:
        client.add_repo_link(url=repo_url, title=title, description="Launchpad published repo", tags=tag_list)

    thread_url = f"{base_url.rstrip('/')}/boards/{board_slug}/threads/{thread_id}"
    _audit().write("publish_coevo", {"thread_id": thread_id, "artifact_id": art_id, "board": board_slug, "thread_url": thread_url})
    console.print(Panel.fit(
        f"✅ Published to CoEvo\nThread: {thread_id}\nArtifact: {art_id}\nBoard: {board_slug}\nURL: {thread_url}",
        title="publish-coevo",
    ))


@app.command()
def status() -> None:
    """Show local audit trail location."""
    path = _config_root() / "audit.jsonl"
    exists = path.exists()
    console.print(Panel.fit(f"audit: {path} ({'exists' if exists else 'missing'})", title="status"))


@app.command()
def run() -> None:
    """(stub) Run the generated project."""
    console.print("[dim]run: TODO (detect project type and run it)[/dim]")


@app.command()
def test() -> None:
    """(stub) Test the generated project."""
    console.print("[dim]test: TODO[/dim]")


@app.command("publish-github")
def publish_github() -> None:
    """(stub) Create/push a GitHub repo."""
    console.print("[dim]publish-github: TODO (PAT-based push)[/dim]")


@app.command()
def deploy() -> None:
    """(stub) Deploy guide (Railway/Render/Vercel)."""
    console.print("[dim]deploy: TODO (non-destructive helper)[/dim]")
