from __future__ import annotations

from collections.abc import Callable
from typing import Any

from crewai import Agent, Crew, Process, Task
from crewai.tools import tool
from pydantic import BaseModel, Field

from app.config import get_settings
from app.database import build_engine, session_factory
from app.tools import SupplyChainTools


class ResearchedSupplier(BaseModel):
    supplier_id: str
    component_id: str
    unit_price: float
    lead_time_days: int
    available_capacity: int
    quality_score: float
    reliability_score: float
    status: str
    eligible: bool
    feasible_quantity: int = Field(ge=0)
    rejection_reasons: list[str] = Field(default_factory=list)
    source_record_id: str


class CrewRoleOutput(BaseModel):
    role: str
    task_name: str
    status: str = "COMPLETED"
    output: str


class SupplierResearchResult(BaseModel):
    component_id: str
    requested_quantity: int = Field(ge=0)
    candidates: list[ResearchedSupplier]
    review_notes: list[str] = Field(default_factory=list)
    role_outputs: list[CrewRoleOutput] = Field(default_factory=list)
    source_system: str = "synthetic_supplier_database"


@tool("query_authorized_component_suppliers", result_as_answer=False)
def query_authorized_component_suppliers(component_id: str) -> list[dict[str, Any]]:
    """Return all synthetic supplier records qualified for a component, including held records."""
    settings = get_settings()
    engine = build_engine(settings.database_url)
    Session = session_factory(engine)
    try:
        with Session() as session:
            rows = SupplyChainTools(session).get_component_suppliers(component_id, active_only=False)
            return [row.model_dump(mode="json") for row in rows]
    finally:
        engine.dispose()


def build_supplier_research_crew(
    model: str,
    *,
    task_callback: Callable[[Any], Any] | None = None,
) -> Crew:
    """Build the required real CrewAI researcher/analyst/reviewer crew."""
    llm_name = model if "/" in model else f"gemini/{model}"
    researcher = Agent(
        role="Supplier Researcher",
        goal="Retrieve every authorized synthetic supplier record for the requested component.",
        backstory="You are a source-disciplined supply researcher. You never invent suppliers or use live-market claims.",
        llm=llm_name,
        tools=[query_authorized_component_suppliers],
        allow_delegation=False,
        allow_code_execution=False,
        max_iter=3,
        max_retry_limit=1,
        max_execution_time=15,
        verbose=False,
    )
    analyst = Agent(
        role="Supplier Analyst",
        goal="Compare retrieved suppliers on cost, capacity, quality, lead time, and reliability without changing source numbers.",
        backstory="You identify operational trade-offs using only records supplied by the researcher.",
        llm=llm_name,
        allow_delegation=False,
        allow_code_execution=False,
        max_iter=2,
        max_retry_limit=1,
        max_execution_time=15,
        verbose=False,
    )
    reviewer = Agent(
        role="Supplier Reviewer",
        goal="Reject unsupported or hard-constraint-violating candidates and produce validated structured candidate data.",
        backstory="You are the final evidence and eligibility gate. Unknown data is never treated as favorable.",
        llm=llm_name,
        allow_delegation=False,
        allow_code_execution=False,
        max_iter=2,
        max_retry_limit=1,
        max_execution_time=15,
        verbose=False,
    )
    research_task = Task(
        name="retrieve_supplier_candidates",
        description=(
            "For component {component_id}, call the authorized supplier tool. Return the exact records and source IDs. "
            "The requested quantity is {requested_quantity}. These are synthetic scenario suppliers, not live sourcing options."
        ),
        expected_output="A source-grounded list of exact supplier records with no invented candidates.",
        agent=researcher,
    )
    analysis_task = Task(
        name="compare_supplier_candidates",
        description=(
            "Compare the retrieved records. Determine capacity-limited feasible quantity as min(requested quantity, available capacity). "
            "Do not estimate missing facts. Preserve all numbers exactly."
        ),
        expected_output="A comparison of cost, capacity, quality, lead time, reliability, and status with explicit trade-offs.",
        agent=analyst,
        context=[research_task],
    )
    review_task = Task(
        name="review_supplier_candidates",
        description=(
            "Review component compatibility, ACTIVE status, minimum quality {minimum_quality}, and capacity. "
            "Set eligible false and list reasons for failures. Output only suppliers present in research context."
        ),
        expected_output="A validated SupplierResearchResult with evidence-grounded eligibility and rejection reasons.",
        agent=reviewer,
        context=[research_task, analysis_task],
        output_pydantic=SupplierResearchResult,
        guardrail_max_retries=2,
    )
    return Crew(
        name="alternative_supplier_research_crew",
        agents=[researcher, analyst, reviewer],
        tasks=[research_task, analysis_task, review_task],
        process=Process.sequential,
        memory=False,
        cache=False,
        verbose=False,
        tracing=False,
        task_callback=task_callback,
    )


class SupplierResearchCrewAdapter:
    """Narrow adapter used by the ADK alternative-supplier agent."""

    def __init__(self, model: str, *, fallback_models: list[str] | None = None) -> None:
        self.models = list(dict.fromkeys([model, *(fallback_models or [])]))
        self.crew = build_supplier_research_crew(model)

    def run(
        self,
        *,
        component_id: str,
        requested_quantity: int,
        minimum_quality: float,
        task_callback: Callable[[Any], Any] | None = None,
    ) -> SupplierResearchResult:
        output = None
        last_error: Exception | None = None
        for index, model in enumerate(self.models):
            crew = (
                self.crew
                if index == 0 and task_callback is None
                else build_supplier_research_crew(
                    model, task_callback=task_callback
                )
            )
            try:
                output = crew.kickoff(inputs={
                    "component_id": component_id,
                    "requested_quantity": requested_quantity,
                    "minimum_quality": minimum_quality,
                })
                break
            except Exception as exc:
                last_error = exc
        if output is None:
            raise RuntimeError(
                f"CrewAI supplier research failed across {len(self.models)} model(s): {last_error}"
            ) from last_error
        if output.pydantic is None:
            raise ValueError("CrewAI supplier research did not return validated structured output")
        result = SupplierResearchResult.model_validate(output.pydantic)
        if result.component_id != component_id:
            raise ValueError("CrewAI output component does not match the request")
        roles = ("Supplier Researcher", "Supplier Analyst", "Supplier Reviewer")
        task_names = (
            "retrieve_supplier_candidates",
            "compare_supplier_candidates",
            "review_supplier_candidates",
        )
        role_outputs = []
        for role, task_name, task_output in zip(
            roles, task_names, output.tasks_output, strict=False
        ):
            raw = str(getattr(task_output, "raw", task_output)).strip()
            role_outputs.append(
                CrewRoleOutput(
                    role=role,
                    task_name=task_name,
                    output=raw[:6000],
                )
            )
        return result.model_copy(update={"role_outputs": role_outputs})

