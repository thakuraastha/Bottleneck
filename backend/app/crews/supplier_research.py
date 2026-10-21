from __future__ import annotations

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


class SupplierResearchResult(BaseModel):
    component_id: str
    requested_quantity: int = Field(ge=0)
    candidates: list[ResearchedSupplier]
    review_notes: list[str] = Field(default_factory=list)
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


def build_supplier_research_crew(model: str) -> Crew:
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
        max_iter=4,
        max_retry_limit=1,
        verbose=False,
    )
    analyst = Agent(
        role="Supplier Analyst",
        goal="Compare retrieved suppliers on cost, capacity, quality, lead time, and reliability without changing source numbers.",
        backstory="You identify operational trade-offs using only records supplied by the researcher.",
        llm=llm_name,
        allow_delegation=False,
        allow_code_execution=False,
        max_iter=4,
        max_retry_limit=1,
        verbose=False,
    )
    reviewer = Agent(
        role="Supplier Reviewer",
        goal="Reject unsupported or hard-constraint-violating candidates and produce validated structured candidate data.",
        backstory="You are the final evidence and eligibility gate. Unknown data is never treated as favorable.",
        llm=llm_name,
        allow_delegation=False,
        allow_code_execution=False,
        max_iter=4,
        max_retry_limit=1,
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
    )


class SupplierResearchCrewAdapter:
    """Narrow adapter used by the ADK alternative-supplier agent."""

    def __init__(self, model: str) -> None:
        self.crew = build_supplier_research_crew(model)

    def run(self, *, component_id: str, requested_quantity: int, minimum_quality: float) -> SupplierResearchResult:
        output = self.crew.kickoff(inputs={
            "component_id": component_id,
            "requested_quantity": requested_quantity,
            "minimum_quality": minimum_quality,
        })
        if output.pydantic is None:
            raise ValueError("CrewAI supplier research did not return validated structured output")
        result = SupplierResearchResult.model_validate(output.pydantic)
        if result.component_id != component_id:
            raise ValueError("CrewAI output component does not match the request")
        return result

