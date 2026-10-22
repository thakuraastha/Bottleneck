# Project requirements compliance

The running API exposes the same matrix as JSON at `GET /system/compliance`; the dashboard renders it in the **Evaluation** tab. This document points to the implementation evidence that can be opened during assessment.

| # | Requirement | Implementation evidence |
|---|---|---|
| 1 | Context sharing and state updates | ADK `InMemorySessionService` state carries namespaced outputs (`triage_output`, four `investigation_*` branches, `risk_interpretation`, `alternative_supplier_research`, `recovery_proposals`, and `reflection_review`). Deterministic continuity uses ADK `EventActions.state_delta`, so the same state contract is preserved. |
| 2 | MCP tools | `app.mcp.server` exposes four read-only MCP tools. Supplier and logistics ADK agents consume them through ADK `McpToolset` over stdio. The integration test performs a real MCP initialize/list-tools exchange. |
| 3 | Pydantic output | Agent outputs, A2A messages, domain entities, API responses, strategies, evaluations, and the final incident report use Pydantic models and are emitted as JSON. |
| 4 | Agentic patterns | Sequential orchestration, four-agent parallel fan-out/join, conditional routing, nested sequential CrewAI research, reflection, bounded replanning, incident memory, and human-in-the-loop approval are implemented. |
| 5 | Callback monitoring | ADK agent/model/tool callbacks persist start/end time, duration, status, retry ordinal, errors, model identity, and provider token metadata in `agent_runs`. |
| 6 | A2A interoperability | The ADK alternative-supplier stage sends a typed A2A 0.3 JSON-RPC message to the CrewAI supplier agent. Its Agent Card is served at `/a2a/.well-known/agent-card.json`. |
| 7 | CrewAI and ADK only | Google ADK owns the top-level workflow. CrewAI owns the researcher/analyst/reviewer sub-team. MCP and A2A are protocols, not additional agent frameworks. |
| 8 | Security | API and callback guardrails detect prompt injection, threats, exposed API-key patterns, oversized inputs, non-JSON/oversized tool payloads, and output injection. Blocks are stored in `security_events`. Tools are read-only and human approval is mandatory before an execution plan is created. |
| 9 | Observability | `workflow_runs`, `agent_runs`, `security_events`, evidence source IDs, risks, candidate provenance, constraint violations, reflections, decisions, and memory are correlated in the incident audit endpoint. |
| 10 | Evaluation, cost, and runtime | `POST /evaluations/run` executes reproducible end-to-end deterministic scenarios and stores completion, invocation, grounding, structured-output, constraint, routing, and latency metrics. It also summarizes the latest workflow runtime, agent failures, token usage, and a configurable cost estimate. |
| 11 | Cloud deployment | `Dockerfile.vercel` and `vercel.json` deploy the complete FastAPI + dashboard container to Vercel. `render.yaml` is a second Docker deployment option. The compliance endpoint marks this criterion passed only when the platform provides a live deployment URL. |

## Verification commands

```bash
pytest -q
node --check frontend/vanilla/app.js
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/a2a/.well-known/agent-card.json
curl --fail http://127.0.0.1:8000/system/compliance
```

The system never labels a deterministic continuity run as a successful model call. Cost values are estimates using the configured input/output rates; provider billing remains authoritative.
