from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import subprocess
import sys

from .utils import env


@dataclass(frozen=True)
class NevoraResult:
    ok: bool
    output_dir: Path
    message: str


def nevora_installed() -> bool:
    try:
        __import__("translator")  # Nevora package
        return True
    except Exception:
        return False


def scaffold_with_nevora(prompt: str, target: str, out_dir: Path, mode: str = "automation") -> NevoraResult:
    """Calls Nevora's CLI to scaffold a project into out_dir.

    Requires Nevora to be installed (pip install -e ../Nevora-Translator).
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Allow override if user wants a different python or module command
    cmd = env("NEVORA_CLI_CMD", "").strip()
    if cmd:
        base = cmd.split()
    else:
        base = [sys.executable, "-m", "translator.cli"]

    args = base + [
        "--target", target,
        "--prompt", prompt,
        "--mode", mode,
        "--scaffold-dir", str(out_dir),
    ]

    try:
        r = subprocess.run(args, capture_output=True, text=True, check=False)
        ok = (r.returncode == 0)
        msg = r.stdout.strip() or r.stderr.strip() or "Nevora finished."
        return NevoraResult(ok=ok, output_dir=out_dir, message=msg)
    except FileNotFoundError as e:
        return NevoraResult(ok=False, output_dir=out_dir, message=f"Nevora command not found: {e}")


def scaffold_fallback(prompt: str, out_dir: Path) -> NevoraResult:
    """Fallback scaffold so the pipeline works even if Nevora isn't installed."""
    out_dir.mkdir(parents=True, exist_ok=True)
    main_py = out_dir / "main.py"
    escaped_prompt = prompt.replace("'", "\\'")
    content = (
        "def main():\n"
        "    print('Hello 369!')\n"
        f"    print('Prompt: {escaped_prompt}')\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    main_py.write_text(content, encoding="utf-8")
    (out_dir / "README.md").write_text(
        "# Fallback Scaffold\n\n"
        "Nevora wasn't available, so Launchpad generated a tiny runnable project.\n",
        encoding="utf-8",
    )
    return NevoraResult(ok=True, output_dir=out_dir, message="Fallback scaffold created (Nevora not installed).")
