# BOTTLENECK

Multi-agent supply-chain disruption and recovery system built with Google ADK, CrewAI, FastAPI, vanilla HTML/CSS/JavaScript, SQLAlchemy, and SQLite.

## What works

- Synthetic Motor X7 supplier-delay scenario with repeatable CSV generation and database seeding.
- Four read-only MCP supply-chain tools, daily inventory/production simulation, deterministic risk, strategy scoring, and mandatory constraints.
- Typed ADK agents with parallel fan-out/join investigation and an ADK session-state supervisor, plus a CrewAI Researcher/Analyst/Reviewer crew reached through A2A JSON-RPC.
- Live frontend cards expose every persisted ADK and CrewAI output while the workflow is running.
- Evidence provenance, explicit conditional routing, bounded replanning, incident memory, and guarded human approval.
- Idempotent event ingestion, 22-table persistence model, FastAPI endpoints, and a responsive operations dashboard.
- ADK agent/model/tool callbacks that validate inputs and persist real execution events, errors, token usage, and security blocks.
- Reproducible evaluations with explicit numerators, denominators, methods, workflow runtime, token counts, and configurable cost estimates.
- Dockerfile and Docker Compose services for the API and dashboard.

The live `/incidents/{id}/run` endpoint requires `GOOGLE_API_KEY` or `GEMINI_API_KEY`. Without a key it returns `503` and creates no fake execution records. The workflow covers triage, parallel specialist investigations, evidence aggregation, deterministic risk, A2A supplier research, strategy planning, reflection, guarded approval, and bounded rejection-triggered replanning.

Parallel ADK investigation uses `BOTTLENECK_GEMINI_MODEL`, later sequential ADK stages use `BOTTLENECK_SEQUENTIAL_GEMINI_MODEL`, and CrewAI uses `BOTTLENECK_CREWAI_MODEL`. Splitting the three workloads across configurable models prevents one stage from exhausting another stage's per-model request quota.

Live stages have a configurable 35-second ceiling. If a provider is congested, deterministic continuity uses the same persisted records and publishes source-labeled outputs instead of leaving dashboard cards hanging.

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

Open `http://127.0.0.1:3000`



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

## Google Cloud Run deployment

The production container serves the dashboard, FastAPI endpoints, and A2A endpoint from one Cloud Run URL. It reads Cloud Run's assigned `PORT`, keeps the Gemini key in Secret Manager, and defaults to a seeded temporary SQLite database when a managed database is not configured.

For a faculty demonstration with no local processes, connect the `main` branch to Cloud Run and use the exact settings in [`docs/CLOUD_RUN_DEPLOYMENT.md`](docs/CLOUD_RUN_DEPLOYMENT.md). Set maximum instances to `1`, minimum instances to `0`, and use request-based billing. In Cloud Run the workflow stays inside the `/run` request while the browser polls its persisted progress concurrently, so scale-to-zero does not interrupt agents.

Temporary SQLite state can be reset by deploying a new revision, but it is not durable across instance replacement. For durable production history, set `BOTTLENECK_DATABASE_URL` to a managed SQL database before allowing more than one instance.

## Verification

```bash
pytest -q
node --check frontend/vanilla/app.js
docker compose config --quiet
```

