from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from google.adk.workflow import Workflow

from app.agents import AgentCatalog, build_agent_catalog


@dataclass(frozen=True)
class InvestigationWorkflow:
    catalog: AgentCatalog
    root: Workflow


def build_investigation_workflow(
    model: str,
    callbacks: Any | None = None,
    *,
    retry_attempts: int = 2,
    timeout_seconds: float = 75.0,
) -> InvestigationWorkflow:
    catalog = build_agent_catalog(
        model,
        callbacks=callbacks,
        retry_attempts=retry_attempts,
        timeout_seconds=timeout_seconds,
    )
    root = Workflow(
        name="bottleneck_investigation_workflow",
        description="Triage followed by genuine parallel specialist investigation.",
        edges=[("START", catalog.orchestrator, catalog.parallel_investigation)],
        max_concurrency=4,
    )
    return InvestigationWorkflow(catalog=catalog, root=root)
