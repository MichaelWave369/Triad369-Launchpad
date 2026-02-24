from __future__ import annotations

import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from launchpad.cli import app
from launchpad.nevora_bridge import scaffold_fallback
from launchpad.packager import zip_dir
from typer.testing import CliRunner


def main() -> None:
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        scaffold_dir = base / "fallback"
        scaffold_fallback("A tiny CLI that prints Hello 369", scaffold_dir)
        assert (scaffold_dir / "main.py").exists(), "fallback scaffold must create main.py"

        zip_path = base / "artifact.zip"
        zip_dir(scaffold_dir, zip_path)
        assert zip_path.exists() and zip_path.stat().st_size > 0, "zip_dir must produce non-empty zip"

        with runner.isolated_filesystem(temp_dir=str(base)):
            result = runner.invoke(app, ["init"], catch_exceptions=False)
            assert result.exit_code == 0, result.output
            assert Path(".triad369/config.toml").exists(), "init must create .triad369/config.toml"


if __name__ == "__main__":
    main()
    print("smoke_checks: OK")
