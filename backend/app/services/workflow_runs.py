from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from google.adk.agents import LlmAgent
from google.adk.events import Event, EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agents import AgentCatalog, build_agent_catalog
from app.config import Settings, get_settings
from app.database.tables import (
    AgentRunRow,
    ConstraintViolationRow,
    EvidenceRow,
    IncidentRow,
    PurchaseOrderRow,
    RecoveryStrategyRow,
    ReflectionRunRow,
    RiskAssessmentRow,
    StrategyEvaluationRow,
    SupplierCandidateRow,
    WorkflowRunRow,
)
from app.engines import RiskEngine
from app.models.domain import IncidentStatus, RiskAssessment
from app.models.investigations import (
    InvestigationFact,
    InventoryInvestigation,
    LogisticsInvestigation,
    ProposedAllocation,
    ProposedStrategy,
    ProductionInvestigation,
    RecoveryPlanningOutput,
    ReflectionReview,
    RiskInterpretation,
    SourceReference,
    SupplierInvestigation,
    TriageOutput,
)
from app.observability import AdkObservabilityCallbacks
from app.orchestration import ConditionalRouter, build_investigation_workflow
from app.services.evidence import EvidenceAggregator
from app.services.strategy_pipeline import StrategyPipeline, StrategyPipelineResult
from app.simulation import SimulationResult, SupplySimulator
from app.tools import SupplyChainTools


logger = logging.getLogger(__name__)


class WorkflowAlreadyRunningError(RuntimeError):
    pass


class ModelCredentialMissingError(RuntimeError):
    pass


class WorkflowUpstreamUnavailableError(RuntimeError):
    pass


class WorkflowModelConfigurationError(RuntimeError):
    pass


