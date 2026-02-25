from pathlib import Path

from launchpad.snapshot import build_snapshot_image


def test_snapshot_png_creation(tmp_path: Path) -> None:
    out = tmp_path / "snap.png"
    build_snapshot_image(out_path=out, title="Triad Snapshot", rows=["a", "b"]) 
    assert out.exists()
    assert out.stat().st_size > 0
