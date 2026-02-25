from launchpad.apps.runner import allocate_port


def test_allocate_port_respects_used() -> None:
    p = allocate_port(19000, 19005, used={19000, 19001})
    assert p >= 19002
