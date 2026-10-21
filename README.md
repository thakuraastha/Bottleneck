# BOTTLENECK

Multi-agent supply-chain disruption and recovery system built with Google ADK, CrewAI, FastAPI, Next.js, SQLAlchemy, and SQLite.

## What works

- Synthetic Motor X7 supplier-delay scenario with repeatable CSV generation and database seeding.
- Read-only supply-chain tools, daily inventory/production simulation, deterministic risk, strategy scoring, and mandatory constraints.
- Nine typed ADK agents, real graph fan-out/join investigation, and a nested CrewAI Researcher/Analyst/Reviewer crew.
- Evidence provenance, explicit conditional routing, bounded replanning, incident memory, and guarded human approval.
- Idempotent event ingestion, 22-table persistence model, FastAPI endpoints, and a responsive Next.js operations dashboard.
- ADK agent/model/tool callbacks that persist real execution events.
- Reproducible offline evaluations with explicit numerators, denominators, methods, and unmeasured model-dependent metrics.
- Dockerfile and Docker Compose services for the API and dashboard.

The live `/incidents/{id}/run` endpoint requires `GOOGLE_API_KEY` or `GEMINI_API_KEY`. Without a key it returns `503` and creates no fake execution records. The currently wired live graph covers triage plus the four parallel specialist investigations, evidence aggregation, deterministic risk, and conditional routing. Live alternative-supplier research, planning, reflection, and rejection-triggered replanning are the remaining orchestration integration work.

The default model is `gemini-3.8-flash`; override it with `BOTTLENECK_GEMINI_MODEL` when required.

## Native setup

Python 3.13 is recommended; the maintained CrewAI release used here is not available under Python 3.14.

```bash
/opt/homebrew/bin/python3.13 -m venv .venv313
source .venv313/bin/activate
python -m pip install -e '.[dev,agents,ui]'
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

### Start services separately

Start the API and dashboard in separate terminals when developing:

```bash
source .venv313/bin/activate
uvicorn app.api.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

```bash
cd frontend/dashboard
corepack pnpm install --frozen-lockfile
BOTTLENECK_API_URL=http://127.0.0.1:8000 corepack pnpm dev --hostname 127.0.0.1 --port 3000
```

API documentation is at `http://127.0.0.1:8000/docs`. The previous Streamlit client remains in `frontend/app.py` as a legacy reference; the Next.js app in `frontend/dashboard` is the primary interface.

## Docker Compose

```bash
docker compose up --build
```

The API seeds the persistent Docker volume only when no suppliers exist. Set `GOOGLE_API_KEY` or `GEMINI_API_KEY` in the shell or an untracked `.env` file to enable live model execution. Never commit credentials.

Open `http://127.0.0.1:3000` after both containers become healthy.

## Verification

```bash
pytest -q
cd frontend/dashboard
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm build
cd ../..
docker compose config --quiet
```

See [architecture](docs/architecture.md), [agent design](docs/agent_design.md), [observability](docs/observability.md), [evaluation](docs/evaluation.md), and the [implementation plan](docs/implementation_plan.md).
