# Faculty demo guide

This is the shortest reliable way to present Bottleneck on your own laptop.

## What you will show

The vanilla HTML/CSS/JavaScript dashboard at `http://127.0.0.1:3000` reads live data from the FastAPI service at `http://127.0.0.1:8000`. The database contains a synthetic Motor X7 supply-chain scenario. Monetary exposure and downtime are modeled estimates, not observed business results.

## One-time setup

Run these commands from Terminal while connected to the internet:

```bash
cd /Users/aasthathakur/classwork/Bottleneck
/opt/homebrew/bin/python3.13 -m venv .venv313
source .venv313/bin/activate
python -m pip install -e '.[dev,agents]'
python scripts/generate_demo_data.py
PYTHONPATH=backend python scripts/seed_database.py
```

Keep the real `GEMINI_API_KEY` only in the project’s untracked `.env` file. Never paste it into slides, source code, or the faculty terminal.

## Start the presentation

Open Terminal and run exactly:

```bash
cd /Users/aasthathakur/classwork/Bottleneck
./scripts/run_demo.sh
```

Wait until Terminal prints both URLs, then open [http://127.0.0.1:3000](http://127.0.0.1:3000). Stop everything with `Ctrl+C` after the presentation.

The public cloud build is available at [https://bottleneck.vercel.app](https://bottleneck.vercel.app). Use the local URL for the assessed walkthrough because it preserves the complete SQLite audit across browser requests; the Vercel container needs a managed SQL database for durable cloud history.

## Recommended five-minute walkthrough

1. **Overview tab:** explain the four KPIs and the functional-proof cards showing persisted records for each major subsystem.
2. **Incidents tab:** select “Motor X7 delay,” click **Run investigation**, and show the live background progress without freezing the page.
3. **Evidence tab:** show the deterministic risk formula, simulation results, and source-linked evidence ledger.
4. **Agents tab:** show all nine agent stages plus the exact execution/tool timeline. `deterministic-continuity` is explicitly labeled when Gemini is quota-limited.
5. **Recovery plans tab:** show allocations, deterministic weighted score, reflection result, and the human approval/rejection gate.
6. **Suppliers tab:** compare every authorized scenario supplier, including status, quality, reliability, capacity, cost, and lead time.
7. **Evaluation tab:** run the stored evaluation suite, show measured runtime/cost evidence, and finish with the live 11-criterion implementation matrix. Open the A2A Agent Card from the listed endpoint if asked for protocol proof.

## Before entering the classroom

Run this quick check once:

```bash
cd /Users/aasthathakur/classwork/Bottleneck
source .venv313/bin/activate
pytest -q
node --check frontend/vanilla/app.js
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/a2a/.well-known/agent-card.json
curl --fail http://127.0.0.1:8000/system/compliance
curl --fail http://127.0.0.1:3000/
```

Also confirm `http://127.0.0.1:3000` loads while Wi-Fi is off. The dashboard and deterministic continuity path work locally; internet access enables the preferred live Gemini agent execution.

## Troubleshooting

- **Port 3000 already in use:** stop the other local web server, then rerun the script.
- **Port 8000 already in use:** open `http://127.0.0.1:8000/health`. If it does not show `{"status":"ok"}`, stop the conflicting process.
- **Dashboard says API unavailable:** check `work/api.log`, then rerun `./scripts/run_demo.sh`.
- **Gemini temporarily unavailable:** keep the page open. The workflow automatically records the provider failure and completes through the explicitly labeled deterministic continuity path; do not describe that fallback as a successful Gemini call.
- **Dependencies missing:** repeat the one-time setup while connected to the internet.
