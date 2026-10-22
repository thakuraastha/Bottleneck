# Implementation plan and dependency map

The build follows the 24 phases in the master brief. Each phase is verified before downstream work relies on it.

## Dependency map

```text
configuration + domain contracts
        |
        +--> synthetic CSVs --> SQLAlchemy schema + seed process
        |                              |
        +--> deterministic tools ------+
                       |
        simulation --> risk/scoring/constraints --> deterministic tests
                       |
        ADK specialists + parallel orchestration
                       |
        evidence + routing + CrewAI research
                       |
        planning + reflection + memory + approval
                       |
        events + API + vanilla dashboard + observability
                       |
        evaluation + E2E + Docker + final docs
```

## Completed milestones

- Phase 1: repository layout, environment configuration, typed domain models, and typed incident state.
- Phase 2: six relational synthetic datasets, fixed simulation date, controlled SQLite schema creation, and repeatable seeding.
- Phase 3: validated read-only source-data tools with typed outputs.
- Phase 4: reusable daily simulation covering reservations, dated receipts, variable demand, safety stock, shortages, interruption, downtime, and financial exposure.
- Phase 5: documented risk, strategy-scoring, and hard-constraint engines.
- Phase 6: deterministic unit and integration tests for these foundations.

## Current agentic milestone

- Phases 7–8: nine top-level ADK agents are defined; triage and the four investigators use the maintained ADK 2.x graph Workflow with fan-out, `JoinNode`, and four-worker concurrency.
- Phases 9–10: deterministic evidence aggregation, conflict/missing-data checks, a non-mutating Risk Analyst, and explicit conditional routing are implemented.
- Phase 11: Agent 7 uses a real CrewAI `Agent`/`Task`/`Crew` adapter with Researcher, Analyst, and Reviewer roles.
- Phases 12–13: Recovery Planning has a structured proposal contract; Python converts proposals into dated allocations, simulation results, constraint results, and comparable scores.
- Phase 14: the Reflection agent and a two-revision bounded loop are implemented, but live model execution is not yet wired into the persisted workflow runner.
- Phase 15: persistent incident-memory reads, planned/predicted records, and later observed-outcome updates are implemented.
- Phase 16: approval validation and execution-plan persistence are implemented. Rejection persistence exists; automatic live-agent replanning remains pending.
- Phase 17: persist-first, idempotent event ingestion and explicit seven-day incident matching are implemented.
- Phase 18: FastAPI exposes event, incident, simulation, evidence, risk, workflow, strategy, approval, report, supplier, dashboard, and evaluation resources.
- Phase 19: the framework-free HTML/CSS/JavaScript operations interface exposes the presentation tabs and consumes the API rather than querying SQLite directly.
- Phase 20: supported ADK agent/model/tool callbacks persist real timing, status, retry, model, error, and token fields when available.
- Phase 21: the offline evaluation runner persists measured source-tool, grounding, routing, and constraint scenarios. Model-dependent metrics remain explicitly unmeasured until live executions exist.
- Phase 22: deterministic component, integration, API, callback, and UI-render paths are covered by the automated suite. A credentialed full-model scenario is still pending.
- Phase 23: Dockerfile and Compose definitions are implemented with guarded first-run seeding and health checks.
- Phase 24: operating, observability, evaluation, risk, strategy, data, and architecture documentation is present; final credentialed orchestration verification remains pending.

No live ADK or CrewAI model invocation is reported without a configured model key and an executed integration run.

Agent dependencies are optional installation extras so deterministic development and tests do not require credentials. The live endpoint currently integrates triage and parallel investigation through evidence, risk, and routing. Alternative research, recovery planning, reflection, and rejection-driven replanning still need to be connected into that persisted live path.
