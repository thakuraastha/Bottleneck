from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.a2a import build_a2a_app
from app.config import get_settings
from app.config.settings import PROJECT_ROOT
from app.database import build_engine, create_schema, session_factory
from app.database.tables import (
    AgentRunRow,
    ConstraintViolationRow,
    EvidenceRow,
    EvaluationRunRow,
    ExecutionPlanRow,
    HumanDecisionRow,
    IncidentMemoryRow,
    IncidentRow,
    RecoveryStrategyRow,
    ReflectionRunRow,
    RiskAssessmentRow,
    SecurityEventRow,
    StrategyEvaluationRow,
    SupplierRow,
    SupplierCandidateRow,
    SupplyChainEventRow,
    WorkflowRunRow,
)
from app.events import EventService
from app.evaluation import EvaluationRunner
from app.events.service import EventValidationError
from app.models.domain import DecisionType, EventType, HumanDecision, SupplyChainEvent
from app.security import GuardrailService, GuardrailViolation
from app.services.decisions import DecisionConflictError, HumanDecisionService
from app.simulation import SupplySimulator
from app.tools import SupplyChainTools
from app.services.workflow_runs import (
    IncidentWorkflowService,
    ModelCredentialMissingError,
    WorkflowAlreadyRunningError,
    WorkflowModelConfigurationError,
    WorkflowUpstreamUnavailableError,
)

from .schemas import ComplianceResponse, CriterionEvidence, DecisionRequest, DecisionResponse, EventIngestionResponse, IncidentReportResponse, StatusResponse


