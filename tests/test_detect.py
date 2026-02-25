from pathlib import Path

from launchpad.apps.detect import detect_package_manager, detect_stack


def test_detect_stack_next(tmp_path: Path) -> None:
    (tmp_path / "next.config.js").write_text("", encoding="utf-8")
    assert detect_stack(tmp_path) == "next"


def test_detect_package_manager(tmp_path: Path) -> None:
    (tmp_path / "pnpm-lock.yaml").write_text("", encoding="utf-8")
    assert detect_package_manager(tmp_path) == "pnpm"
