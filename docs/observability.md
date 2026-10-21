# Observability

`AdkObservabilityCallbacks` uses maintained Google ADK lifecycle hooks for agents, models, and tools. It writes `agent_runs` only when the ADK session state contains a persisted `incident_id` and `workflow_run_id`; missing scope results in no row rather than a synthetic event.

Recorded fields include agent and tool identity, start/end timestamps, duration, status, retry count, model identifier, error text, and provider token metadata when returned. Parallel branches use invocation/function-call keys protected by a lock. SQLite timestamps are normalized to UTC when calculating durations because SQLite can round-trip timezone-aware values as naive datetimes.

The workflow dashboard reads `workflow_runs` and `agent_runs` through FastAPI. An absent credential returns `503` before a workflow row is created, so the UI cannot imply an execution that did not occur.
