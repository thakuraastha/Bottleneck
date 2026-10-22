# BOTTLENECK

Multi-agent supply-chain disruption and recovery system built with Google ADK, CrewAI, FastAPI, vanilla HTML/CSS/JavaScript, SQLAlchemy, and SQLite.

## What works

- Synthetic Motor X7 supplier-delay scenario with repeatable CSV generation and database seeding.
- Four read-only MCP supply-chain tools, daily inventory/production simulation, deterministic risk, strategy scoring, and mandatory constraints.
- Nine typed ADK agents, real graph fan-out/join investigation, and a CrewAI Researcher/Analyst/Reviewer agent reached through A2A JSON-RPC.
- Evidence provenance, explicit conditional routing, bounded replanning, incident memory, and guarded human approval.
- Idempotent event ingestion, 22-table persistence model, FastAPI endpoints, and a responsive operations dashboard.
- ADK agent/model/tool callbacks that validate inputs and persist real execution events, errors, token usage, and security blocks.
- Reproducible evaluations with explicit numerators, denominators, methods, workflow runtime, token counts, and configurable cost estimates.
- Dockerfile and Docker Compose services for the API and dashboard.

The live `/incidents/{id}/run` endpoint requires `GOOGLE_API_KEY` or `GEMINI_API_KEY`. Without a key it returns `503` and creates no fake execution records. The workflow covers triage, parallel specialist investigations, evidence aggregation, deterministic risk, A2A supplier research, strategy planning, reflection, guarded approval, and bounded rejection-triggered replanning.

The default model is `gemini-3.8-flash`; override it with `BOTTLENECK_GEMINI_MODEL` when required.

## Native setup

Python 3.13 is recommended; the maintained CrewAI release used here is not available under Python 3.14.

```bash
/opt/homebrew/bin/python3.13 -m venv .venv313
source .venv313/bin/activate
python -m pip install -e '.[dev,agents]'
python scripts/generate_demo_data.py
PYTHONPATH=backend python scripts/seed_database.py
pytest
```

### One-command demo

After the one-time setup, start both services with:

```bash
./scripts/run_demo.sh
```

Open `http://127.0.0.1:3000`. The faculty presentation sequence and troubleshooting checklist are in [docs/FACULTY_DEMO.md](docs/FACULTY_DEMO.md).

The live requirements matrix is in the dashboard's **Evaluation** tab and at `GET /system/compliance`. Its source-level evidence is documented in [docs/requirements_compliance.md](docs/requirements_compliance.md).

### Start services separately

Start the API and dashboard in separate terminals when developing:

```bash
source .venv313/bin/activate
uvicorn app.api.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

```bash
python -m http.server 3000 --bind 127.0.0.1 --directory frontend/vanilla
```

API documentation is at `http://127.0.0.1:8000/docs`. The complete frontend is intentionally kept in three framework-free files: `frontend/vanilla/index.html`, `styles.css`, and `app.js`.

## Docker Compose

```bash
docker compose up --build
```

The API seeds the persistent Docker volume only when no suppliers exist. Set `GOOGLE_API_KEY` or `GEMINI_API_KEY` in the shell or an untracked `.env` file to enable live model execution. Never commit credentials.

Open `http://127.0.0.1:3000` after both containers become healthy.

## Cloud deployment

The repository includes a Vercel container deployment (`Dockerfile.vercel` + `vercel.json`) and a Render Blueprint (`render.yaml`). The FastAPI container also serves the dashboard at `/`, so a cloud deployment has one public URL. Configure `GEMINI_API_KEY` in the platform's encrypted environment settings; never commit it.

## Verification

```bash
pytest -q
node --check frontend/vanilla/app.js
docker compose config --quiet
```

See [requirements compliance](docs/requirements_compliance.md), [architecture](docs/architecture.md), [agent design](docs/agent_design.md), [observability](docs/observability.md), [evaluation](docs/evaluation.md), and the [implementation plan](docs/implementation_plan.md).
