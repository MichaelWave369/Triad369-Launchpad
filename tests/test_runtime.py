from pathlib import Path

from launchpad.apps.runtime import load_runtime, save_runtime


def test_runtime_rw(tmp_path: Path) -> None:
    path = tmp_path / "runtime.json"
    data = {"apps": {"x": {"running": True}}}
    save_runtime(path, data)
    loaded = load_runtime(path)
    assert loaded["apps"]["x"]["running"] is True
