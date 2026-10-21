# Faculty demo guide

This is the shortest reliable way to present Bottleneck on your own laptop.

## What you will show

The Next.js dashboard at `http://127.0.0.1:3000` reads live data from the FastAPI service at `http://127.0.0.1:8000`. The database contains a synthetic Motor X7 supply-chain scenario. Monetary exposure and downtime are modeled estimates, not observed business results.

## One-time setup

Run these commands from Terminal while connected to the internet:

```bash
cd /Users/aasthathakur/classwork/Bottleneck
/opt/homebrew/bin/python3.13 -m venv .venv313
source .venv313/bin/activate
python -m pip install -e '.[dev,agents]'
python scripts/generate_demo_data.py
PYTHONPATH=backend python scripts/seed_database.py
cd frontend/dashboard
corepack pnpm install --frozen-lockfile
```

Keep the real `GEMINI_API_KEY` only in the project’s untracked `.env` file. Never paste it into slides, source code, or the faculty terminal.

## Start the presentation

Open Terminal and run exactly:

```bash
cd /Users/aasthathakur/classwork/Bottleneck
./scripts/run_demo.sh
```

Wait until Terminal prints both URLs, then open [http://127.0.0.1:3000](http://127.0.0.1:3000). Stop everything with `Ctrl+C` after the presentation.

## Recommended five-minute walkthrough

1. **Command center:** explain the active incident count, pending approvals, modeled financial exposure, and estimated downtime.
2. **Incident queue:** select “Motor X7 delay” and point out that the dashboard is reading an actual incident record from SQLite through FastAPI.
3. **Incident analysis:** explain the baseline simulation, first shortage date, and the explicit “not assessed” risk state when an agent workflow has not completed.
4. **Supplier resilience:** compare reliability and on-time delivery across active suppliers. Mention that suppliers on quality hold are intentionally excluded from this comparison.
5. **Agent workflow:** click **Run investigation**. The request starts immediately in the background, the progress bar advances through triage, evidence, risk, supplier research, recovery planning, and reflection, and all nine stages remain visible. The app prefers the real Gemini/ADK agents. If Gemini is temporarily quota-limited, the run transparently switches to the labeled `deterministic-continuity` path, which uses the same authorized SQLite records, simulation, constraints, scoring, and human-approval gate.
6. **Evaluation evidence:** finish with the stored deterministic evaluation metrics and the human-approval guardrail.

## Before entering the classroom

Run this quick check once:

```bash
cd /Users/aasthathakur/classwork/Bottleneck
source .venv313/bin/activate
pytest -q
cd frontend/dashboard
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm build
```

Also confirm `http://127.0.0.1:3000` loads while Wi-Fi is off. The dashboard and deterministic continuity path work locally; internet access enables the preferred live Gemini agent execution.

## Troubleshooting

- **Port 3000 already in use:** stop the other Next.js process, then rerun the script.
- **Port 8000 already in use:** open `http://127.0.0.1:8000/health`. If it does not show `{"status":"ok"}`, stop the conflicting process.
- **Dashboard says API unavailable:** check `work/api.log`, then rerun `./scripts/run_demo.sh`.
- **Gemini temporarily unavailable:** keep the page open. The workflow automatically records the provider failure and completes through the explicitly labeled deterministic continuity path; do not describe that fallback as a successful Gemini call.
- **Dependencies missing:** repeat the one-time setup while connected to the internet.
