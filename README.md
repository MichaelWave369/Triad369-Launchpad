# Triad369 Launchpad Hub ⚡️

Triad369 Launchpad is now a **local-first hub/orchestrator/packager/publisher** for your connected apps.

It supports:
- Spec → Generate → Pack → Publish workflows
- App workspace orchestration via `triad369 apps ...`
- Manifest-based artifact integrity (`artifact.manifest.json` + verification)
- Optional CoEvo publishing
- Streamlit dashboard mode (cloud-safe)

---

## What Launchpad Hub does

### 1) Hub Orchestration (local-first)
- Registry-driven app management (`.triad369/apps.toml`)
- Workspace sync to `.triad369/workspace/`
- App lifecycle helpers: list/sync/install/run/stop/status/open
- Port-safe runtime tracking in `.triad369/runtime.json`

### 2) Packaging + Verification
- Standardized zip packaging
- `artifact.manifest.json` with SHA256 hashes
- Directory and zip verification commands

### 3) Optional CoEvo publishing
- Package zip upload + thread publish via configured `COEVO_*` env vars
- No hidden outbound calls (network is explicit: git + optional CoEvo)

### 4) Streamlit cloud-safe UI
- Entry point: `streamlit_app.py`
- Cloud mode avoids long-running subprocess orchestration
- Supports repo links, source zip links, capsule export, snapshot export

---

## Quickstart (CLI)

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e .[streamlit]

# Initialize config + registry + workspace
triad369 init

# Hub checks
triad369 apps doctor
triad369 apps list

# Default orchestrator flow
triad369 up
triad369 hub
triad369 down
```

---

## Core Hub commands

```bash
triad369 apps list
triad369 apps sync --all
triad369 apps install --all
triad369 apps run --all
triad369 apps stop --all
triad369 apps status
triad369 apps open coevo-api

triad369 apps pack coevo-api --out build/coevo-api.zip
triad369 apps verify coevo-api --zip build/coevo-api.zip
triad369 apps capsule coevo-api --out build/coevo-api.capsule.json
triad369 apps publish-coevo coevo-api --board dev --title "CoEvo package" --zip build/coevo-api.zip
```

Top-level helpers:

```bash
triad369 snapshot --out build/triad-snapshot.png
triad369 verify-artifact --zip build/hello369.zip
```

---

## Streamlit Mode

### Local run
```bash
pip install -e .[streamlit]
streamlit run streamlit_app.py
```

### Streamlit Cloud deploy checklist
1. Main file path: **`streamlit_app.py`** (not `launchpad/__init__.py`)
2. `requirements.txt` should contain `-e .[streamlit]`
3. Keep `.streamlit/config.toml` committed

### Cloud mode limitations
- No subprocess farm orchestration by default
- Use cloud-safe actions only:
  - repo links
  - source zip links
  - capsule export JSON
  - snapshot PNG generation/download

---

## App Registry Concept

The hub registry lives at:
- `.triad369/apps.toml`

Each app entry defines core metadata such as:
- name, repo URL, app type
- stack hints, capsule mode
- default port range
- install/start/test/build commands
- optional health path

You can edit this file to add/adjust apps and commands safely.

---

## Packaging + CoEvo publishing

```bash
triad369 generate --prompt "A tiny CLI that prints Hello 369" --target python --out build/hello369
triad369 pack --in build/hello369 --zip build/hello369.zip
triad369 verify-artifact --zip build/hello369.zip

# Optional if COEVO_* env vars are set
triad369 publish-coevo --board dev --title "Hello 369 demo" --zip build/hello369.zip
```

---

## Troubleshooting

### Poetry install error: package not found
- Ensure `pyproject.toml` includes:
  - `[tool.poetry]`
  - `packages = [{ include = "launchpad" }]`
- Then run:
  - `poetry check`
  - `poetry install`

### TOML parse errors
- Validate quickly:
```bash
python -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('TOML OK')"
```

### Streamlit Cloud wrong entrypoint
- If Cloud points to `launchpad/__init__.py`, change it to `streamlit_app.py`.

### Lockfile mismatch
- Rebuild lockfile:
```bash
poetry lock
poetry install
```

---

## License
MIT
