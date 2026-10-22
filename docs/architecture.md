# Architecture

```mermaid
flowchart LR
  E[Supply-chain event] --> V[Persist and validate]
  V --> T[Orchestrator / Triage]
  T --> S[Supplier Intelligence]
  T --> L[Logistics Intelligence]
  T --> I[Demand & Inventory]
  T --> P[Production Impact]
  S --> A[Evidence aggregation]
  L --> A
  I --> A
  P --> A
  A --> R[Deterministic risk engine]
  R --> RA[Risk Analyst]
  RA --> C{Conditional route}
  C -->|triggered| AS[Alternative Supplier Agent]
  AS -->|A2A JSON-RPC| CR[CrewAI nested research crew]
  C -->|skipped| RP[Recovery Planning]
  CR --> RP
  RP --> DS[Simulation + scoring + constraints]
  DS --> RF[Reflection]
  RF -->|fail, max 2| RP
  RF -->|pass| H[Human approval]
  H -->|reject| RP
  H -->|approve| X[Execution plan only]
  X --> M[Incident memory]
```

Supplier and logistics agents discover read-only database and date-calculation tools through MCP. AI interprets, investigates, proposes, and explains. Deterministic Python calculates and validates. SQLite stores source records, workflow state, evidence, strategies, decisions, execution plans, outcomes, security events, and evaluation results. Humans alone authorize the final action plan; the MVP never places real orders.

