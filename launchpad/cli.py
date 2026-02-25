from __future__ import annotations

import json
import httpx
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
from .packager import build_manifest, verify_manifest_dir, verify_manifest_zip, write_manifest, zip_dir
from .specs import ProjectSpec
from .utils import env, load_json, load_toml, write_text
from .apps.detect import detect_package_manager, detect_stack
from .bridge.contracts import capsule_from_app
from .snapshot import build_snapshot_image, snapshot_rows_from_runtime
from .apps.doctor import doctor_report
from .apps.pack import should_exclude
from .apps.publish import publish_zip_to_coevo
from .apps.registry import AppConfig, app_by_name, ensure_default_registry, load_registry
from .apps.runner import allocate_port, mark_stopped, start_process, update_runtime_running
from .apps.runtime import load_runtime

app = typer.Typer(add_completion=False, help="Triad369 Launchpad — Spec → Generate → Ship")
console = Console()


def _config_root() -> Path:
    return Path(".triad369")


def _audit() -> AuditLog:
    return AuditLog(_config_root())


def _workspace_root() -> Path:
    return _config_root() / "workspace"


def _apps_registry_path() -> Path:
    return _config_root() / "apps.toml"


def _runtime_path() -> Path:
    return _config_root() / "runtime.json"


def _ensure_hub_files() -> list[AppConfig]:
    _workspace_root().mkdir(parents=True, exist_ok=True)
    ensure_default_registry(_apps_registry_path())
    return load_registry(_apps_registry_path())


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


def _generate_project(prompt: str, target: str, mode: str, out: Path) -> tuple[bool, str, str]:
    if nevora_installed():
        res = scaffold_with_nevora(prompt=prompt, target=target, out_dir=out, mode=mode)
        return res.ok, res.message, "nevora"
    res = scaffold_fallback(prompt=prompt, out_dir=out)
    return res.ok, res.message, "fallback"


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
    apps_path = ensure_default_registry(_apps_registry_path())
    _workspace_root().mkdir(parents=True, exist_ok=True)
    _audit().write("init", {"path": str(root / "config.toml"), "apps": str(apps_path)})
    console.print(Panel.fit("✅ Initialized .triad369/config.toml\n✅ Initialized .triad369/apps.toml", title="triad369 init"))


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

    ok, message, engine = _generate_project(prompt=prompt, target=target, mode=mode, out=out)
    if engine == "nevora":
        console.print(f"[bold]Nevora:[/bold] {message[:4000]}")
    else:
        console.print(f"[yellow]Nevora not installed.[/yellow] {message}")

    _audit().write("generate", {"ok": ok, "out": str(out), "target": target, "mode": mode, "engine": engine})
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
        ok, message, engine = _generate_project(prompt=v["prompt"], target=target, mode=mode, out=variant_dir)
        results.append({"id": v["id"], "label": v["label"], "out": str(variant_dir), "ok": ok, "engine": engine, "message": message[:500]})

    chosen = next(r for r in results if r["id"] == pick)
    if not chosen["ok"]:
        _audit().write("generate_batch", {"out": str(out), "winner": chosen["out"], "pick": pick, "ok": False})
        raise typer.Exit(code=2)

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


@app.command("simulate-webhook")
def simulate_webhook(
    payload_path: Path = typer.Option(..., "--payload", help="Webhook payload JSON file"),
    out: Path = typer.Option(Path("build/webhook369"), "--out", help="Output directory"),
    target: str = typer.Option("python", "--target", help="Generation target"),
    mode: str = typer.Option("automation", "--mode", help="Generation mode"),
) -> None:
    """Simulate a CoEvo webhook payload and generate from it."""
    data = load_json(payload_path)
    prompt = str(data.get("prompt") or data.get("title") or "A tiny app from webhook event")
    ok, message, engine = _generate_project(prompt=prompt, target=target, mode=mode, out=out)
    _audit().write("simulate_webhook", {"payload": str(payload_path), "out": str(out), "ok": ok, "engine": engine})
    console.print(
        Panel.fit(
            f"Prompt: {prompt}\nOut: {out}\nEngine: {engine}\nMessage: {message[:500]}",
            title="simulate-webhook",
        )
    )
    if not ok:
        raise typer.Exit(code=2)


