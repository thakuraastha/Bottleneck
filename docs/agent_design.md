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

All current numerical facts are obtained from deterministic function tools. Investigation outputs use Pydantic schemas and retain source-system and source-record references. The risk analyst may explain but cannot modify the deterministic score. The recovery planner proposes allocations; Python assigns dates and prices, simulates them, validates constraints, and scores them. Reflection does not replace hard constraints.

Agent 7 invokes a real CrewAI `Crew` with three sequential nested roles: Supplier Researcher, Supplier Analyst, and Supplier Reviewer. Its only supplier source is the synthetic supplier database. The final review task has a Pydantic output contract.

Live execution requires `GOOGLE_API_KEY`. Offline tests construct and validate the real framework objects but do not claim that model calls ran.

