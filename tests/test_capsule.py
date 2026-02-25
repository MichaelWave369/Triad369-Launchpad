from launchpad.apps.registry import AppConfig
from launchpad.bridge.contracts import capsule_from_app


def test_capsule_schema() -> None:
    app = AppConfig(
        name="demo",
        repo_url="https://github.com/x/y.git",
        app_type="python",
        path="demo",
        default_port=8000,
        port_max=8010,
        start_cmd="python main.py",
        capsule_mode="http",
    )
    capsule = capsule_from_app(app, detected_stack="python")
    for key in ["name", "repo_url", "stack", "entrypoints", "recommended_ports", "tags", "capabilities", "capsule_mode"]:
        assert key in capsule
