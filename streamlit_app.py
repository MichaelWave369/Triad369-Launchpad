from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from launchpad.apps.registry import AppConfig, ensure_default_registry, load_registry
from launchpad.apps.runtime import load_runtime
from launchpad.bridge.contracts import capsule_from_app
from launchpad.snapshot import build_snapshot_image, snapshot_rows_from_runtime


CONFIG_ROOT = Path('.triad369')
WORKSPACE = CONFIG_ROOT / 'workspace'
APPS_PATH = CONFIG_ROOT / 'apps.toml'
RUNTIME_PATH = CONFIG_ROOT / 'runtime.json'


def _is_cloud_mode() -> bool:
    import os

    if os.getenv("STREAMLIT_CLOUD", "").lower() in {"1", "true", "yes"}:
        return True
    if st.secrets.get("FORCE_LOCAL_MODE", False):
        return False
    return os.getenv("CI", "").lower() == "true"


def _archive_link(repo_url: str) -> str:
    url = repo_url.removesuffix('.git')
    return f"{url}/archive/refs/heads/main.zip"


def _load_apps() -> list[AppConfig]:
    CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    ensure_default_registry(APPS_PATH)
    return load_registry(APPS_PATH)


def main() -> None:
    st.set_page_config(page_title='Triad369 Hub', layout='wide')
    st.title('Triad369 Hub')

    apps = _load_apps()
    runtime = load_runtime(RUNTIME_PATH)

    cloud_mode = _is_cloud_mode()
    local_mode = False
    if cloud_mode:
        st.info('Cloud Mode: run/install actions are disabled. You can export capsules and snapshots.')
    else:
        st.success('Local Mode available.')
        local_mode = st.checkbox('Enable Local Mode actions (advanced)', value=False)

    st.subheader('Apps')
    for a in apps:
        info = (runtime.get('apps', {}) or {}).get(a.name, {})
        running = bool(info.get('running', False))
        port = info.get('port', '-')
        with st.expander(f"{a.name} [{a.app_type}] — running={running} port={port}"):
            st.write(a.description or '-')
            st.markdown(f"Repo: {a.repo_url}")
            st.link_button('Open repo', a.repo_url)
            st.link_button('Download source zip', _archive_link(a.repo_url))

            capsule = capsule_from_app(a, detected_stack=a.stack_hint or a.app_type)
            st.download_button(
                label='Download Capsule JSON',
                data=json.dumps(capsule, indent=2),
                file_name=f"{a.name}.capsule.json",
                mime='application/json',
            )

            if local_mode and not cloud_mode:
                st.caption('Use CLI for local orchestration (sync/install/run/stop).')

    st.subheader('Snapshot')
    rows = snapshot_rows_from_runtime([{"name": a.name, "repo_url": a.repo_url} for a in apps], runtime)
    if st.button('Generate Snapshot'):
        out = Path('build/triad-snapshot.png')
        build_snapshot_image(out_path=out, title='Triad369 Hub Snapshot', rows=rows)
        data = out.read_bytes()
        st.success(f'Generated {out}')
        st.download_button('Download Snapshot PNG', data=data, file_name='triad-snapshot.png', mime='image/png')

    st.subheader('CoEvo Publish')
    st.caption('Optional. Requires COEVO_* env vars and should be run locally via CLI.')
    st.code('triad369 apps publish-coevo <name> --board dev --title "..." --zip build/<name>.zip')


if __name__ == '__main__':
    main()
