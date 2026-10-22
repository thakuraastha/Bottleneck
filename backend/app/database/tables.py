from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SupplierRow(Base):
    __tablename__ = "suppliers"
    __table_args__ = (Index("ix_suppliers_component", "component_id"),)

    supplier_id: Mapped[str] = mapped_column(String, primary_key=True)
    supplier_name: Mapped[str] = mapped_column(String, nullable=False)
    component_id: Mapped[str] = mapped_column(String, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    available_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    capacity_period: Mapped[str] = mapped_column(String, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    reliability_score: Mapped[float] = mapped_column(Float, nullable=False)
    on_time_delivery_rate: Mapped[float] = mapped_column(Float, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    expedite_supported: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expedite_lead_time_days: Mapped[int | None] = mapped_column(Integer)
    expedite_unit_surcharge: Mapped[float | None] = mapped_column(Float)


class PurchaseOrderRow(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        Index("ix_orders_supplier", "supplier_id"),
        Index("ix_orders_component", "component_id"),
    )

    order_id: Mapped[str] = mapped_column(String, primary_key=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"), nullable=False)
    component_id: Mapped[str] = mapped_column(String, nullable=False)
    ordered_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_delivery: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)


class InventoryRow(Base):
    __tablename__ = "inventory"
    __table_args__ = (UniqueConstraint("component_id", "warehouse_id"),)

    inventory_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    component_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String, nullable=False)
    on_hand_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    safety_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ShipmentRow(Base):
    __tablename__ = "shipments"

    shipment_id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.order_id"), index=True)
    shipped_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    shipment_status: Mapped[str] = mapped_column(String, nullable=False)
    dispatch_date: Mapped[date | None] = mapped_column(Date)
    original_eta: Mapped[date] = mapped_column(Date, nullable=False)
    revised_eta: Mapped[date] = mapped_column(Date, nullable=False)
    transport_mode: Mapped[str] = mapped_column(String, nullable=False)
    route: Mapped[str] = mapped_column(String, nullable=False)


class ProductionRequirementRow(Base):
    __tablename__ = "production_requirements"

    production_line_id: Mapped[str] = mapped_column(String, primary_key=True)
    component_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    component_units_per_product: Mapped[float] = mapped_column(Float, nullable=False)
    daily_production_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_daily_output: Mapped[int] = mapped_column(Integer, nullable=False)
    downtime_cost_per_day: Mapped[float] = mapped_column(Float, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)


class DemandRecordRow(Base):
    __tablename__ = "demand_records"
    __table_args__ = (UniqueConstraint("date", "component_id"),)

    demand_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    component_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    demand_quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class SupplyChainEventRow(Base):
    __tablename__ = "supply_chain_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    source_system: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    incident_id: Mapped[str | None] = mapped_column(String, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IncidentRow(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.supplier_id"), index=True)
    component_id: Mapped[str | None] = mapped_column(String, index=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("purchase_orders.order_id"))
    source_event_id: Mapped[str | None] = mapped_column(ForeignKey("supply_chain_events.event_id"))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowRunRow(Base):
    __tablename__ = "workflow_runs"

    workflow_run_id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRunRow(Base):
    __tablename__ = "agent_runs"

    execution_id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    workflow_run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.workflow_run_id"), index=True)
    agent_name: Mapped[str] = mapped_column(String, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_identifier: Mapped[str | None] = mapped_column(String)
    token_usage: Mapped[dict | None] = mapped_column(JSON)


class SecurityEventRow(Base):
    __tablename__ = "security_events"

    security_event_id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_id: Mapped[str | None] = mapped_column(String, index=True)
    workflow_run_id: Mapped[str | None] = mapped_column(String, index=True)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    rule: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class EvidenceRow(Base):
    __tablename__ = "evidence"

    evidence_id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    evidence_type: Mapped[str] = mapped_column(String, nullable=False)
    field: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    unit: Mapped[str | None] = mapped_column(String)
    source_system: Mapped[str] = mapped_column(String, nullable=False)
    source_record_id: Mapped[str] = mapped_column(String, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence_if_inferred: Mapped[float | None] = mapped_column(Float)


class IncidentMemoryRow(Base):
    __tablename__ = "incident_memory"

    memory_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    supplier_id: Mapped[str | None] = mapped_column(String, index=True)
    component_id: Mapped[str | None] = mapped_column(String, index=True)
    incident_type: Mapped[str] = mapped_column(String, nullable=False)
    historical_delay: Mapped[int | None] = mapped_column(Integer)
    historical_impact: Mapped[dict | None] = mapped_column(JSON)
    selected_strategy: Mapped[str | None] = mapped_column(String)
    approved_allocations: Mapped[list | None] = mapped_column(JSON)
    estimated_cost: Mapped[float | None] = mapped_column(Float)
    actual_cost_if_known: Mapped[float | None] = mapped_column(Float)
    estimated_downtime: Mapped[float | None] = mapped_column(Float)
    actual_downtime_if_known: Mapped[float | None] = mapped_column(Float)
    recovery_outcome: Mapped[str | None] = mapped_column(String)
    record_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RiskAssessmentRow(Base):
    __tablename__ = "risk_assessments"

    assessment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    delivery_score: Mapped[float] = mapped_column(Float, nullable=False)
    inventory_score: Mapped[float] = mapped_column(Float, nullable=False)
    financial_score: Mapped[float] = mapped_column(Float, nullable=False)
    production_score: Mapped[float] = mapped_column(Float, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    formula_version: Mapped[str] = mapped_column(String, nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SupplierCandidateRow(Base):
    __tablename__ = "supplier_candidates"

    candidate_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    workflow_run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.workflow_run_id"), index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"), index=True)
    candidate_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)


class RecoveryStrategyRow(Base):
    __tablename__ = "recovery_strategies"

    strategy_id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    workflow_run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.workflow_run_id"), index=True)
    strategy_type: Mapped[str] = mapped_column(String, nullable=False)
    strategy_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StrategyEvaluationRow(Base):
    __tablename__ = "strategy_evaluations"

    evaluation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[str] = mapped_column(ForeignKey("recovery_strategies.strategy_id"), index=True)
    valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    weighted_score: Mapped[float] = mapped_column(Float, nullable=False)
    evaluation_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConstraintViolationRow(Base):
    __tablename__ = "constraint_violations"

    violation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[str] = mapped_column(ForeignKey("recovery_strategies.strategy_id"), index=True)
    constraint_name: Mapped[str] = mapped_column(String, nullable=False)
    expected_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    actual_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    affected_entity: Mapped[str] = mapped_column(String, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)


class ReflectionRunRow(Base):
    __tablename__ = "reflection_runs"

    reflection_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    workflow_run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.workflow_run_id"), index=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    result_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class HumanDecisionRow(Base):
    __tablename__ = "human_decisions"
    __table_args__ = (UniqueConstraint("incident_id", "strategy_id", "decision", "decided_by"),)

    decision_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    strategy_id: Mapped[str] = mapped_column(String, index=True)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    decided_by: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExecutionPlanRow(Base):
    __tablename__ = "execution_plans"

    execution_plan_id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), unique=True, index=True)
    strategy_id: Mapped[str] = mapped_column(String, index=True)
    plan_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IncidentOutcomeRow(Base):
    __tablename__ = "incident_outcomes"

    outcome_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    outcome_type: Mapped[str] = mapped_column(String, nullable=False)
    outcome_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvaluationRunRow(Base):
    __tablename__ = "evaluation_runs"

    evaluation_run_id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    scenario_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