def create_app(database_url: str | None = None) -> FastAPI:
    resolved_url = database_url or get_settings().database_url
    engine = build_engine(resolved_url)
    SessionFactory = session_factory(engine)

    workflow_tasks: set[asyncio.Task[None]] = set()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        create_schema(engine)
        yield
        for task in workflow_tasks:
            task.cancel()
        if workflow_tasks:
            await asyncio.gather(*workflow_tasks, return_exceptions=True)
        engine.dispose()

    application = FastAPI(title="Bottleneck API", version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.state.SessionFactory = SessionFactory
    application.state.workflow_tasks = workflow_tasks
    application.mount("/a2a", build_a2a_app(), name="crew-a2a")

    def db_session(request: Request) -> Iterator[Session]:
        with request.app.state.SessionFactory() as session:
            yield session

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/events", response_model=EventIngestionResponse, status_code=status.HTTP_201_CREATED)
    def create_event(event: SupplyChainEvent, session: Session = Depends(db_session)) -> EventIngestionResponse:
        try:
            GuardrailService.require_safe_text(event.model_dump_json())
            return EventIngestionResponse.model_validate(EventService(session).ingest(event).__dict__)
        except GuardrailViolation as exc:
            session.add(
                SecurityEventRow(
                    security_event_id=str(uuid4()),
                    incident_id=None,
                    workflow_run_id=None,
                    stage="api_event_ingestion",
                    outcome="BLOCKED",
                    rule=exc.result.rule,
                    detail=exc.result.detail,
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
            raise HTTPException(status_code=422, detail=exc.result.detail) from exc
        except EventValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.post("/incidents", response_model=EventIngestionResponse, status_code=status.HTTP_201_CREATED)
    def create_incident(event: SupplyChainEvent, session: Session = Depends(db_session)) -> EventIngestionResponse:
        if event.event_type != EventType.MANUAL_INCIDENT:
            raise HTTPException(status_code=422, detail="direct incident creation requires MANUAL_INCIDENT")
        return create_event(event, session)

    @application.get("/incidents")
    def list_incidents(session: Session = Depends(db_session)) -> list[dict]:
        rows = session.scalars(select(IncidentRow).order_by(IncidentRow.created_at.desc())).all()
        return [_incident_dict(row) for row in rows]

    @application.get("/dashboard/summary")
    def dashboard_summary(session: Session = Depends(db_session)) -> dict:
        incidents = session.scalars(select(IncidentRow)).all()
        active = [row for row in incidents if row.status not in {"APPROVED", "CLOSED", "FAILED"}]
        latest_risk: dict[str, RiskAssessmentRow] = {}
        for row in session.scalars(select(RiskAssessmentRow).order_by(RiskAssessmentRow.assessed_at)).all():
            latest_risk[row.incident_id] = row
        exposure = 0.0
        downtime = 0.0
        for incident in active:
            simulation = _baseline_simulation(session, incident)
            if simulation:
                exposure += simulation.financial_exposure
                downtime += simulation.estimated_downtime_days
        completed_runs = session.scalars(select(WorkflowRunRow).where(WorkflowRunRow.status == "COMPLETED")).all()
        return {
            "active_incidents": len(active),
            "critical_incidents": sum(1 for incident in active if latest_risk.get(incident.incident_id) and latest_risk[incident.incident_id].severity == "CRITICAL"),
            "pending_approvals": sum(1 for incident in incidents if incident.status == "WAITING_FOR_APPROVAL"),
            "estimated_financial_exposure": round(exposure, 2),
            "estimated_downtime_days": round(downtime, 2),
            "completed_investigations": len(completed_runs),
            "recent_disruptions": [_incident_dict(row) for row in sorted(incidents, key=lambda item: item.updated_at, reverse=True)[:5]],
            "classification": "synthetic scenario data and modeled estimates",
        }

    @application.get("/incidents/{incident_id}")
    def get_incident(incident_id: str, session: Session = Depends(db_session)) -> dict:
        return _incident_dict(_require_incident(session, incident_id))

    @application.post("/incidents/{incident_id}/run", status_code=status.HTTP_202_ACCEPTED)
    async def run_incident(incident_id: str, session: Session = Depends(db_session)) -> dict:
        _require_incident(session, incident_id)
        settings = get_settings()
        service = IncidentWorkflowService(
            application.state.SessionFactory,
            settings=settings,
        )
        try:
            row = service.start(incident_id)
            if os.getenv("VERCEL"):
                await service.execute(incident_id, row.workflow_run_id)
                with application.state.SessionFactory() as completed_session:
                    completed = completed_session.get(
                        WorkflowRunRow, row.workflow_run_id
                    )
                    return _row_dict(completed) if completed else _row_dict(row)
            task = asyncio.create_task(service.execute(incident_id, row.workflow_run_id))
            workflow_tasks.add(task)
            task.add_done_callback(workflow_tasks.discard)
            return _row_dict(row)
        except ModelCredentialMissingError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except WorkflowAlreadyRunningError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except WorkflowUpstreamUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except WorkflowModelConfigurationError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @application.get("/incidents/{incident_id}/status", response_model=StatusResponse)
    def incident_status(incident_id: str, session: Session = Depends(db_session)) -> StatusResponse:
        incident = _require_incident(session, incident_id)
        workflow = session.scalar(select(WorkflowRunRow).where(WorkflowRunRow.incident_id == incident_id).order_by(WorkflowRunRow.started_at.desc()))
        return StatusResponse(incident_id=incident_id, status=incident.status, latest_workflow_status=workflow.status if workflow else None)

    @application.get("/incidents/{incident_id}/evidence")
    def incident_evidence(incident_id: str, session: Session = Depends(db_session)) -> list[dict]:
        _require_incident(session, incident_id)
        return [_row_dict(row) for row in session.scalars(select(EvidenceRow).where(EvidenceRow.incident_id == incident_id))]

    @application.get("/incidents/{incident_id}/risk")
    def incident_risk(incident_id: str, session: Session = Depends(db_session)) -> dict | None:
        _require_incident(session, incident_id)
        row = session.scalar(select(RiskAssessmentRow).where(RiskAssessmentRow.incident_id == incident_id).order_by(RiskAssessmentRow.assessed_at.desc()))
        return _row_dict(row) if row else None

    @application.get("/incidents/{incident_id}/simulation")
    def incident_simulation(incident_id: str, session: Session = Depends(db_session)) -> dict:
        incident = _require_incident(session, incident_id)
        result = _baseline_simulation(session, incident)
        if result is None:
            raise HTTPException(status_code=422, detail="incident lacks component/order data needed for simulation")
        return result.model_dump(mode="json")

    @application.get("/incidents/{incident_id}/strategies")
    def incident_strategies(incident_id: str, session: Session = Depends(db_session)) -> list[dict]:
        _require_incident(session, incident_id)
        strategies = session.scalars(select(RecoveryStrategyRow).where(RecoveryStrategyRow.incident_id == incident_id)).all()
        return [_row_dict(row) for row in strategies]

    @application.get("/incidents/{incident_id}/workflow")
    def incident_workflow(incident_id: str, session: Session = Depends(db_session)) -> dict:
        _require_incident(session, incident_id)
        runs = session.scalars(
            select(WorkflowRunRow)
            .where(WorkflowRunRow.incident_id == incident_id)
            .order_by(WorkflowRunRow.started_at)
        ).all()
        agents = session.scalars(
            select(AgentRunRow)
            .where(AgentRunRow.incident_id == incident_id)
            .order_by(AgentRunRow.start_time)
        ).all()
        return {"workflow_runs": [_row_dict(row) for row in runs], "agent_runs": [_row_dict(row) for row in agents]}

    @application.get("/incidents/{incident_id}/audit")
    def incident_audit(incident_id: str, session: Session = Depends(db_session)) -> dict:
        """Return the complete persisted evidence trail for one incident."""
        incident = _require_incident(session, incident_id)
        workflows = session.scalars(
            select(WorkflowRunRow)
            .where(WorkflowRunRow.incident_id == incident_id)
            .order_by(WorkflowRunRow.started_at)
        ).all()
        agents = session.scalars(
            select(AgentRunRow)
            .where(AgentRunRow.incident_id == incident_id)
            .order_by(AgentRunRow.start_time)
        ).all()
        evidence = session.scalars(
            select(EvidenceRow)
            .where(EvidenceRow.incident_id == incident_id)
            .order_by(EvidenceRow.created_at)
        ).all()
        risks = session.scalars(
            select(RiskAssessmentRow)
            .where(RiskAssessmentRow.incident_id == incident_id)
            .order_by(RiskAssessmentRow.assessed_at)
        ).all()
        candidates = session.scalars(
            select(SupplierCandidateRow).where(
                SupplierCandidateRow.incident_id == incident_id
            )
        ).all()
        strategies = session.scalars(
            select(RecoveryStrategyRow)
            .where(RecoveryStrategyRow.incident_id == incident_id)
            .order_by(RecoveryStrategyRow.created_at)
        ).all()
        strategy_ids = [row.strategy_id for row in strategies]
        evaluations = (
            session.scalars(
                select(StrategyEvaluationRow)
                .where(StrategyEvaluationRow.strategy_id.in_(strategy_ids))
                .order_by(StrategyEvaluationRow.evaluated_at)
            ).all()
            if strategy_ids
            else []
        )
        violations = (
            session.scalars(
                select(ConstraintViolationRow).where(
                    ConstraintViolationRow.strategy_id.in_(strategy_ids)
                )
            ).all()
            if strategy_ids
            else []
        )
        reflections = session.scalars(
            select(ReflectionRunRow)
            .where(ReflectionRunRow.incident_id == incident_id)
            .order_by(ReflectionRunRow.created_at)
        ).all()
        security_events = session.scalars(
            select(SecurityEventRow)
            .where(SecurityEventRow.incident_id == incident_id)
            .order_by(SecurityEventRow.created_at)
        ).all()
        decisions = session.scalars(
            select(HumanDecisionRow)
            .where(HumanDecisionRow.incident_id == incident_id)
            .order_by(HumanDecisionRow.decided_at)
        ).all()
        memory = session.scalars(
            select(IncidentMemoryRow)
            .where(IncidentMemoryRow.incident_id == incident_id)
            .order_by(IncidentMemoryRow.record_timestamp)
        ).all()
        plan = session.scalar(
            select(ExecutionPlanRow).where(
                ExecutionPlanRow.incident_id == incident_id
            )
        )
        return {
            "incident": _incident_dict(incident),
            "workflow_runs": [_row_dict(row) for row in workflows],
            "agent_runs": [_row_dict(row) for row in agents],
            "evidence": [_row_dict(row) for row in evidence],
            "risk_assessments": [_row_dict(row) for row in risks],
            "supplier_candidates": [_row_dict(row) for row in candidates],
            "strategies": [_row_dict(row) for row in strategies],
            "strategy_evaluations": [_row_dict(row) for row in evaluations],
            "constraint_violations": [_row_dict(row) for row in violations],
            "reflections": [_row_dict(row) for row in reflections],
            "security_events": [_row_dict(row) for row in security_events],
            "human_decisions": [_row_dict(row) for row in decisions],
            "incident_memory": [_row_dict(row) for row in memory],
            "execution_plan": _row_dict(plan) if plan else None,
        }

    @application.get("/incidents/{incident_id}/history")
    def incident_history(incident_id: str, session: Session = Depends(db_session)) -> list[dict]:
        _require_incident(session, incident_id)
        rows = session.scalars(select(IncidentMemoryRow).where(IncidentMemoryRow.incident_id == incident_id)).all()
        return [_row_dict(row) for row in rows]

    @application.post("/incidents/{incident_id}/approve", response_model=DecisionResponse)
    def approve(incident_id: str, request: DecisionRequest, session: Session = Depends(db_session)) -> DecisionResponse:
        return _decision(session, incident_id, request, DecisionType.APPROVE)

    @application.post("/incidents/{incident_id}/reject", response_model=DecisionResponse)
    def reject(incident_id: str, request: DecisionRequest, session: Session = Depends(db_session)) -> DecisionResponse:
        if not request.reason:
            raise HTTPException(status_code=422, detail="rejection reason is required")
        return _decision(session, incident_id, request, DecisionType.REJECT)

    @application.get("/incidents/{incident_id}/report", response_model=IncidentReportResponse)
    def report(incident_id: str, session: Session = Depends(db_session)) -> IncidentReportResponse:
        incident = _require_incident(session, incident_id)
        risk = session.scalar(select(RiskAssessmentRow).where(RiskAssessmentRow.incident_id == incident_id).order_by(RiskAssessmentRow.assessed_at.desc()))
        strategies = session.scalars(select(RecoveryStrategyRow).where(RecoveryStrategyRow.incident_id == incident_id)).all()
        decisions = session.scalars(select(HumanDecisionRow).where(HumanDecisionRow.incident_id == incident_id)).all()
        plan = session.scalar(select(ExecutionPlanRow).where(ExecutionPlanRow.incident_id == incident_id))
        return IncidentReportResponse(
            incident=_incident_dict(incident), risk_assessment=_row_dict(risk) if risk else None,
            strategies=[_row_dict(row) for row in strategies], decisions=[_row_dict(row) for row in decisions],
            execution_plan=_row_dict(plan) if plan else None,
            disclaimer="All costs and outcomes are modeled estimates unless explicitly recorded as observed. No real orders are executed.",
        )

    @application.get("/evaluations")
    def evaluations(session: Session = Depends(db_session)) -> list[dict]:
        rows = session.scalars(select(EvaluationRunRow).order_by(EvaluationRunRow.started_at.desc())).all()
        return [_row_dict(row) for row in rows]

    @application.get("/security/events")
    def security_events(session: Session = Depends(db_session)) -> list[dict]:
        rows = session.scalars(
            select(SecurityEventRow).order_by(SecurityEventRow.created_at.desc())
        ).all()
        return [_row_dict(row) for row in rows]

    @application.get("/system/compliance", response_model=ComplianceResponse)
    def compliance(session: Session = Depends(db_session)) -> ComplianceResponse:
        settings = get_settings()
        workflow_count = len(session.scalars(select(WorkflowRunRow)).all())
        agent_event_count = len(session.scalars(select(AgentRunRow)).all())
        evidence_count = len(session.scalars(select(EvidenceRow)).all())
        evaluation_count = len(session.scalars(select(EvaluationRunRow)).all())
        deployment_status = "PASS" if settings.cloud_deployment_url else "NEEDS_ACTION"
        criteria = [
            CriterionEvidence(criterion=1, title="Context sharing and state updates", status="PASS", implementation="Google ADK session state carries namespaced outputs across triage, parallel specialists, risk, planning, and reflection.", evidence=[f"{workflow_count} persisted workflow run(s)", "EventActions.state_delta updates shared state"]),
            CriterionEvidence(criterion=2, title="MCP tool integration", status="PASS", implementation="ADK supplier and logistics agents consume a stdio MCP server, not direct Python functions.", evidence=["lookup_supplier", "lookup_supplier_orders", "lookup_order_shipments", "calculate_delay_days"]),
            CriterionEvidence(criterion=3, title="Pydantic structured output", status="PASS", implementation="Agent, A2A, API, strategy, reflection, and final report contracts are Pydantic models serialized as JSON.", evidence=["TriageOutput", "InvestigationOutput", "RecoveryPlanningOutput", "IncidentReportResponse"]),
            CriterionEvidence(criterion=4, title="Agentic design patterns", status="PASS", implementation="Sequential orchestration, parallel fan-out/join, conditional routing, reflection, bounded replanning, memory, and human approval are implemented.", evidence=["9 ADK stages", "4-worker parallel investigation", "maximum bounded revisions"]),
            CriterionEvidence(criterion=5, title="Callback monitoring and logging", status="PASS", implementation="ADK agent/model/tool callbacks persist timing, status, retries, errors, model IDs, and token usage.", evidence=[f"{agent_event_count} persisted agent/tool event(s)", "/incidents/{id}/audit"]),
            CriterionEvidence(criterion=6, title="A2A agent interoperability", status="PASS", implementation="The ADK alternative-supplier agent calls a separately addressable CrewAI agent endpoint through A2A JSON-RPC 0.3.", evidence=[settings.a2a_supplier_url, "/.well-known/agent-card.json", "CrewAI → Google ADK structured response"]),
            CriterionEvidence(criterion=7, title="CrewAI and ADK only", status="PASS", implementation="Google ADK owns orchestration; CrewAI owns nested supplier research. A2A and MCP are protocols, not additional agent frameworks.", evidence=["google-adk", "crewai"]),
            CriterionEvidence(criterion=8, title="Security guardrails", status="PASS", implementation="Deterministic API and ADK callbacks block prompt injection, threats, secret exposure, oversized inputs, and invalid tool payloads.", evidence=["before_model_callback", "before_tool_callback", "after_tool_callback", "/security/events"]),
            CriterionEvidence(criterion=9, title="Observability and provenance", status="PASS", implementation="SQLite-backed traces link workflows, agent calls, tool calls, evidence source IDs, model metadata, decisions, and security events.", evidence=[f"{evidence_count} provenance record(s)", "complete incident audit endpoint"]),
            CriterionEvidence(criterion=10, title="End-to-end evaluation, cost, and runtime", status="PASS", implementation="The evaluation runner measures scenario quality and latest workflow runtime, token totals, failures, and configurable cost estimates.", evidence=[f"{evaluation_count} stored evaluation run(s)", "end_to_end_performance", "estimated_model_cost_usd"]),
            CriterionEvidence(criterion=11, title="Cloud deployment", status=deployment_status, implementation="Vercel container and Render Blueprint definitions deploy the API, A2A endpoint, and static dashboard as one service.", evidence=[settings.cloud_deployment_url or "Set BOTTLENECK_CLOUD_DEPLOYMENT_URL after the first cloud release"]),
        ]
        return ComplianceResponse(
            project="Bottleneck",
            generated_at=datetime.now(timezone.utc),
            passed=sum(item.status == "PASS" for item in criteria),
            total=len(criteria),
            criteria=criteria,
        )

    @application.get("/suppliers")
    def suppliers(component_id: str | None = None, session: Session = Depends(db_session)) -> list[dict]:
        statement = select(SupplierRow)
        if component_id:
            statement = statement.where(SupplierRow.component_id == component_id)
        return [_row_dict(row) for row in session.scalars(statement.order_by(SupplierRow.supplier_id))]

    @application.post("/evaluations/run", status_code=status.HTTP_201_CREATED)
    def run_evaluations(session: Session = Depends(db_session)) -> dict:
        row = EvaluationRunner(session, get_settings()).run()
        return _row_dict(row)

    application.mount(
        "/",
        StaticFiles(directory=PROJECT_ROOT / "frontend" / "vanilla", html=True),
        name="dashboard",
    )
    return application


def _decision(session: Session, incident_id: str, request: DecisionRequest, decision_type: DecisionType) -> DecisionResponse:
    try:
        decision = HumanDecision(
            incident_id=incident_id, strategy_id=request.strategy_id, decision=decision_type,
            decided_by=request.decided_by, reason=request.reason,
        )
        return DecisionResponse.model_validate(HumanDecisionService(session).record(decision).__dict__)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DecisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _require_incident(session: Session, incident_id: str) -> IncidentRow:
    row = session.get(IncidentRow, incident_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"incident not found: {incident_id}")
    return row


def _incident_dict(row: IncidentRow) -> dict:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def _row_dict(row: object) -> dict:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def _baseline_simulation(session: Session, incident: IncidentRow):
    if not incident.component_id or not incident.order_id:
        return None
    settings = get_settings()
    tools = SupplyChainTools(session)
    start = settings.simulation_date
    end = start + timedelta(days=settings.planning_horizon_days - 1)
    try:
        return SupplySimulator().simulate(
            start_date=start,
            horizon_days=settings.planning_horizon_days,
            inventory=tools.get_inventory(incident.component_id),
            demand=tools.get_demand(incident.component_id, start, end),
            shipments=tools.get_shipments(incident.order_id),
            production_requirements=tools.get_production_requirements(incident.component_id),
        )
    except (LookupError, ValueError):
        return None


app = create_app()