class IncidentWorkflowService:
    """Runs the full agent workflow while persisting user-visible progress."""

    APP_NAME = "bottleneck"
    USER_ID = "bottleneck-system"

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        settings: Settings | None = None,
        model: str | None = None,
        simulation_date=None,
        horizon_days: int | None = None,
    ) -> None:
        self.sessions = sessions
        self.settings = settings or get_settings()
        self.model = model or self.settings.gemini_model
        self.simulation_date = simulation_date or self.settings.simulation_date
        self.horizon_days = horizon_days or self.settings.planning_horizon_days

    def start(self, incident_id: str) -> WorkflowRunRow:
        """Validate and persist a queued run without waiting for a model call."""
        if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
            raise ModelCredentialMissingError(
                "GOOGLE_API_KEY or GEMINI_API_KEY is required for live ADK execution"
            )
        workflow_run_id = str(uuid4())
        now = datetime.now(timezone.utc)
        with self.sessions() as session:
            incident = session.get(IncidentRow, incident_id)
            if incident is None:
                raise LookupError(f"incident not found: {incident_id}")
            active = session.scalar(
                select(WorkflowRunRow).where(
                    WorkflowRunRow.incident_id == incident_id,
                    WorkflowRunRow.status == "RUNNING",
                )
            )
            if active:
                raise WorkflowAlreadyRunningError(
                    f"workflow already running: {active.workflow_run_id}"
                )
            row = WorkflowRunRow(
                workflow_run_id=workflow_run_id,
                incident_id=incident_id,
                status="RUNNING",
                state={
                    "incident_id": incident_id,
                    "workflow_run_id": workflow_run_id,
                    "phase": "QUEUED",
                    "phase_label": "Preparing agent workflow",
                    "progress_percent": 2,
                },
                started_at=now,
            )
            incident.status = IncidentStatus.INVESTIGATING.value
            incident.updated_at = now
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    async def run(self, incident_id: str) -> WorkflowRunRow:
        """Compatibility entry point used by tests and non-HTTP callers."""
        row = self.start(incident_id)
        await self.execute(incident_id, row.workflow_run_id)
        with self.sessions() as session:
            completed = session.get(WorkflowRunRow, row.workflow_run_id)
            if completed is None:
                raise LookupError(f"workflow run not found: {row.workflow_run_id}")
            session.expunge(completed)
            return completed

    async def execute(self, incident_id: str, workflow_run_id: str) -> None:
        """Execute all nine agent stages; failures are recorded, never leaked from a task."""
        adk_sessions = InMemorySessionService()
        adk_session_id = f"incident-{incident_id}-{workflow_run_id}"
        try:
            payload = self._incident_payload(incident_id)
            await adk_sessions.create_session(
                app_name=self.APP_NAME,
                user_id=self.USER_ID,
                session_id=adk_session_id,
                state={"incident_id": incident_id, "workflow_run_id": workflow_run_id},
            )

            self._progress(workflow_run_id, "INVESTIGATION", "Triage and four specialist agents", 8)
            catalog, active_model = await self._run_initial_investigation(
                adk_sessions, adk_session_id, payload
            )
            state = await self._state(adk_sessions, adk_session_id)

            self._progress(workflow_run_id, "EVIDENCE", "Aggregating evidence and deterministic risk", 46)
            risk, simulation, routing, required_quantity, evidence_ids = self._persist_investigation_results(
                incident_id, state
            )
            deterministic_context = {
                "incident": payload,
                "evidence_ids": evidence_ids,
                "risk_assessment": risk.model_dump(mode="json"),
                "simulation": simulation.model_dump(mode="json"),
                "conditional_routing": jsonable_encoder(routing.__dict__),
            }

            self._progress(workflow_run_id, "RISK_ANALYSIS", "Risk analyst interpreting scored impact", 56)
            catalog, active_model = await self._invoke_with_fallback(
                lambda item: item.risk_analyst,
                adk_sessions,
                adk_session_id,
                active_model,
                "Interpret this deterministic risk result without changing its score:\n"
                + json.dumps(jsonable_encoder(deterministic_context), sort_keys=True),
                fallback_agent_name="risk_analyst_agent",
                fallback_output_key="risk_interpretation",
                fallback_value=lambda: RiskInterpretation(
                    incident_id=incident_id,
                    primary_drivers=[
                        f"Deterministic severity is {risk.severity.value}",
                        f"Projected shortage is {simulation.total_shortage_quantity} units",
                    ],
                    secondary_consequences=[
                        f"Modeled downtime is {simulation.estimated_downtime_days} days"
                    ],
                    unresolved_uncertainties=[],
                    narrative="Deterministic risk results were preserved and routed to recovery planning.",
                    evidence_ids=evidence_ids,
                    deterministic_score_unchanged=True,
                ).model_dump(mode="json"),
            )

            if routing.should_run:
                self._progress(workflow_run_id, "SUPPLIER_RESEARCH", "Alternative supplier crew researching options", 65)
                catalog, active_model = await self._invoke_with_fallback(
                    lambda item: item.alternative_supplier,
                    adk_sessions,
                    adk_session_id,
                    active_model,
                    json.dumps(
                        {
                            "request": "Run the nested supplier research workflow and preserve its structured result.",
                            "component_id": payload.get("component_id"),
                            "requested_quantity": required_quantity,
                            "minimum_quality": self.settings.minimum_quality_score,
                            "routing": jsonable_encoder(routing.__dict__),
                        },
                        sort_keys=True,
                    ),
                    fallback_agent_name="alternative_supplier_agent",
                    fallback_output_key="alternative_supplier_research",
                    fallback_value=lambda: self._deterministic_supplier_research(
                        payload.get("component_id"), required_quantity
                    ),
                )
                state = await self._state(adk_sessions, adk_session_id)
                alternative_research = self._structured_value(
                    state.get("alternative_supplier_research")
                )
                self._persist_supplier_candidates(
                    incident_id, workflow_run_id, alternative_research
                )
            else:
                alternative_research = {
                    "skipped": True,
                    "reason": routing.reason,
                    "candidates": [],
                }

            last_pipeline: StrategyPipelineResult | None = None
            last_review: ReflectionReview | None = None
            for revision in range(self.settings.maximum_replanning_attempts + 1):
                planning_progress = 73 + min(revision * 7, 14)
                self._progress(
                    workflow_run_id,
                    "RECOVERY_PLANNING",
                    f"Recovery planner building revision {revision}",
                    planning_progress,
                )
                state = await self._state(adk_sessions, adk_session_id)
                planning_context = {
                    **deterministic_context,
                    "risk_interpretation": state.get("risk_interpretation"),
                    "alternative_supplier_research": alternative_research,
                    "revision_number": revision,
                    "previous_reflection": last_review.model_dump(mode="json") if last_review else None,
                }
                catalog, active_model = await self._invoke_with_fallback(
                    lambda item: item.recovery_planner,
                    adk_sessions,
                    adk_session_id,
                    active_model,
                    "Propose recovery strategies from this evidence. Do not claim deterministic feasibility:\n"
                    + json.dumps(jsonable_encoder(planning_context), sort_keys=True),
                    fallback_agent_name="recovery_planning_agent",
                    fallback_output_key="recovery_proposals",
                    fallback_value=lambda: self._deterministic_recovery_plan(
                        incident_id, payload.get("component_id"), required_quantity
                    ),
                )
                state = await self._state(adk_sessions, adk_session_id)
                plan = RecoveryPlanningOutput.model_validate(state.get("recovery_proposals"))
                last_pipeline = self._evaluate_and_persist(
                    incident_id,
                    workflow_run_id,
                    plan,
                    evidence_ids,
                    revision,
                )

                self._progress(
                    workflow_run_id,
                    "REFLECTION",
                    f"Reflection agent validating revision {revision}",
                    min(planning_progress + 5, 94),
                )
                reflection_context = {
                    "incident_id": incident_id,
                    "revision_number": revision,
                    "planner_output": plan.model_dump(mode="json"),
                    "deterministic_evaluation": last_pipeline.model_dump(mode="json"),
                    "must_fail_if_no_valid_recommendation": last_pipeline.recommended_strategy_id is None,
                }
                catalog, active_model = await self._invoke_with_fallback(
                    lambda item: item.reflection_quality,
                    adk_sessions,
                    adk_session_id,
                    active_model,
                    "Review this plan and deterministic validation. Pass only a supported valid recommendation:\n"
                    + json.dumps(reflection_context, sort_keys=True),
                    fallback_agent_name="reflection_quality_agent",
                    fallback_output_key="reflection_review",
                    fallback_value=lambda: ReflectionReview(
                        incident_id=incident_id,
                        passed=last_pipeline.recommended_strategy_id is not None,
                        issues=[] if last_pipeline.recommended_strategy_id else [
                            "No strategy passed deterministic constraints."
                        ],
                        revision_guidance=[] if last_pipeline.recommended_strategy_id else [
                            "Escalate for manual sourcing review."
                        ],
                        unsupported_assumptions=[],
                        contradictory_recommendations=[],
                        revision_number=revision,
                    ).model_dump(mode="json"),
                )
                state = await self._state(adk_sessions, adk_session_id)
                last_review = ReflectionReview.model_validate(state.get("reflection_review"))
                if last_pipeline.recommended_strategy_id is None and last_review.passed:
                    last_review = last_review.model_copy(
                        update={
                            "passed": False,
                            "issues": [*last_review.issues, "No strategy passed deterministic constraints."],
                        }
                    )
                self._persist_reflection(incident_id, workflow_run_id, last_review, revision)
                if last_review.passed and last_pipeline.recommended_strategy_id:
                    break

            final_state = await self._state(adk_sessions, adk_session_id)
            final_state.update(
                {
                    "phase": "WAITING_FOR_APPROVAL" if last_review and last_review.passed else "ESCALATED",
                    "phase_label": "Human approval required" if last_review and last_review.passed else "Human review required",
                    "progress_percent": 100,
                    "conditional_routing": jsonable_encoder(routing.__dict__),
                    "recommended_strategy_id": last_pipeline.recommended_strategy_id if last_pipeline else None,
                    "active_model": active_model,
                }
            )
            incident_status = (
                IncidentStatus.WAITING_FOR_APPROVAL
                if last_review and last_review.passed and last_pipeline and last_pipeline.recommended_strategy_id
                else IncidentStatus.ESCALATED
            )
            self._complete(incident_id, workflow_run_id, final_state, incident_status)
        except Exception as exc:
            logger.exception("Workflow %s failed during live execution", workflow_run_id)
            self._fail(incident_id, workflow_run_id, exc)

    async def _run_initial_investigation(
        self,
        adk_sessions: InMemorySessionService,
        adk_session_id: str,
        payload: dict[str, Any],
    ) -> tuple[AgentCatalog, str]:
        last_error: Exception | None = None
        for model in self._model_candidates(self.model):
            callbacks = AdkObservabilityCallbacks(self.sessions, model_identifier=model)
            workflow = build_investigation_workflow(
                model,
                callbacks=callbacks,
                retry_attempts=self.settings.model_retry_attempts,
                timeout_seconds=self.settings.model_stage_timeout_seconds,
            )
            try:
                await self._run_node(
                    workflow.root,
                    adk_sessions,
                    adk_session_id,
                    "Investigate this persisted supply-chain incident with authorized tools. Incident JSON:\n"
                    + json.dumps(jsonable_encoder(payload), sort_keys=True),
                )
                return workflow.catalog, model
            except Exception as exc:
                last_error = exc
                if not self._is_transient(exc):
                    break
        logger.warning(
            "Live investigation models unavailable; using deterministic continuity mode: %s",
            self._friendly_error(last_error or RuntimeError("unknown provider error")),
        )
        fallback_state = self._deterministic_investigation(payload)
        session_state = await self._state(adk_sessions, adk_session_id)
        await self._inject_state(adk_sessions, adk_session_id, fallback_state)
        for name in (
            "orchestrator_triage_agent",
            "supplier_intelligence_agent",
            "logistics_intelligence_agent",
            "demand_inventory_agent",
            "production_impact_agent",
        ):
            self._record_fallback_agent(
                session_state["incident_id"], session_state["workflow_run_id"], name
            )
        return build_agent_catalog(self.model), "deterministic-continuity"

    async def _invoke_with_fallback(
        self,
        selector: Callable[[AgentCatalog], LlmAgent],
        adk_sessions: InMemorySessionService,
        adk_session_id: str,
        preferred_model: str,
        message: str,
        *,
        fallback_agent_name: str,
        fallback_output_key: str,
        fallback_value: Callable[[], Any],
    ) -> tuple[AgentCatalog, str]:
        if preferred_model == "deterministic-continuity":
            state = await self._state(adk_sessions, adk_session_id)
            await self._inject_state(
                adk_sessions, adk_session_id, {fallback_output_key: fallback_value()}
            )
            self._record_fallback_agent(
                state["incident_id"], state["workflow_run_id"], fallback_agent_name
            )
            return build_agent_catalog(self.model), preferred_model
        last_error: Exception | None = None
        for model in self._model_candidates(preferred_model):
            callbacks = AdkObservabilityCallbacks(self.sessions, model_identifier=model)
            catalog = build_agent_catalog(
                model,
                callbacks=callbacks,
                retry_attempts=self.settings.model_retry_attempts,
                timeout_seconds=self.settings.model_stage_timeout_seconds,
            )
            try:
                await self._run_node(
                    selector(catalog), adk_sessions, adk_session_id, message
                )
                return catalog, model
            except Exception as exc:
                last_error = exc
                if not self._is_transient(exc):
                    break
        logger.warning(
            "Live %s unavailable; using deterministic continuity mode: %s",
            fallback_agent_name,
            self._friendly_error(last_error or RuntimeError("unknown provider error")),
        )
        state = await self._state(adk_sessions, adk_session_id)
        await self._inject_state(
            adk_sessions, adk_session_id, {fallback_output_key: fallback_value()}
        )
        self._record_fallback_agent(
            state["incident_id"], state["workflow_run_id"], fallback_agent_name
        )
        return build_agent_catalog(self.model), "deterministic-continuity"

    async def _run_node(
        self,
        node: Any,
        adk_sessions: InMemorySessionService,
        adk_session_id: str,
        message: str,
    ) -> None:
        runner = Runner(app_name=self.APP_NAME, node=node, session_service=adk_sessions)
        async for _ in runner.run_async(
            user_id=self.USER_ID,
            session_id=adk_session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=message)]),
        ):
            pass

    async def _state(
        self, adk_sessions: InMemorySessionService, adk_session_id: str
    ) -> dict[str, Any]:
        adk_session = await adk_sessions.get_session(
            app_name=self.APP_NAME,
            user_id=self.USER_ID,
            session_id=adk_session_id,
        )
        return dict(adk_session.state if adk_session else {})

    async def _inject_state(
        self,
        adk_sessions: InMemorySessionService,
        adk_session_id: str,
        values: dict[str, Any],
    ) -> None:
        adk_session = await adk_sessions.get_session(
            app_name=self.APP_NAME,
            user_id=self.USER_ID,
            session_id=adk_session_id,
        )
        if adk_session is None:
            raise LookupError(f"ADK session not found: {adk_session_id}")
        await adk_sessions.append_event(
            adk_session,
            Event(
                author="deterministic-continuity",
                actions=EventActions(state_delta=jsonable_encoder(values)),
            ),
        )

    def _deterministic_investigation(self, payload: dict[str, Any]) -> dict[str, Any]:
        incident_id = str(payload["incident_id"])
        supplier_id = str(payload["supplier_id"])
        component_id = str(payload["component_id"])
        order_id = str(payload["order_id"])
        with self.sessions() as session:
            tools = SupplyChainTools(session)
            supplier = tools.get_supplier(supplier_id)
            shipments = tools.get_shipments(order_id)
            inventory = tools.get_inventory(component_id)
            production = tools.get_production_requirements(component_id)
            incident = session.get(IncidentRow, incident_id)
            if incident is None:
                raise LookupError(f"incident not found: {incident_id}")
            simulation = self._simulate(session, incident)
            if simulation is None:
                raise ValueError("incident lacks component/order data needed for simulation")
            source_supplier = SourceReference(
                source_system="synthetic_supplier_database",
                source_record_id=supplier_id,
                fields=["available_capacity", "quality_score", "reliability_score"],
            )
            source_order = SourceReference(
                source_system="synthetic_logistics_database",
                source_record_id=order_id,
                fields=["original_eta", "revised_eta"],
            )
            source_inventory = SourceReference(
                source_system="deterministic_supply_projection",
                source_record_id=component_id,
                fields=["available_quantity", "total_shortage_quantity"],
            )
            source_production = SourceReference(
                source_system="deterministic_supply_projection",
                source_record_id=component_id,
                fields=["estimated_downtime_days", "financial_exposure"],
            )
            available = sum(row.available_quantity for row in inventory)
            original_eta = min((row.original_eta for row in shipments), default=None)
            revised_eta = max((row.revised_eta for row in shipments), default=None)
            delay_days = max(
                (tools.calculate_delay_days(row) for row in shipments), default=0
            )
            remaining = sum(
                max(0, row.shipped_quantity - row.received_quantity)
                for row in shipments
            )
            safety_stock = sum(row.safety_stock for row in inventory)
            return {
                "triage_output": TriageOutput(
                    incident_id=incident_id,
                    affected_supplier_ids=[supplier_id],
                    affected_component_ids=[component_id],
                    affected_order_ids=[order_id],
                    investigation_scope=["supplier", "logistics", "inventory", "production"],
                    can_proceed=True,
                    rationale="All required persisted identifiers are present.",
                ).model_dump(mode="json"),
                "investigation_supplier": SupplierInvestigation(
                    summary="Authorized supplier record retrieved.",
                    supplier_id=supplier_id,
                    active=supplier.status == "ACTIVE",
                    available_capacity=supplier.available_capacity,
                    quality_score=supplier.quality_score,
                    reliability_score=supplier.reliability_score,
                    verified_facts=[
                        InvestigationFact(
                            field="available_capacity",
                            value=supplier.available_capacity,
                            unit="units",
                            source=source_supplier,
                        )
                    ],
                    tool_calls_used=["get_supplier_record"],
                ).model_dump(mode="json"),
                "investigation_logistics": LogisticsInvestigation(
                    summary="Authorized shipment records and deterministic delay retrieved.",
                    order_id=order_id,
                    original_eta=original_eta,
                    revised_eta=revised_eta,
                    delay_days=delay_days,
                    remaining_inbound_quantity=remaining,
                    calculated_facts=[
                        InvestigationFact(
                            field="delay_days",
                            value=delay_days,
                            unit="days",
                            source=source_order,
                        )
                    ],
                    tool_calls_used=["get_order_shipments"],
                ).model_dump(mode="json"),
                "investigation_inventory": InventoryInvestigation(
                    summary="Inventory and supply projection calculated from persisted records.",
                    component_id=component_id,
                    on_hand_quantity=sum(row.on_hand_quantity for row in inventory),
                    reserved_quantity=sum(row.reserved_quantity for row in inventory),
                    available_quantity=available,
                    safety_stock=safety_stock,
                    first_safety_stock_breach_date=simulation.first_safety_stock_breach_date,
                    first_shortage_date=simulation.first_actual_shortage_date,
                    total_shortage_quantity=simulation.total_shortage_quantity,
                    calculated_facts=[
                        InvestigationFact(
                            field="total_shortage_quantity",
                            value=simulation.total_shortage_quantity,
                            unit="units",
                            source=source_inventory,
                        )
                    ],
                    tool_calls_used=["get_component_inventory", "project_component_supply"],
                ).model_dump(mode="json"),
                "investigation_production": ProductionInvestigation(
                    summary="Production impact calculated from persisted requirements.",
                    component_id=component_id,
                    affected_line_ids=[row.production_line_id for row in production],
                    planned_daily_component_requirement=sum(
                        row.planned_daily_output * row.component_units_per_product
                        for row in production
                    ),
                    estimated_downtime_days=simulation.estimated_downtime_days,
                    estimated_financial_exposure=simulation.financial_exposure,
                    calculated_facts=[
                        InvestigationFact(
                            field="financial_exposure",
                            value=simulation.financial_exposure,
                            unit="currency_units",
                            source=source_production,
                        )
                    ],
                    tool_calls_used=["get_production_requirements", "project_component_supply"],
                ).model_dump(mode="json"),
            }

    def _deterministic_supplier_research(
        self, component_id: str | None, requested_quantity: int
    ) -> dict[str, Any]:
        if not component_id:
            return {"component_id": None, "requested_quantity": requested_quantity, "candidates": []}
        with self.sessions() as session:
            suppliers = SupplyChainTools(session).get_component_suppliers(
                component_id, active_only=False
            )
        candidates = []
        for supplier in suppliers:
            reasons = []
            if supplier.status != "ACTIVE":
                reasons.append(f"status is {supplier.status}")
            if supplier.quality_score < self.settings.minimum_quality_score:
                reasons.append("quality is below the configured minimum")
            if supplier.available_capacity <= 0:
                reasons.append("no available capacity")
            candidates.append(
                {
                    **supplier.model_dump(mode="json"),
                    "requested_quantity": requested_quantity,
                    "feasible_quantity": min(requested_quantity, supplier.available_capacity),
                    "eligible": not reasons,
                    "rejection_reasons": reasons,
                    "source_record_id": supplier.supplier_id,
                }
            )
        return {
            "component_id": component_id,
            "requested_quantity": requested_quantity,
            "candidates": candidates,
            "review_notes": ["Eligibility derived from persisted status, quality, and capacity."],
            "source_system": "synthetic_supplier_database",
        }

    def _deterministic_recovery_plan(
        self, incident_id: str, component_id: str | None, required_quantity: int
    ) -> dict[str, Any]:
        if not component_id:
            return RecoveryPlanningOutput(
                incident_id=incident_id,
                escalation_required=True,
                escalation_reason="Component identifier is missing.",
            ).model_dump(mode="json")
        with self.sessions() as session:
            incident = session.get(IncidentRow, incident_id)
            suppliers = SupplyChainTools(session).get_component_suppliers(component_id)
        eligible = sorted(
            [
                item
                for item in suppliers
                if item.supplier_id != (incident.supplier_id if incident else None)
                and item.quality_score >= self.settings.minimum_quality_score
                and item.available_capacity > 0
            ],
            key=lambda item: (item.lead_time_days, item.unit_price),
        )
        remaining = required_quantity
        allocations: list[ProposedAllocation] = []
        for supplier in eligible:
            quantity = min(remaining, supplier.available_capacity)
            if quantity:
                allocations.append(
                    ProposedAllocation(
                        supplier_id=supplier.supplier_id,
                        quantity=quantity,
                        expedite=False,
                    )
                )
                remaining -= quantity
            if remaining <= 0:
                break
        if required_quantity == 0:
            proposals = [
                ProposedStrategy(
                    strategy_type="WAIT",
                    allocations=[],
                    rationale="No outstanding order quantity remains.",
                )
            ]
        elif remaining > 0:
            proposals = []
        else:
            proposals = [
                ProposedStrategy(
                    strategy_type="FULL_SWITCH" if len(allocations) == 1 else "SPLIT_ORDER",
                    allocations=allocations,
                    rationale="Covers outstanding quantity using active, quality-qualified persisted suppliers.",
                    assumptions=["Arrival dates and cost are calculated by the deterministic pipeline."],
                )
            ]
        return RecoveryPlanningOutput(
            incident_id=incident_id,
            proposals=proposals,
            escalation_required=not proposals,
            escalation_reason="Qualified capacity is insufficient." if not proposals else None,
        ).model_dump(mode="json")

    def _record_fallback_agent(
        self, incident_id: str, workflow_run_id: str, agent_name: str
    ) -> None:
        now = datetime.now(timezone.utc)
        with self.sessions() as session:
            session.add(
                AgentRunRow(
                    execution_id=str(uuid4()),
                    incident_id=incident_id,
                    workflow_run_id=workflow_run_id,
                    agent_name=agent_name,
                    start_time=now,
                    end_time=now,
                    duration_ms=0.0,
                    status="COMPLETED",
                    retry_count=0,
                    model_identifier="deterministic-continuity",
                    token_usage={},
                )
            )
            session.commit()

    def _persist_investigation_results(
        self, incident_id: str, state: dict[str, Any]
    ) -> tuple[RiskAssessment, SimulationResult, Any, int, list[str]]:
        specifications = (
            ("investigation_supplier", SupplierInvestigation),
            ("investigation_logistics", LogisticsInvestigation),
            ("investigation_inventory", InventoryInvestigation),
            ("investigation_production", ProductionInvestigation),
        )
        outputs = []
        for key, model in specifications:
            if not state.get(key):
                raise ValueError(f"required specialist output missing: {key}")
            outputs.append(model.model_validate(state[key]))
        aggregation = EvidenceAggregator().aggregate(
            incident_id=incident_id, outputs=outputs, mandatory_fields=set()
        )
        with self.sessions() as session:
            incident = session.get(IncidentRow, incident_id)
            if incident is None:
                raise LookupError(f"incident not found: {incident_id}")
            for item in aggregation.evidence:
                session.add(
                    EvidenceRow(
                        evidence_id=item.evidence_id,
                        incident_id=item.incident_id,
                        evidence_type=item.evidence_type.value,
                        field=item.field,
                        value=jsonable_encoder(item.value),
                        unit=item.unit,
                        source_system=item.source_system,
                        source_record_id=item.source_record_id,
                        observed_at=item.observed_at,
                        created_at=item.created_at,
                        confidence_if_inferred=item.confidence_if_inferred,
                    )
                )
            simulation = self._simulate(session, incident)
            if simulation is None:
                raise ValueError("incident lacks component/order data needed for simulation")
            tools = SupplyChainTools(session)
            shipments = tools.get_shipments(incident.order_id)
            delay_days = max(
                (tools.calculate_delay_days(row) for row in shipments), default=0
            )
            end = self.simulation_date + timedelta(days=self.horizon_days - 1)
            demand = tools.get_demand(incident.component_id, self.simulation_date, end)
            risk = RiskEngine().assess(
                incident_id=incident_id,
                delay_days=delay_days,
                simulation=simulation,
                total_required_demand=sum(row.demand_quantity for row in demand),
            )
            session.add(RiskAssessmentRow(**risk.model_dump(mode="python")))
            routing = ConditionalRouter(
                medium_risk_enabled=self.settings.medium_risk_alternative_research
            ).decide(risk, simulation)
            order = session.get(PurchaseOrderRow, incident.order_id)
            required_quantity = (
                max(0, order.ordered_quantity - order.received_quantity) if order else 0
            )
            session.commit()
        return (
            risk,
            simulation,
            routing,
            required_quantity,
            [item.evidence_id for item in aggregation.evidence],
        )

    def _evaluate_and_persist(
        self,
        incident_id: str,
        workflow_run_id: str,
        plan: RecoveryPlanningOutput,
        evidence_ids: list[str],
        revision: int,
    ) -> StrategyPipelineResult:
        with self.sessions() as session:
            incident = session.get(IncidentRow, incident_id)
            if incident is None:
                raise LookupError(f"incident not found: {incident_id}")
            result = StrategyPipeline(session, self.settings).evaluate(
                incident=incident,
                proposals=plan.proposals,
                maximum_additional_budget=self.settings.maximum_additional_budget,
                evidence_ids=evidence_ids,
            )
            now = datetime.now(timezone.utc)
            for item in result.evaluated:
                session.add(
                    RecoveryStrategyRow(
                        strategy_id=item.strategy.strategy_id,
                        incident_id=incident_id,
                        workflow_run_id=workflow_run_id,
                        strategy_type=item.strategy.strategy_type.value,
                        strategy_data=item.strategy.model_dump(mode="json"),
                        revision_number=revision,
                        created_at=now,
                    )
                )
                session.add(
                    StrategyEvaluationRow(
                        strategy_id=item.strategy.strategy_id,
                        valid=item.evaluation.valid,
                        weighted_score=item.evaluation.weighted_score,
                        evaluation_data=item.evaluation.model_dump(mode="json"),
                        evaluated_at=now,
                    )
                )
                for violation in item.constraints.constraint_violations:
                    session.add(
                        ConstraintViolationRow(
                            strategy_id=item.strategy.strategy_id,
                            constraint_name=violation.constraint_name,
                            expected_value=jsonable_encoder(violation.expected_value),
                            actual_value=jsonable_encoder(violation.actual_value),
                            affected_entity=violation.affected_entity,
                            explanation=violation.explanation,
                        )
                    )
            session.commit()
            return result

    def _persist_supplier_candidates(
        self,
        incident_id: str,
        workflow_run_id: str,
        research: Any,
    ) -> None:
        if not isinstance(research, dict):
            return
        candidates = research.get("candidates") or []
        with self.sessions() as session:
            for candidate in candidates:
                if not isinstance(candidate, dict) or not candidate.get("supplier_id"):
                    continue
                session.add(
                    SupplierCandidateRow(
                        incident_id=incident_id,
                        workflow_run_id=workflow_run_id,
                        supplier_id=candidate["supplier_id"],
                        candidate_data=jsonable_encoder(candidate),
                        eligible=bool(candidate.get("eligible")),
                    )
                )
            session.commit()

    def _persist_reflection(
        self,
        incident_id: str,
        workflow_run_id: str,
        review: ReflectionReview,
        revision: int,
    ) -> None:
        with self.sessions() as session:
            session.add(
                ReflectionRunRow(
                    incident_id=incident_id,
                    workflow_run_id=workflow_run_id,
                    passed=review.passed,
                    result_data=review.model_dump(mode="json"),
                    revision_number=revision,
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

    def _simulate(self, session: Session, incident: IncidentRow) -> SimulationResult | None:
        if not incident.component_id or not incident.order_id:
            return None
        tools = SupplyChainTools(session)
        end = self.simulation_date + timedelta(days=self.horizon_days - 1)
        return SupplySimulator().simulate(
            start_date=self.simulation_date,
            horizon_days=self.horizon_days,
            inventory=tools.get_inventory(incident.component_id),
            demand=tools.get_demand(incident.component_id, self.simulation_date, end),
            shipments=tools.get_shipments(incident.order_id),
            production_requirements=tools.get_production_requirements(
                incident.component_id
            ),
        )

    def _incident_payload(self, incident_id: str) -> dict[str, Any]:
        with self.sessions() as session:
            incident = session.get(IncidentRow, incident_id)
            if incident is None:
                raise LookupError(f"incident not found: {incident_id}")
            return {
                column.name: getattr(incident, column.name)
                for column in incident.__table__.columns
            }

    def _progress(
        self, workflow_run_id: str, phase: str, phase_label: str, percent: int
    ) -> None:
        with self.sessions() as session:
            row = session.get(WorkflowRunRow, workflow_run_id)
            if row is None:
                return
            row.state = {
                **dict(row.state or {}),
                "phase": phase,
                "phase_label": phase_label,
                "progress_percent": percent,
            }
            session.commit()

    def _complete(
        self,
        incident_id: str,
        workflow_run_id: str,
        state: dict[str, Any],
        incident_status: IncidentStatus,
    ) -> None:
        now = datetime.now(timezone.utc)
        with self.sessions() as session:
            row = session.get(WorkflowRunRow, workflow_run_id)
            if row:
                row.status = "COMPLETED"
                row.state = jsonable_encoder(state)
                row.completed_at = now
            incident = session.get(IncidentRow, incident_id)
            if incident:
                incident.status = incident_status.value
                incident.updated_at = now
            session.commit()

    def _fail(self, incident_id: str, workflow_run_id: str, error: Exception) -> None:
        now = datetime.now(timezone.utc)
        message = self._friendly_error(error)
        with self.sessions() as session:
            row = session.get(WorkflowRunRow, workflow_run_id)
            if row:
                row.status = "FAILED"
                row.state = {
                    **dict(row.state or {}),
                    "phase": "FAILED",
                    "phase_label": "Workflow needs attention",
                    "error": message,
                }
                row.completed_at = now
            incident = session.get(IncidentRow, incident_id)
            if incident:
                incident.status = IncidentStatus.FAILED.value
                incident.updated_at = now
            session.commit()

    def _model_candidates(self, preferred: str) -> list[str]:
        configured = [
            item.strip()
            for item in self.settings.gemini_fallback_models.split(",")
            if item.strip()
        ]
        return list(dict.fromkeys([preferred, self.model, *configured]))

    @classmethod
    def _is_transient(cls, error: BaseException) -> bool:
        api_error = cls._find_api_error(error)
        return bool(api_error and getattr(api_error, "code", None) in {429, 500, 502, 503, 504})

    @staticmethod
    def _find_api_error(error: BaseException) -> APIError | None:
        current: BaseException | None = error
        visited: set[int] = set()
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            if isinstance(current, APIError):
                return current
            current = current.__cause__ or current.__context__
        return None

    @classmethod
    def _friendly_error(cls, error: Exception) -> str:
        if isinstance(error, WorkflowUpstreamUnavailableError) or cls._is_transient(error):
            return "Gemini is temporarily busy. The incident is safe to retry."
        api_error = cls._find_api_error(error)
        if api_error:
            return f"Gemini rejected the configured model request (HTTP {getattr(api_error, 'code', 'unknown')})."
        return str(error)[:500]

    @staticmethod
    def _structured_value(value: Any) -> Any:
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            start, end = value.find("{"), value.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(value[start : end + 1])
                except json.JSONDecodeError:
                    pass
        return {"summary": value}
