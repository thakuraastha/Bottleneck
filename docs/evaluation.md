# Evaluation framework

`POST /evaluations/run` executes three deterministic scenarios against the configured database:

1. Authorized source-tool reads and evidence provenance.
2. Inventory simulation, deterministic risk, and conditional routing.
3. Recovery proposal simulation, hard-constraint validation, scoring, and valid-strategy selection.

Each rate stores its numerator, denominator, observed percentage, and measurement method. The run also stores wall-clock latency and per-scenario results. Reflection issue detection and agent failure rate require credentialed model executions, so the offline suite records them as `measured: false`, denominator zero, and a reason. The dashboard never substitutes a placeholder percentage.

The suite is reproducible for the fixed simulation clock (`2026-01-15`) and seeded Motor X7 data. Its 100% values describe this executed fixture suite only; they are not production reliability claims.