@app.command("bridge-thread")
def bridge_thread(
    thread_id: int = typer.Option(..., "--thread-id", help="CoEvo thread ID to bridge"),
    out: Path = typer.Option(Path("build/thread369"), "--out", help="Output directory"),
    target: str = typer.Option("python", "--target", help="Generation target"),
    mode: str = typer.Option("automation", "--mode", help="Generation mode"),
    board: Optional[str] = typer.Option(None, "--board", help="Board slug override (for URL display)"),
) -> None:
    """Fetch a CoEvo thread and generate a scaffold from title + latest post."""
    base_url = _resolve_setting(None, "COEVO_BASE_URL", "coevo_base_url", "http://localhost:8000")
    board_slug = _resolve_setting(board, "COEVO_BOARD_SLUG", "coevo_board_slug", "dev")
    client = CoEvoClient.from_env(base_url_override=base_url)

    thread = client.get_thread(thread_id)
    posts = client.list_thread_posts(thread_id)
    title = str(thread.get("title", f"Thread {thread_id}"))
    latest_post = ""
    if posts:
        latest = posts[-1]
        latest_post = str(latest.get("content_md", ""))

    prompt = f"{title}\n\n{latest_post}".strip()
    ok, message, engine = _generate_project(prompt=prompt, target=target, mode=mode, out=out)

    thread_url = f"{base_url.rstrip('/')}/boards/{board_slug}/threads/{thread_id}"
    _audit().write(
        "bridge_thread",
        {"thread_id": thread_id, "thread_url": thread_url, "out": str(out), "ok": ok, "engine": engine},
    )
    console.print(
        Panel.fit(
            f"Thread: {thread_id}\nURL: {thread_url}\nOut: {out}\nEngine: {engine}\nResult: {message[:500]}",
            title="bridge-thread",
        )
    )
    if not ok:
        raise typer.Exit(code=2)


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
    ok_manifest, errors = verify_manifest_dir(in_dir)
    _audit().write(
        "pack",
        {
            "in": str(in_dir),
            "zip": str(out_zip),
            "manifest": str(manifest_path),
            "manifest_ok": ok_manifest,
            "manifest_errors": errors,
        },
    )
    if not ok_manifest:
        raise typer.BadParameter("Manifest verification failed after packing: " + "; ".join(errors[:3]))
    console.print(Panel.fit(f"✅ Manifest: {manifest_path}\n✅ Zipped {in_dir} → {out_zip}\n✅ Verified manifest hashes", title="pack"))


