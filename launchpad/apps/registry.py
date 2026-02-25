from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..utils import load_toml, write_text


@dataclass
class AppConfig:
    name: str
    repo_url: str
    app_type: str
    path: str
    default_port: int
    port_max: int
    category: str = "app"
    stack_hint: str = ""
    start_cmd: str = ""
    install_cmd: str = ""
    test_cmd: str = ""
    build_cmd: str = ""
    health_path: str = ""
    package_manager: str = ""
    python_entrypoint: str = ""
    capsule_mode: str = "http"
    description: str = ""
    enabled_by_default: bool = True


def _default_registry() -> str:
    return '''# Triad369 Launchpad Hub app registry
# Edit commands/ports as needed for your local setup.

[[apps]]
name = "coevo-api"
repo_url = "https://github.com/MichaelWave369/CoEvo.git"
category = "coevo"
app_type = "fastapi"
stack_hint = "fastapi"
path = "CoEvo/server"
default_port = 8000
port_max = 8019
start_cmd = "uvicorn app.main:app --reload --host 127.0.0.1 --port {PORT}"
install_cmd = "python -m pip install -r requirements.txt"
test_cmd = "python -m pytest"
health_path = "/health"
python_entrypoint = "app.main:app"
capsule_mode = "http"
description = "CoEvo backend API"
enabled_by_default = true

[[apps]]
name = "coevo-web"
repo_url = "https://github.com/MichaelWave369/CoEvo.git"
category = "coevo"
app_type = "vite"
stack_hint = "vite"
path = "CoEvo/web"
default_port = 5173
port_max = 5199
start_cmd = "npm run dev -- --host 127.0.0.1 --port {PORT}"
install_cmd = "npm install"
build_cmd = "npm run build"
package_manager = "npm"
capsule_mode = "http"
description = "CoEvo frontend web app"
enabled_by_default = true

[[apps]]
name = "nevora-translator"
repo_url = "https://github.com/MichaelWave369/Nevora-Translator.git"
category = "nevora"
app_type = "python-cli"
stack_hint = "python-cli"
path = "Nevora-Translator"
default_port = 8040
port_max = 8059
start_cmd = "python -m translator.cli --help"
install_cmd = "python -m pip install -e ."
test_cmd = "python -m pytest"
python_entrypoint = "translator.cli"
capsule_mode = "static"
description = "Nevora translator CLI"
enabled_by_default = false

[[apps]]
name = "reconnect"
repo_url = "https://github.com/MichaelWave369/Reconnect.git"
category = "reconnect"
app_type = "python"
stack_hint = "fastapi"
path = "Reconnect"
default_port = 8010
port_max = 8029
start_cmd = "python main.py"
install_cmd = "python -m pip install -r requirements.txt"
health_path = "/health"
capsule_mode = "http"
description = "Reconnect local-first backend"
enabled_by_default = false

[[apps]]
name = "recom3ndo"
repo_url = "https://github.com/MichaelWave369/RecoM3ndo.git"
category = "recom3ndo"
app_type = "static"
stack_hint = "static"
path = "RecoM3ndo"
default_port = 8030
port_max = 8049
start_cmd = "python -m http.server {PORT} --bind 127.0.0.1"
capsule_mode = "static"
description = "RecoM3ndo static web app"
enabled_by_default = false

[[apps]]
name = "aidora"
repo_url = "https://github.com/MichaelWave369/Aidora.git"
category = "aidora"
app_type = "vite"
stack_hint = "vite"
path = "Aidora"
default_port = 5174
port_max = 5199
start_cmd = "pnpm dev -- --host 127.0.0.1 --port {PORT}"
install_cmd = "pnpm install"
build_cmd = "pnpm build"
package_manager = "pnpm"
capsule_mode = "http"
description = "Aidora React+TS app"
enabled_by_default = false

[[apps]]
name = "mindora"
repo_url = "https://github.com/MichaelWave369/Mindora.git"
category = "mindora"
app_type = "next"
stack_hint = "next"
path = "Mindora"
default_port = 3000
port_max = 3019
start_cmd = "pnpm dev -p {PORT}"
install_cmd = "pnpm install"
build_cmd = "pnpm build"
package_manager = "pnpm"
capsule_mode = "http"
description = "Mindora Next.js app"
enabled_by_default = false

[[apps]]
name = "gypsyai"
repo_url = "https://github.com/MichaelWave369/GypsyAI.git"
category = "gypsyai"
app_type = "next"
stack_hint = "next"
path = "GypsyAI"
default_port = 3001
port_max = 3029
start_cmd = "pnpm dev -p {PORT}"
install_cmd = "pnpm install"
build_cmd = "pnpm build"
package_manager = "pnpm"
capsule_mode = "http"
description = "GypsyAI Next.js app"
enabled_by_default = false

[[apps]]
name = "growora"
repo_url = "https://github.com/MichaelWave369/Growora.git"
category = "growora"
app_type = "wip"
stack_hint = "wip"
path = "Growora"
default_port = 8060
port_max = 8079
capsule_mode = "wip"
description = "Growora WIP placeholder"
enabled_by_default = false
'''


def ensure_default_registry(path: Path) -> Path:
    if not path.exists():
        write_text(path, _default_registry())
    return path


def load_registry(path: Path) -> list[AppConfig]:
    data = load_toml(path)
    rows = data.get("apps", [])
    apps: list[AppConfig] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        apps.append(
            AppConfig(
                name=str(r.get("name", "")),
                repo_url=str(r.get("repo_url", "")),
                app_type=str(r.get("app_type", "unknown")),
                path=str(r.get("path", "")),
                default_port=int(r.get("default_port", 0)),
                port_max=int(r.get("port_max", int(r.get("default_port", 0)))),
                category=str(r.get("category", "app")),
                stack_hint=str(r.get("stack_hint", "")),
                start_cmd=str(r.get("start_cmd", "")),
                install_cmd=str(r.get("install_cmd", "")),
                test_cmd=str(r.get("test_cmd", "")),
                build_cmd=str(r.get("build_cmd", "")),
                health_path=str(r.get("health_path", "")),
                package_manager=str(r.get("package_manager", "")),
                python_entrypoint=str(r.get("python_entrypoint", "")),
                capsule_mode=str(r.get("capsule_mode", "http")),
                description=str(r.get("description", "")),
                enabled_by_default=bool(r.get("enabled_by_default", True)),
            )
        )
    return apps


def app_by_name(apps: list[AppConfig], name: str) -> AppConfig | None:
    for a in apps:
        if a.name == name:
            return a
    return None
