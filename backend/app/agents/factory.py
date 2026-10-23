from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.workflow import JoinNode, RetryConfig, Workflow
from google.genai.errors import ServerError

from app.mcp import build_mcp_toolset
from app.models.investigations import (
    InventoryInvestigation,
    LogisticsInvestigation,
    ProductionInvestigation,
    RecoveryPlanningOutput,
    ReflectionReview,
    RiskInterpretation,
    SupplierInvestigation,
    TriageOutput,
)
from app.tools.agent_tools import (
    ALTERNATIVE_SUPPLIER_TOOLS,
    INVENTORY_TOOLS,
    PRODUCTION_TOOLS,
)

from .prompts import (
    ALTERNATIVE_SUPPLIER_INSTRUCTION,
    INVENTORY_INSTRUCTION,
    LOGISTICS_INSTRUCTION,
    PRODUCTION_INSTRUCTION,
    RISK_ANALYST_INSTRUCTION,
    RECOVERY_PLANNER_INSTRUCTION,
    REFLECTION_INSTRUCTION,
    SUPPLIER_INSTRUCTION,
    TRIAGE_INSTRUCTION,
)


@dataclass(frozen=True)
class AgentCatalog:
    orchestrator: LlmAgent
    supplier_intelligence: LlmAgent
    logistics_intelligence: LlmAgent
    demand_inventory: LlmAgent
    production_impact: LlmAgent
    parallel_investigation: Workflow
    risk_analyst: LlmAgent
    alternative_supplier: LlmAgent
    recovery_planner: LlmAgent
    reflection_quality: LlmAgent

    @property
    def top_level_agents(self) -> tuple[LlmAgent, ...]:
        return (
            self.orchestrator,
            self.supplier_intelligence,
            self.logistics_intelligence,
            self.demand_inventory,
            self.production_impact,
            self.risk_analyst,
            self.alternative_supplier,
            self.recovery_planner,
            self.reflection_quality,
        )


def build_agent_catalog(
    model: str,
    callbacks: Any | None = None,
    *,
    retry_attempts: int = 2,
    timeout_seconds: float = 75.0,
) -> AgentCatalog:
    """Create supported ADK 2.x agents without executing a model call."""
    callback_kwargs = callbacks.agent_kwargs() if callbacks else {}
    supplier_mcp = build_mcp_toolset(
        ["lookup_supplier", "lookup_supplier_orders"]
    )
    logistics_mcp = build_mcp_toolset(
        ["lookup_order_shipments", "calculate_delay_days"]
    )
    execution_kwargs = {
        **callback_kwargs,
        "retry_config": RetryConfig(
            max_attempts=retry_attempts,
            initial_delay=2.0,
            max_delay=8.0,
            backoff_factor=2.0,
            jitter=0.5,
            exceptions=[ServerError],
        ),
        "timeout": timeout_seconds,
    }
    orchestrator = LlmAgent(
        name="orchestrator_triage_agent",
        description="Validates and scopes supply-chain incidents.",
        model=model,
        instruction=TRIAGE_INSTRUCTION,
        output_schema=TriageOutput,
        output_key="triage_output",
        mode="single_turn",
        **execution_kwargs,
    )
    supplier = LlmAgent(
        name="supplier_intelligence_agent",
        description="Investigates current supplier facts and commitments.",
        model=model,
        instruction=SUPPLIER_INSTRUCTION,
        tools=[supplier_mcp],
        output_schema=SupplierInvestigation,
        output_key="investigation_supplier",
        mode="single_turn",
        **execution_kwargs,
    )
    logistics = LlmAgent(
        name="logistics_intelligence_agent",
        description="Investigates shipment state and delay exposure.",
        model=model,
        instruction=LOGISTICS_INSTRUCTION,
        tools=[logistics_mcp],
        output_schema=LogisticsInvestigation,
        output_key="investigation_logistics",
        mode="single_turn",
        **execution_kwargs,
    )
    inventory = LlmAgent(
        name="demand_inventory_agent",
        description="Investigates stock, demand, inbound supply, and shortage exposure.",
        model=model,
        instruction=INVENTORY_INSTRUCTION,
        tools=INVENTORY_TOOLS,
        output_schema=InventoryInvestigation,
        output_key="investigation_inventory",
        mode="single_turn",
        **execution_kwargs,
    )
    production = LlmAgent(
        name="production_impact_agent",
        description="Investigates production dependencies and deterministic impact.",
        model=model,
        instruction=PRODUCTION_INSTRUCTION,
        tools=PRODUCTION_TOOLS,
        output_schema=ProductionInvestigation,
        output_key="investigation_production",
        mode="single_turn",
        **execution_kwargs,
    )
    join = JoinNode(name="investigation_evidence_join")
    parallel = Workflow(
        name="parallel_investigation",
        description="Runs four independent specialist investigations concurrently.",
        edges=[
            ("START", supplier, join),
            ("START", logistics, join),
            ("START", inventory, join),
            ("START", production, join),
        ],
        max_concurrency=4,
    )
    risk_analyst = LlmAgent(
        name="risk_analyst_agent",
        description="Explains deterministic risk without changing its score.",
        model=model,
        instruction=RISK_ANALYST_INSTRUCTION,
        output_schema=RiskInterpretation,
        output_key="risk_interpretation",
        mode="chat",
        **execution_kwargs,
    )
    alternative_supplier = LlmAgent(
        name="alternative_supplier_agent",
        description="Invokes the nested CrewAI supplier research workflow.",
        model=model,
        instruction=ALTERNATIVE_SUPPLIER_INSTRUCTION,
        tools=ALTERNATIVE_SUPPLIER_TOOLS,
        output_key="alternative_supplier_research",
        mode="chat",
        **execution_kwargs,
    )
    recovery_planner = LlmAgent(
        name="recovery_planning_agent",
        description="Proposes evidence-grounded recovery allocations for deterministic evaluation.",
        model=model,
        instruction=RECOVERY_PLANNER_INSTRUCTION,
        output_schema=RecoveryPlanningOutput,
        output_key="recovery_proposals",
        mode="chat",
        **execution_kwargs,
    )
    reflection = LlmAgent(
        name="reflection_quality_agent",
        description="Reviews recommendation quality without replacing hard validation.",
        model=model,
        instruction=REFLECTION_INSTRUCTION,
        output_schema=ReflectionReview,
        output_key="reflection_review",
        mode="chat",
        **execution_kwargs,
    )
    return AgentCatalog(
        orchestrator=orchestrator,
        supplier_intelligence=supplier,
        logistics_intelligence=logistics,
        demand_inventory=inventory,
        production_impact=production,
        parallel_investigation=parallel,
        risk_analyst=risk_analyst,
        alternative_supplier=alternative_supplier,
        recovery_planner=recovery_planner,
        reflection_quality=reflection,
    )
