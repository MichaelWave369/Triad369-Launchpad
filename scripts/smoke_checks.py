from __future__ import annotations

import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from launchpad.cli import app
from launchpad.nevora_bridge import scaffold_fallback
from launchpad.packager import build_manifest, write_manifest, zip_dir
from typer.testing import CliRunner


def main() -> None:
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        scaffold_dir = base / "fallback"
        scaffold_fallback("A tiny CLI that prints Hello 369", scaffold_dir)
        assert (scaffold_dir / "main.py").exists(), "fallback scaffold must create main.py"

        manifest = build_manifest(scaffold_dir, project_name="fallback", target="python", prompt="hello")
        manifest_path = write_manifest(scaffold_dir, manifest)
        assert manifest_path.exists(), "packager must write artifact.manifest.json"

        zip_path = base / "artifact.zip"
        zip_dir(scaffold_dir, zip_path)
        assert zip_path.exists() and zip_path.stat().st_size > 0, "zip_dir must produce non-empty zip"

        run_result = runner.invoke(app, ["run", "--in", str(scaffold_dir)], catch_exceptions=False)
        assert run_result.exit_code == 0, run_result.output

        batch_dir = base / "batch"
        batch_result = runner.invoke(
            app,
            [
                "generate-batch",
                "--prompt",
                "A tiny CLI that prints Hello 369",
                "--target",
                "python",
                "--out",
                str(batch_dir),
            ],
            catch_exceptions=False,
        )
        assert batch_result.exit_code == 0, batch_result.output
        assert (batch_dir / "batch_summary.json").exists(), "generate-batch must write batch_summary.json"

        webhook_payload = base / "webhook.json"
        webhook_payload.write_text("{\"title\": \"Webhook 369\", \"prompt\": \"Build me a tiny 369 CLI\"}\n", encoding="utf-8")
        webhook_result = runner.invoke(
            app,
            ["simulate-webhook", "--payload", str(webhook_payload), "--out", str(base / "webhook_out")],
            catch_exceptions=False,
        )
        assert webhook_result.exit_code == 0, webhook_result.output
        assert (base / "webhook_out" / "main.py").exists(), "simulate-webhook must generate scaffold"

        bounty_out = base / "bounty_plan_369.json"
        spec_path = ROOT / "examples" / "spec_python_cli.toml"
        bounty_result = runner.invoke(
            app,
            ["bounty-plan", "--spec", str(spec_path), "--out", str(bounty_out)],
            catch_exceptions=False,
        )
        assert bounty_result.exit_code == 0, bounty_result.output
        assert bounty_out.exists(), "bounty-plan must write output file"

        with runner.isolated_filesystem(temp_dir=str(base)):
            result = runner.invoke(app, ["init"], catch_exceptions=False)
            assert result.exit_code == 0, result.output
            assert Path(".triad369/config.toml").exists(), "init must create .triad369/config.toml"


if __name__ == "__main__":
    main()
    print("smoke_checks: OK")
