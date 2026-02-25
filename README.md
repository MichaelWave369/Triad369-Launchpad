# Triad369 Launchpad ⚡️ (Spec → Generate → Ship)

Your **3rd pillar** repo to complete the 3-6-9 triad:

1) **CoEvo** = co-creation, bounties, threads, artifacts  
2) **Nevora** = natural-language → starter code  
3) **Triad369 Launchpad** = turns Nevora output into a *shippable project* and publishes it to CoEvo

**Goal:** one command to go from *idea/spec* → *project scaffold* → *zip artifact* → *CoEvo thread* (+ optional repo link).

---

## Quickstart (local)

### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip setuptools wheel build twine
python -m pip install -e .

triad369 init
triad369 generate --prompt "A tiny CLI that prints Hello 369" --target python --out build/hello369
triad369 pack --in build/hello369 --zip build/hello369.zip
# writes + verifies build/hello369/artifact.manifest.json (manifest does not hash itself)
triad369 verify-artifact --in build/hello369
triad369 verify-artifact --zip build/hello369.zip
python -m build
python -m twine check dist/*
```

### macOS/Linux (bash/zsh)
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel build twine
python -m pip install -e .

triad369 init
triad369 generate --prompt "A tiny CLI that prints Hello 369" --target python --out build/hello369
triad369 pack --in build/hello369 --zip build/hello369.zip
# writes + verifies build/hello369/artifact.manifest.json (manifest does not hash itself)
triad369 verify-artifact --in build/hello369
triad369 verify-artifact --zip build/hello369.zip
python -m build
python -m twine check dist/*
```

---


### Python compatibility
- Python 3.11+ uses the standard-library `tomllib`.
- Python 3.10 automatically uses `tomli` (installed via package dependency).

## Config layering (3-6-9 priority)

1. `.triad369/config.toml` defaults
2. Environment variables override config
3. CLI flags override both

## CoEvo publish (optional, but supported)

This repo ships a **CoEvo API client** that:
- logs in (`/api/auth/login`)
- lists boards (`/api/boards`)
- creates a thread (`POST /api/boards/{board_id}/threads`)
- uploads a zip (`POST /api/artifacts/upload`)
- attaches it to the thread (`POST /api/artifacts/{artifact_id}/attach/thread/{thread_id}`)
- optionally adds a repo link (`POST /api/repos`)

Those endpoints exist in your CoEvo server today. (See CoEvo router files.)

### Configure
Set env vars (or put them in your shell profile):

```bash
# required
set COEVO_BASE_URL=http://localhost:8000
set COEVO_HANDLE=admin
set COEVO_PASSWORD=change-me

# optional
set COEVO_WEBHOOK_SECRET=   # only if you set it in CoEvo server
```

### Publish
```bash
triad369 publish-coevo --board dev --title "Hello 369 demo" --in build/hello369
# or provide --zip build/hello369.zip if already packed
# optional repo tags: --tags "369,launchpad"
```

---

## Nevora integration options

Launchpad supports **two** ways to use Nevora:

### A) CLI adapter (recommended)
Install Nevora locally (e.g. in a sibling folder), then:

```bash
pip install -e ../Nevora-Translator
```

Launchpad will call:

```bash
python -m translator.cli --target <target> --prompt "<prompt>" --scaffold-dir <out>
```

### B) Fallback (works even without Nevora)
If Nevora isn't installed, Launchpad generates a minimal scaffold (so the pipeline still works).

---

## 3-6-9 structure (built-in)

**3 Modes:** Build • Share • Ship  
**6 Modules:** Spec • Nevora • Packager • CoEvo • Deploy • Audit  
**9 Commands:** init • generate • run • test • pack • publish-github • publish-coevo • deploy • status

Core commands are now implemented for day-to-day Spec → Generate → Run/Test → Pack → Publish flow.

---

## Example specs

- `examples/spec_python_cli.toml`
- `examples/spec_fastapi.toml`
- `examples/spec_react_vite.toml`

Use them like:

```bash
triad369 generate --spec examples/spec_python_cli.toml --out build/myapp
triad369 pack --in build/myapp --zip build/myapp.zip
```

---


## Run, test, and publish GitHub (v0.3)

```bash
# Run with auto-detection
triad369 run --in build/hello369

# Test with auto-detection (pytest if available, otherwise unittest)
triad369 test --in build/hello369

# Publish to GitHub (uses gh CLI if installed; otherwise prints manual commands)
triad369 publish-github --name your-org/hello369 --in build/hello369

# Verify directory/zip artifacts against artifact.manifest.json
triad369 verify-artifact --in build/hello369
triad369 verify-artifact --zip build/hello369.zip

# Print non-destructive deploy guide commands
triad369 deploy --in build/hello369 --provider railway
```


## Bridge helpers (v0.4)

```bash
# Generate 3 variants (3/6/9 style) and pick preferred winner
triad369 generate-batch --prompt "A tiny CLI that prints Hello 369" --target python --out build/batch369 --pick 1

# Create a 3/6/9 bounty plan from a spec for CoEvo workflows
triad369 bounty-plan --spec examples/spec_python_cli.toml --out build/bounty_plan_369.json

# Simulate a webhook event payload and generate automatically
triad369 simulate-webhook --payload examples/webhook_payload.json --out build/webhook369

# Bridge an existing CoEvo thread into a generated scaffold
triad369 bridge-thread --thread-id 123 --out build/thread369 --target python
```


## Launchpad Hub (v1.0)

Triad369-Launchpad now includes a local-first **workspace orchestrator** for your other apps.

### Hub quickstart
```bash
triad369 init
triad369 apps doctor
triad369 apps list
triad369 up
triad369 hub
triad369 down
```

### Workspace + registry
- Workspace root: `.triad369/workspace/`
- App registry: `.triad369/apps.toml`
- Runtime state: `.triad369/runtime.json`

To add/update an app, edit `.triad369/apps.toml` with name/repo/type/port ranges and commands.

### Core Hub commands
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
triad369 apps publish-coevo coevo-api --board dev --title "CoEvo package" --zip build/coevo-api.zip
```

### Safety defaults
- Local-first by default (no hidden telemetry/scraping).
- Network calls are explicit (`git clone/pull` and optional CoEvo publish).
- Port allocation is collision-aware within configured app port ranges.

## Validation smoke script

```bash
python scripts/smoke_checks.py
```

## Roadmap (v0.x)

- [ ] Add “publish-github” (create repo + push) using a personal access token
- [ ] Add deploy helpers for Railway/Render/Vercel (non-destructive, guide-only)
- [ ] Add Nevora “batch” mode: generate 3 options → pick best
- [ ] Add CoEvo bounty auto-creation with 3/6/9 reward presets

---

## License
MIT (same vibe as your other repos).
