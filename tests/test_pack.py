from launchpad.apps.pack import should_exclude


def test_pack_exclude_rules() -> None:
    assert should_exclude("node_modules/a.js")
    assert should_exclude(".git/config")
    assert not should_exclude("src/main.py")
