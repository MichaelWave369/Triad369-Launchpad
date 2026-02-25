from pathlib import Path

from launchpad.apps.registry import ensure_default_registry, load_registry


def test_load_default_registry(tmp_path: Path) -> None:
    path = tmp_path / "apps.toml"
    ensure_default_registry(path)
    apps = load_registry(path)
    assert len(apps) >= 8
    assert any(a.name == "coevo-api" for a in apps)
