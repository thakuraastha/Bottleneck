# Agent design

BOTTLENECK defines exactly nine top-level ADK `LlmAgent` instances:

1. Orchestrator / Triage
2. Supplier Intelligence
3. Logistics Intelligence
4. Demand & Inventory
5. Production Impact
6. Risk Analyst
7. Alternative Supplier
8. Recovery Planning
9. Reflection / Quality Check

The four investigators are nodes in an ADK 2.x graph `Workflow`. Four edges fan out from `START`, execute with `max_concurrency=4`, and converge on a `JoinNode`. Each agent writes to a distinct output key. The parent workflow runs triage before entering this nested fan-out workflow.

All current numerical facts are obtained from deterministic tools. Supplier and logistics facts come from a local read-only MCP server consumed by ADK `McpToolset`; inventory, production, and simulation tools remain typed deterministic Python functions. Investigation outputs use Pydantic schemas and retain source-system and source-record references. The risk analyst may explain but cannot modify the deterministic score. The recovery planner proposes allocations; Python assigns dates and prices, simulates them, validates constraints, and scores them. Reflection does not replace hard constraints.

Agent 7 sends a typed A2A 0.3 JSON-RPC message to a real CrewAI `Crew` with three sequential nested roles: Supplier Researcher, Supplier Analyst, and Supplier Reviewer. The CrewAI Agent Card is discoverable at `/a2a/.well-known/agent-card.json`. Its only supplier source is the synthetic supplier database. The final review task and the A2A response both have Pydantic contracts.

Live execution requires `GOOGLE_API_KEY`. Offline tests construct and validate the real framework objects but do not claim that model calls ran.