@app.command("verify-artifact")
def verify_artifact(
    in_dir: Optional[Path] = typer.Option(None, "--in", help="Directory containing artifact.manifest.json"),
    zip_path: Optional[Path] = typer.Option(None, "--zip", help="Zip artifact with manifest"),
) -> None:
    """Verify manifest hashes for a directory or zip artifact."""
    if in_dir is None and zip_path is None:
        raise typer.BadParameter("Provide --in or --zip")

    if in_dir is not None:
        if not in_dir.exists() or not in_dir.is_dir():
            raise typer.BadParameter(f"Not a directory: {in_dir}")
        ok, errors = verify_manifest_dir(in_dir)
        mode = "dir"
        target = str(in_dir)
    else:
        assert zip_path is not None
        if not zip_path.exists() or not zip_path.is_file():
            raise typer.BadParameter(f"Missing zip: {zip_path}")
        ok, errors = verify_manifest_zip(zip_path)
        mode = "zip"
        target = str(zip_path)

    _audit().write("verify_artifact", {"mode": mode, "target": target, "ok": ok, "errors": errors[:10]})
    if not ok:
        detail = "\n".join(errors[:10])
        console.print(Panel.fit(f"❌ Verification failed\n{detail}", title="verify-artifact"))
        raise typer.Exit(code=2)

    console.print(Panel.fit(f"✅ Verified artifact manifest for {target}", title="verify-artifact"))


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
    _run_cmd(["git", "commit", "--allow-empty", "-m", "Initial commit from Triad369 Launchpad"], cwd=project_dir)
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
def deploy(
    project_dir: Path = typer.Option(Path("build/out"), "--in", help="Project directory"),
    provider: str = typer.Option("railway", "--provider", help="railway, render, vercel"),
) -> None:
    """Print non-destructive deploy commands by provider and project type."""
    if not project_dir.exists() or not project_dir.is_dir():
        raise typer.BadParameter(f"Not a directory: {project_dir}")

    kind = _project_kind(project_dir)
    provider = provider.lower().strip()
    lines = [f"Project: {project_dir}", f"Kind: {kind}", f"Provider: {provider}"]

    if provider == "railway":
        lines += [
            "railway login",
            "railway init",
            "railway up",
        ]
    elif provider == "render":
        lines += [
            "Create a new Web Service in Render dashboard",
            "Connect repo and choose build/start commands below",
        ]
    elif provider == "vercel":
        lines += [
            "vercel login",
            "vercel",
            "vercel --prod",
        ]
    else:
        raise typer.BadParameter("Provider must be railway, render, or vercel")

    if kind == "python":
        lines += ["Build: pip install -r requirements.txt", "Start: python main.py"]
    elif kind == "fastapi":
        lines += ["Build: pip install -r requirements.txt", "Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
    elif kind == "vite":
        lines += ["Build: npm install && npm run build", "Start: npm run dev (or serve dist)"]
    else:
        lines += ["Could not auto-detect project type; set build/start commands manually."]

    _audit().write("deploy", {"in": str(project_dir), "provider": provider, "kind": kind})
    console.print(Panel.fit("\n".join(lines), title="deploy"))



apps_app = typer.Typer(help="Launchpad Hub app orchestration")
app.add_typer(apps_app, name="apps")


def _select_apps(name: Optional[str], all_apps: bool) -> list[AppConfig]:
    apps = _ensure_hub_files()
    if all_apps:
        return apps
    if name:
        a = app_by_name(apps, name)
        if not a:
            raise typer.BadParameter(f"Unknown app: {name}")
        return [a]
    raise typer.BadParameter("Provide app name or --all")


@apps_app.command("list")
def apps_list() -> None:
    apps = _ensure_hub_files()
    rt = load_runtime(_runtime_path())
    rows = []
    for a in apps:
        info = rt.get("apps", {}).get(a.name, {}) if isinstance(rt.get("apps", {}), dict) else {}
        running = bool(info.get("running", False))
        port = info.get("port", "-")
        rows.append(f"- {a.name} [{a.app_type}] category={a.category} path={a.path} running={running} port={port} :: {a.description}")
    console.print("\n".join(rows), markup=False)


@apps_app.command("doctor")
def apps_doctor() -> None:
    rep = doctor_report()
    lines = [f"{k}: {'ok' if v else 'missing'}" for k, v in rep.items()]
    console.print(Panel.fit("\n".join(lines), title="apps doctor"))


@apps_app.command("sync")
def apps_sync(name: Optional[str] = typer.Argument(None), all_apps: bool = typer.Option(False, "--all")) -> None:
    apps = _select_apps(name, all_apps)
    ws = _workspace_root()
    for a in apps:
        repo_root = ws / a.path.split("/")[0]
        if not repo_root.exists():
            _run_cmd(["git", "clone", a.repo_url, str(repo_root)], cwd=ws)
        else:
            _run_cmd(["git", "pull"], cwd=repo_root)
    _audit().write("apps_sync", {"apps": [a.name for a in apps]})


@apps_app.command("install")
def apps_install(name: Optional[str] = typer.Argument(None), all_apps: bool = typer.Option(False, "--all")) -> None:
    apps = _select_apps(name, all_apps)
    ws = _workspace_root()
    for a in apps:
        workdir = ws / a.path
        if not workdir.exists():
            console.print(f"[yellow]Skip {a.name}: missing {workdir}[/yellow]")
            continue
        cmd = a.install_cmd.strip()
        if not cmd:
            console.print(f"[yellow]Skip {a.name}: no install_cmd[/yellow]")
            continue
        _run_cmd(cmd.split(), cwd=workdir)
    _audit().write("apps_install", {"apps": [a.name for a in apps]})


@apps_app.command("run")
def apps_run(name: Optional[str] = typer.Argument(None), all_apps: bool = typer.Option(False, "--all")) -> None:
    apps = _select_apps(name, all_apps)
    ws = _workspace_root()
    used: set[int] = set()
    rt = load_runtime(_runtime_path())
    for a in apps:
        workdir = ws / a.path
        if not workdir.exists():
            console.print(f"[yellow]Skip {a.name}: missing {workdir}[/yellow]")
            continue
        if not a.start_cmd.strip():
            console.print(f"[yellow]Skip {a.name}: WIP/no start command[/yellow]")
            continue
        port = allocate_port(a.default_port, a.port_max, used=used)
        used.add(port)
        cmd = a.start_cmd.replace("{PORT}", str(port))
        env = dict(**__import__('os').environ)
        env["PORT"] = str(port)
        log_path = _config_root() / "logs" / f"{a.name}.log"
        proc = start_process(cmd, cwd=workdir, log_path=log_path, env=env)
        update_runtime_running(_runtime_path(), a.name, {
            "pid": proc.pid,
            "port": port,
            "log": str(log_path),
            "running": True,
            "started_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            "path": str(workdir),
        })
        console.print(f"✅ Started {a.name} on {port} (pid {proc.pid})")
    _audit().write("apps_run", {"apps": [a.name for a in apps]})


@apps_app.command("stop")
def apps_stop(name: Optional[str] = typer.Argument(None), all_apps: bool = typer.Option(False, "--all")) -> None:
    rt = load_runtime(_runtime_path())
    all_rt = rt.get("apps", {}) if isinstance(rt.get("apps", {}), dict) else {}
    targets = list(all_rt.keys()) if all_apps else ([name] if name else [])
    if not targets:
        raise typer.BadParameter("Provide app name or --all")
    for n in targets:
        info = all_rt.get(n, {})
        pid = int(info.get("pid", 0)) if isinstance(info, dict) else 0
        if pid > 0:
            try:
                import os, signal
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
        mark_stopped(_runtime_path(), n)
        console.print(f"✅ Stopped {n}")
    _audit().write("apps_stop", {"apps": targets})


@apps_app.command("status")
def apps_status() -> None:
    apps = _ensure_hub_files()
    rt = load_runtime(_runtime_path())
    rows = []
    for a in apps:
        info = (rt.get("apps", {}) or {}).get(a.name, {})
        repo_dir = _workspace_root() / a.path
        detected = detect_stack(repo_dir) if repo_dir.exists() else a.stack_hint or a.app_type
        running = info.get('running', False)
        port = info.get('port', '-')
        health = "-"
        if running and a.capsule_mode == "http" and a.health_path and isinstance(port, int):
            url = f"http://127.0.0.1:{port}{a.health_path}"
            try:
                r = httpx.get(url, timeout=2)
                health = str(r.status_code)
            except Exception:
                health = "down"
        rows.append(
            f"- {a.name}: stack={detected} running={running} pid={info.get('pid', '-')} port={port} health={health}"
        )
    console.print("\n".join(rows) if rows else "No apps configured")


@apps_app.command("open")
def apps_open(name: str) -> None:
    rt = load_runtime(_runtime_path())
    info = (rt.get("apps", {}) or {}).get(name, {})
    port = info.get("port")
    if not port:
        raise typer.BadParameter(f"No runtime port found for {name}")
    url = f"http://127.0.0.1:{port}"
    console.print(url)
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass


@apps_app.command("pack")
def apps_pack(
    name: str,
    out: Path = typer.Option(Path("build"), "--out", help="Zip output file or directory"),
    include_build_output: bool = typer.Option(False, "--include-build-output"),
) -> None:
    apps = _ensure_hub_files()
    a = app_by_name(apps, name)
    if not a:
        raise typer.BadParameter(f"Unknown app: {name}")
    src = _workspace_root() / a.path
    if not src.exists():
        raise typer.BadParameter(f"Missing app directory: {src}")

    tmp = _config_root() / "pack_tmp" / name
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    for p in src.rglob("*"):
        if p.is_dir():
            continue
        rel = str(p.relative_to(src))
        if should_exclude(rel, include_build_output=include_build_output):
            continue
        dest = tmp / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)

    manifest = build_manifest(tmp, project_name=name, target=a.app_type, prompt="")
    write_manifest(tmp, manifest)
    if out.suffix == ".zip":
        zip_path = out
    else:
        zip_path = out / f"{name}.zip"
    zip_dir(tmp, zip_path)
    shutil.rmtree(tmp, ignore_errors=True)
    console.print(f"✅ Packed {name} -> {zip_path}")


