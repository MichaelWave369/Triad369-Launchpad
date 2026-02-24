from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Optional

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


def _run_cmd(args: list[str], cwd: Path) -> int:
    console.print(f"[bold]$[/bold] {' '.join(args)}")
    proc = subprocess.run(args, cwd=str(cwd), check=False)
    return proc.returncode


def _project_kind(project_dir: Path) -> str:
    if (project_dir / "app" / "main.py").exists():
        return "fastapi"
    if (project_dir / "main.py").exists():
        return "python"
    if (project_dir / "package.json").exists():
        return "vite"
    return "unknown"


def _package_scripts(project_dir: Path) -> dict[str, str]:
    path = project_dir / "package.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        scripts = data.get("scripts", {})
        return scripts if isinstance(scripts, dict) else {}
    except Exception:
        return {}


def _generate_project(prompt: str, target: str, mode: str, out: Path) -> tuple[bool, str]:
    if nevora_installed():
        res = scaffold_with_nevora(prompt=prompt, target=target, out_dir=out, mode=mode)
    else:
        res = scaffold_fallback(prompt=prompt, out_dir=out)
    return res.ok, res.message


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

    assert prompt is not None
    assert out is not None
    console.print(Panel.fit(f"Prompt: {prompt}\nTarget: {target}\nOut: {out}", title="generate"))

    ok, message = _generate_project(prompt=prompt, target=target, mode=mode, out=out)
    if nevora_installed():
        console.print(f"[bold]Nevora:[/bold] {message[:4000]}")
    else:
        console.print(f"[yellow]Nevora not installed.[/yellow] {message}")

    _audit().write("generate", {"ok": ok, "out": str(out), "target": target, "mode": mode})
    if not ok:
        raise typer.Exit(code=2)


@app.command("generate-batch")
def generate_batch(
    prompt: str = typer.Option(..., help="Base prompt"),
    target: str = typer.Option("python", help="Nevora target"),
    mode: str = typer.Option("automation", help="Nevora mode"),
    out: Path = typer.Option(Path("build/batch369"), help="Directory to place 3 variants"),
    pick: int = typer.Option(1, min=1, max=3, help="Preferred variant index (1-3)"),
) -> None:
    """Generate 3 prompt variants (3-6-9 style) and select a preferred winner."""
    variants = [
        {"id": 1, "label": "3", "prompt": f"{prompt}\n\nStyle: minimal runnable MVP."},
        {"id": 2, "label": "6", "prompt": f"{prompt}\n\nStyle: production-friendly structure and docs."},
        {"id": 3, "label": "9", "prompt": f"{prompt}\n\nStyle: extra polish, tests, and developer UX."},
    ]

    results: list[dict[str, Any]] = []
    for v in variants:
        variant_dir = out / f"variant_{v['label']}"
        ok, message = _generate_project(prompt=v["prompt"], target=target, mode=mode, out=variant_dir)
        results.append({"id": v["id"], "label": v["label"], "out": str(variant_dir), "ok": ok, "message": message[:500]})

    chosen = next(r for r in results if r["id"] == pick)
    summary = {
        "prompt": prompt,
        "target": target,
        "mode": mode,
        "variants": results,
        "winner": chosen,
    }
    summary_path = out / "batch_summary.json"
    write_text(summary_path, json.dumps(summary, indent=2) + "\n")
    _audit().write("generate_batch", {"out": str(out), "winner": chosen["out"], "pick": pick})

    console.print(Panel.fit(
        f"✅ Generated 3 variants in {out}\n✅ Winner: {chosen['out']}\n✅ Summary: {summary_path}",
        title="generate-batch",
    ))


@app.command("bounty-plan")
def bounty_plan(
    spec: Path = typer.Option(..., "--spec", help="Spec file (.toml/.json)"),
    out: Path = typer.Option(Path("build/bounty_plan_369.json"), "--out", help="Output plan path"),
) -> None:
    """Create a 3/6/9 bounty plan from a spec (bridge helper for CoEvo workflows)."""
    s = _load_spec(spec)
    plan = {
        "name": s.name,
        "target": s.target,
        "bounties": [
            {"tier": 3, "title": "UI polish / DX tweaks", "reward": 300, "prompt": s.prompt},
            {"tier": 6, "title": "Backend hardening + reliability", "reward": 600, "prompt": s.prompt},
            {"tier": 9, "title": "Deploy + observability", "reward": 900, "prompt": s.prompt},
        ],
    }
    write_text(out, json.dumps(plan, indent=2) + "\n")
    _audit().write("bounty_plan", {"spec": str(spec), "out": str(out)})
    console.print(Panel.fit(f"✅ Wrote 3/6/9 bounty plan: {out}", title="bounty-plan"))


