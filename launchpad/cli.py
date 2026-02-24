from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from .audit import AuditLog
from .specs import ProjectSpec
from .utils import load_json, load_toml, write_text
from .nevora_bridge import nevora_installed, scaffold_with_nevora, scaffold_fallback
from .packager import zip_dir
from .coevo_client import CoEvoClient

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
) -> None:
    """Zip a scaffold directory into a single artifact."""
    if not in_dir.exists() or not in_dir.is_dir():
        raise typer.BadParameter(f"Not a directory: {in_dir}")
    out = zip_dir(in_dir, zip_path)
    _audit().write("pack", {"in": str(in_dir), "zip": str(out)})
    console.print(Panel.fit(f"✅ Zipped {in_dir} → {out}", title="pack"))


@app.command("publish-coevo")
def publish_coevo(
    zip_path: Path = typer.Option(..., "--zip", help="Zip artifact to upload"),
    title: str = typer.Option(..., "--title", help="Thread title"),
    board: str = typer.Option("dev", "--board", help="Board slug (dev/help/general)"),
    summary: str = typer.Option("Built with Triad369 Launchpad.", "--summary", help="Post body (markdown)"),
    repo_url: Optional[str] = typer.Option(None, "--repo-url", help="Optional repo link to add to CoEvo"),
) -> None:
    """Create a CoEvo thread, upload artifact, attach it, and optionally add a repo link."""
    if not zip_path.exists():
        raise typer.BadParameter(f"Missing zip: {zip_path}")

    client = CoEvoClient.from_env()
    board_id = client.find_board_id(board)
    thread = client.create_thread(board_id=board_id, title=title)
    thread_id = int(thread["id"])

    # Add a summary post
    client.create_post(thread_id=thread_id, content_md=summary)

    # Upload + attach zip
    art = client.upload_artifact(zip_path)
    art_id = int(art["id"])
    client.attach_artifact_to_thread(artifact_id=art_id, thread_id=thread_id)

    # Optional repo link
    if repo_url:
        client.add_repo_link(url=repo_url, title=title, description="Launchpad published repo", tags=["launchpad","369"])

    _audit().write("publish_coevo", {"thread_id": thread_id, "artifact_id": art_id, "board": board})
    console.print(Panel.fit(
        f"✅ Published to CoEvo\nThread: {thread_id}\nArtifact: {art_id}\nBoard: {board}",
        title="publish-coevo"
    ))


@app.command()
def status() -> None:
    """Show local audit trail location."""
    path = _config_root() / "audit.jsonl"
    exists = path.exists()
    console.print(Panel.fit(f"audit: {path} ({'exists' if exists else 'missing'})", title="status"))


# --- stubs (future 9-command set) ---

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