@apps_app.command("verify")
def apps_verify(name: str, zip_path: Path = typer.Option(..., "--zip")) -> None:
    apps = _ensure_hub_files()
    if not app_by_name(apps, name):
        raise typer.BadParameter(f"Unknown app: {name}")
    ok, errors = verify_manifest_zip(zip_path)
    if not ok:
        raise typer.BadParameter("; ".join(errors[:5]))
    console.print(f"✅ Verified {name}: {zip_path}")


@apps_app.command("capsule")
def apps_capsule(
    name: str,
    out: Path = typer.Option(Path("build"), "--out", help="Output file or directory"),
) -> None:
    apps = _ensure_hub_files()
    a = app_by_name(apps, name)
    if not a:
        raise typer.BadParameter(f"Unknown app: {name}")
    repo_dir = _workspace_root() / a.path
    detected = detect_stack(repo_dir) if repo_dir.exists() else a.stack_hint or a.app_type
    capsule = capsule_from_app(a, detected_stack=detected)
    if out.suffix == ".json":
        out_path = out
    else:
        out_path = out / f"{name}.capsule.json"
    write_text(out_path, json.dumps(capsule, indent=2) + "\n")
    console.print(f"✅ Capsule written: {out_path}")


@apps_app.command("publish-coevo")
def apps_publish_coevo(
    name: str,
    board: str = typer.Option("dev", "--board"),
    title: str = typer.Option(..., "--title"),
    zip_path: Path = typer.Option(..., "--zip"),
    summary: str = typer.Option("Published via Launchpad Hub", "--summary"),
) -> None:
    apps = _ensure_hub_files()
    a = app_by_name(apps, name)
    if not a:
        raise typer.BadParameter(f"Unknown app: {name}")
    result = publish_zip_to_coevo(zip_path=zip_path, title=title, board=board, summary=summary, repo_url=a.repo_url)
    console.print(Panel.fit(f"✅ Published {name}\nThread: {result['thread_id']}\nArtifact: {result['artifact_id']}", title="apps publish-coevo"))