@app.command()
def run(project_dir: Path = typer.Option(Path("build/out"), "--in", help="Project directory to run")) -> None:
    """Run generated project with lightweight auto-detection."""
    if not project_dir.exists() or not project_dir.is_dir():
        raise typer.BadParameter(f"Not a directory: {project_dir}")

    kind = _project_kind(project_dir)
    if kind == "python":
        code = _run_cmd(["python", "main.py"], cwd=project_dir)
    elif kind == "fastapi":
        code = _run_cmd(["uvicorn", "app.main:app", "--reload"], cwd=project_dir)
    elif kind == "vite":
        code = _run_cmd(["npm", "install"], cwd=project_dir)
        if code == 0:
            code = _run_cmd(["npm", "run", "dev"], cwd=project_dir)
    else:
        raise typer.BadParameter("Could not detect project type (expected main.py, app/main.py, or package.json)")

    _audit().write("run", {"in": str(project_dir), "kind": kind, "exit_code": code})
    if code != 0:
        raise typer.Exit(code=code)


@app.command()
def test(project_dir: Path = typer.Option(Path("build/out"), "--in", help="Project directory to test")) -> None:
    """Run tests with lightweight auto-detection."""
    if not project_dir.exists() or not project_dir.is_dir():
        raise typer.BadParameter(f"Not a directory: {project_dir}")

    kind = _project_kind(project_dir)
    if kind in {"python", "fastapi"}:
        if shutil.which("pytest"):
            code = _run_cmd(["pytest"], cwd=project_dir)
            if code == 5:
                console.print("[yellow]No pytest tests collected; falling back to unittest discovery.[/yellow]")
                code = _run_cmd(["python", "-m", "unittest", "discover"], cwd=project_dir)
        else:
            code = _run_cmd(["python", "-m", "unittest", "discover"], cwd=project_dir)
    elif kind == "vite":
        scripts = _package_scripts(project_dir)
        if "test" in scripts:
            code = _run_cmd(["npm", "test"], cwd=project_dir)
        elif "lint" in scripts:
            code = _run_cmd(["npm", "run", "lint"], cwd=project_dir)
        else:
            raise typer.BadParameter("No test/lint script found in package.json")
    else:
        raise typer.BadParameter("Could not detect project type (expected main.py, app/main.py, or package.json)")

    if code == 5:
        console.print("[yellow]No tests discovered; treating as a successful smoke run.[/yellow]")
        code = 0

    _audit().write("test", {"in": str(project_dir), "kind": kind, "exit_code": code})
    if code != 0:
        raise typer.Exit(code=code)


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
    out_zip = zip_dir(in_dir, zip_path)
    _audit().write("pack", {"in": str(in_dir), "zip": str(out_zip), "manifest": str(manifest_path)})
    console.print(Panel.fit(f"✅ Manifest: {manifest_path}\n✅ Zipped {in_dir} → {out_zip}", title="pack"))


@app.command("publish-github")
def publish_github(
    name: str = typer.Option(..., "--name", help="GitHub repository name"),
    project_dir: Path = typer.Option(Path("."), "--in", help="Project directory to publish"),
    private: bool = typer.Option(False, "--private", help="Create a private repository"),
) -> None:
    """Create and push a GitHub repository (uses gh CLI if installed)."""
    if not project_dir.exists() or not project_dir.is_dir():
        raise typer.BadParameter(f"Not a directory: {project_dir}")

    if shutil.which("gh") is None:
        console.print("[yellow]gh CLI not found. Run these commands manually:[/yellow]")
        console.print(
            f"git init\ngit add .\ngit commit -m \"Initial commit\"\n"
            f"gh repo create {name} {'--private' if private else '--public'} --source . --push"
        )
        _audit().write("publish_github", {"in": str(project_dir), "name": name, "mode": "manual"})
        return

    if not (project_dir / ".git").exists():
        _run_cmd(["git", "init"], cwd=project_dir)
    _run_cmd(["git", "add", "."], cwd=project_dir)
    _run_cmd(["git", "commit", "-m", "Initial commit from Triad369 Launchpad"], cwd=project_dir)
    vis = "--private" if private else "--public"
    code = _run_cmd(["gh", "repo", "create", name, vis, "--source", ".", "--push"], cwd=project_dir)
    _audit().write("publish_github", {"in": str(project_dir), "name": name, "exit_code": code})
    if code != 0:
        raise typer.Exit(code=code)


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
def deploy() -> None:
    """Deploy guide (Railway/Render/Vercel)."""
    console.print("[dim]deploy: TODO (non-destructive helper)[/dim]")
