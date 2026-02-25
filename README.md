# Triad369-Launchpad (Triad Hub)

**Triad369-Launchpad** is the **local-first hub** that connects and orchestrates your Triad ecosystem: it can **sync**, **inspect**, **package**, and (optionally) **publish** your other apps from one place.

- **Default:** local-first + offline-friendly (no telemetry, no scraping)
- **Modes:**
  - **Local Hub (CLI):** manage repos on your machine
  - **Streamlit Hub (Dashboard):** cloud-safe UI for browsing/exporting/snapshotting (no long-running subprocess orchestration in cloud)

---

## What it does

### Hub Orchestration
- Sync (clone/pull) multiple GitHub repos into a local workspace
- Detect each repo’s stack (Python / FastAPI / Streamlit / Next.js / Vite / static)
- Show status + recommended run commands

### Packaging
- Build consistent **artifact ZIPs** for any registered app
- Output an `artifact.manifest.json` with checksums
- Exclude junk folders like `.git/`, `node_modules/`, `.venv/`, caches, local DBs

### Optional Publishing (CoEvo)
- If configured, Launchpad can publish packaged artifacts to CoEvo
- Publishing is **opt-in** and requires explicit environment variables

### Snapshot (PNG)
- Generate a downloadable **status-card image** (PNG) summarizing your Hub state

---

## Quickstart (Local Hub)

### Requirements
- Python 3.12+
- Poetry
- Git

### Install
```bash
poetry install
```

### Initialize + inspect
```bash
poetry run triad369 init
poetry run triad369 apps doctor
poetry run triad369 apps list
```

### Sync workspace
```bash
poetry run triad369 apps sync --all
```

### Package a registered app
```bash
poetry run triad369 apps pack coevo-api --out build/coevo-api.zip
poetry run triad369 apps verify coevo-api --zip build/coevo-api.zip
```

### Generate a Hub snapshot image
```bash
poetry run triad369 snapshot --out build/triad-snapshot.png
```

---

## Streamlit Hub (Cloud-safe)

Run locally:

```bash
poetry run streamlit run streamlit_app.py
```

### Streamlit Cloud settings
- **Main file path must be:** `streamlit_app.py`
- Keep `.streamlit/config.toml` in repo
- Keep `requirements.txt` using `-e .[streamlit]`

### Cloud mode behavior
In constrained cloud environments, the dashboard is intentionally safe:
- shows app metadata and links
- supports capsule export + snapshot download
- does **not** start long-running local subprocess fleets by default

---

## App Registry

Launchpad uses a registry file at:

- `.triad369/apps.toml`

Each app entry can define:
- name + repo URL
- stack hints and health path
- default ports
- install/run/test/build commands
- packaging and capsule behavior

---

## Optional CoEvo publish

When `COEVO_*` environment variables are configured, you can publish packaged artifacts:

```bash
poetry run triad369 apps publish-coevo coevo-api --board dev --title "CoEvo package" --zip build/coevo-api.zip
```

---

## Troubleshooting

### Poetry install/package issues
If packaging fails, confirm `pyproject.toml` includes:

- `[tool.poetry]`
- `packages = [{ include = "launchpad" }]`

Then run:

```bash
poetry check
poetry install
```

### TOML parse check
```bash
python -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('TOML OK')"
```

### Streamlit Cloud wrong entrypoint
If Cloud points to `launchpad/__init__.py`, change it to `streamlit_app.py`.

### Lockfile mismatch
```bash
poetry lock
poetry install
```

---

## License
MIT