@app.command("snapshot")
def snapshot(out: Path = typer.Option(Path("build/triad-snapshot.png"), "--out", help="Output PNG path")) -> None:
    """Generate a PNG status card snapshot for Hub apps."""
    apps = _ensure_hub_files()
    rt = load_runtime(_runtime_path())
    rows = snapshot_rows_from_runtime([{"name": a.name, "repo_url": a.repo_url} for a in apps], rt)
    img = build_snapshot_image(out_path=out, title="Triad369 Hub Snapshot", rows=rows)
    console.print(f"✅ Snapshot: {img}")

@app.command()
def up() -> None:
    """Sync + install + run default hub apps."""
    apps = _ensure_hub_files()
    defaults = [a for a in apps if a.enabled_by_default]
    if not defaults:
        console.print("No default apps enabled in apps.toml")
        return
    for a in defaults:
        apps_sync(name=a.name, all_apps=False)
        apps_install(name=a.name, all_apps=False)
    for a in defaults:
        apps_run(name=a.name, all_apps=False)


@app.command()
def down() -> None:
    """Stop all hub-managed apps."""
    apps_stop(name=None, all_apps=True)


@app.command()
def hub() -> None:
    """Show hub URLs + runtime status table."""
    mode = "cloud" if env("STREAMLIT_SERVER_RUNNING") else "local"
    rt = load_runtime(_runtime_path())
    rows = []
    for name, info in (rt.get("apps", {}) or {}).items():
        port = info.get("port")
        url = f"http://127.0.0.1:{port}" if port else "-"
        rows.append(f"- {name}: running={info.get('running', False)} url={url}")
    header = f"Hub mode: {mode}"
    body = "\n".join(rows) if rows else "Hub runtime is empty"
    console.print(Panel.fit(f"{header}\n{body}", title="hub"))
