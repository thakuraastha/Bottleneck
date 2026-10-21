from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EventType(StrEnum):
    SUPPLIER_DELAY = "SUPPLIER_DELAY"
    INVENTORY_ALERT = "INVENTORY_ALERT"
    SHIPMENT_DELAY = "SHIPMENT_DELAY"
    QUALITY_FAILURE = "QUALITY_FAILURE"
    SUPPLIER_CAPACITY_FAILURE = "SUPPLIER_CAPACITY_FAILURE"
    PRICE_INCREASE = "PRICE_INCREASE"
    MANUAL_INCIDENT = "MANUAL_INCIDENT"


class IncidentStatus(StrEnum):
    NEW = "NEW"
    INVESTIGATING = "INVESTIGATING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"
    FAILED = "FAILED"


class WorkflowStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class EvidenceType(StrEnum):
    VERIFIED_FACT = "VERIFIED_FACT"
    CALCULATED_FACT = "CALCULATED_FACT"
    INFERRED_RISK = "INFERRED_RISK"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class StrategyType(StrEnum):
    WAIT = "WAIT"
    EXPEDITE = "EXPEDITE"
    PARTIAL_SWITCH = "PARTIAL_SWITCH"
    FULL_SWITCH = "FULL_SWITCH"
    SPLIT_ORDER = "SPLIT_ORDER"


class ValidationStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class DecisionType(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class SupplyChainEvent(DomainModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    source_system: str
    entity_id: str
    timestamp: datetime
    payload: dict[str, Any]
    correlation_id: str | None = None
    idempotency_key: str = Field(min_length=1)


class Incident(DomainModel):
    incident_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str
    event_type: EventType
    status: IncidentStatus = IncidentStatus.NEW
    supplier_id: str | None = None
    component_id: str | None = None
    order_id: str | None = None
    source_event_id: str | None = None
    detected_at: datetime
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Supplier(DomainModel):
    supplier_id: str
    supplier_name: str
    component_id: str
    unit_price: float = Field(gt=0)
    lead_time_days: int = Field(ge=0)
    available_capacity: int = Field(ge=0)
    capacity_period: str
    quality_score: float = Field(ge=0, le=100)
    reliability_score: float = Field(ge=0, le=100)
    on_time_delivery_rate: float = Field(ge=0, le=1)
    location: str
    status: str
    expedite_supported: bool = False
    expedite_lead_time_days: int | None = Field(default=None, ge=0)
    expedite_unit_surcharge: float | None = Field(default=None, ge=0)


class PurchaseOrder(DomainModel):
    order_id: str
    supplier_id: str
    component_id: str
    ordered_quantity: int = Field(gt=0)
    received_quantity: int = Field(ge=0)
    unit_price: float = Field(gt=0)
    order_date: date
    expected_delivery: date
    status: str

    @model_validator(mode="after")
    def received_not_above_ordered(self) -> "PurchaseOrder":
        if self.received_quantity > self.ordered_quantity:
            raise ValueError("received_quantity cannot exceed ordered_quantity")
        return self


class Shipment(DomainModel):
    shipment_id: str
    order_id: str
    shipped_quantity: int = Field(ge=0)
    received_quantity: int = Field(ge=0)
    shipment_status: str
    dispatch_date: date | None = None
    original_eta: date
    revised_eta: date
    transport_mode: str
    route: str

    @model_validator(mode="after")
    def received_not_above_shipped(self) -> "Shipment":
        if self.received_quantity > self.shipped_quantity:
            raise ValueError("received_quantity cannot exceed shipped_quantity")
        return self


class InventoryRecord(DomainModel):
    component_id: str
    warehouse_id: str
    on_hand_quantity: int = Field(ge=0)
    reserved_quantity: int = Field(ge=0)
    safety_stock: int = Field(ge=0)
    last_updated: datetime

    @property
    def available_quantity(self) -> int:
        return max(0, self.on_hand_quantity - self.reserved_quantity)


class ProductionRequirement(DomainModel):
    production_line_id: str
    component_id: str
    component_units_per_product: float = Field(gt=0)
    daily_production_capacity: int = Field(gt=0)
    planned_daily_output: int = Field(ge=0)
    downtime_cost_per_day: float = Field(ge=0)
    priority: int = Field(ge=1)


class DemandRecord(DomainModel):
    date: date
    component_id: str
    demand_quantity: int = Field(ge=0)


class EvidenceItem(DomainModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    incident_id: str
    evidence_type: EvidenceType
    field: str
    value: Any
    unit: str | None = None
    source_system: str
    source_record_id: str
    observed_at: datetime
    created_at: datetime = Field(default_factory=utc_now)
    confidence_if_inferred: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def inferred_claim_requires_confidence(self) -> "EvidenceItem":
        if self.evidence_type == EvidenceType.INFERRED_RISK and self.confidence_if_inferred is None:
            raise ValueError("inferred evidence requires confidence_if_inferred")
        return self


class RiskAssessment(DomainModel):
    incident_id: str
    delivery_score: float = Field(ge=0, le=100)
    inventory_score: float = Field(ge=0, le=100)
    financial_score: float = Field(ge=0, le=100)
    production_score: float = Field(ge=0, le=100)
    overall_score: float = Field(ge=0, le=100)
    severity: Severity
    formula_version: str
    assessed_at: datetime = Field(default_factory=utc_now)


class SupplierCandidate(DomainModel):
    supplier: Supplier
    requested_quantity: int = Field(ge=0)
    feasible_quantity: int = Field(ge=0)
    expected_arrival: date
    eligible: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class SupplierAllocation(DomainModel):
    supplier_id: str
    quantity: int = Field(ge=0)
    expected_arrival_date: date
    unit_price: float = Field(gt=0)
    expedite: bool = False


class RecoveryStrategy(DomainModel):
    strategy_id: str = Field(default_factory=lambda: str(uuid4()))
    incident_id: str
    strategy_type: StrategyType
    supplier_allocations: list[SupplierAllocation]
    expected_arrival_dates: list[date]
    expedite_assumptions: list[str] = Field(default_factory=list)
    estimated_additional_cost: float = Field(ge=0)
    estimated_downtime: float = Field(ge=0)
    estimated_quality: float = Field(ge=0, le=100)
    residual_risk: float = Field(ge=0, le=100)
    supporting_evidence: list[str]
    assumptions: list[str] = Field(default_factory=list)


class StrategyEvaluation(DomainModel):
    strategy_id: str
    valid: bool
    cost_score: float = Field(ge=0, le=100)
    delivery_score: float = Field(ge=0, le=100)
    quality_score: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)
    weighted_score: float = Field(ge=0, le=100)
    additional_procurement_cost: float = Field(ge=0)
    expected_downtime_cost: float = Field(ge=0)
    total_modeled_financial_impact: float = Field(ge=0)
    formula_version: str


class ConstraintViolation(DomainModel):
    constraint_name: str
    expected_value: Any
    actual_value: Any
    affected_entity: str
    explanation: str


class ConstraintResult(DomainModel):
    strategy_id: str
    status: ValidationStatus
    constraint_violations: list[ConstraintViolation] = Field(default_factory=list)
    validation_details: dict[str, Any] = Field(default_factory=dict)


class ReflectionResult(DomainModel):
    incident_id: str
    passed: bool
    issues: list[str] = Field(default_factory=list)
    revision_guidance: list[str] = Field(default_factory=list)
    revision_number: int = Field(ge=0)


class HumanDecision(DomainModel):
    incident_id: str
    strategy_id: str
    decision: DecisionType
    decided_by: str
    reason: str | None = None
    decided_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def rejection_requires_reason(self) -> "HumanDecision":
        if self.decision == DecisionType.REJECT and not self.reason:
            raise ValueError("a rejection reason is required")
        return self


class IncidentOutcome(DomainModel):
    incident_id: str
    outcome_type: str
    planned_cost: float | None = Field(default=None, ge=0)
    predicted_cost: float | None = Field(default=None, ge=0)
    actual_cost: float | None = Field(default=None, ge=0)
    planned_downtime: float | None = Field(default=None, ge=0)
    predicted_downtime: float | None = Field(default=None, ge=0)
    actual_downtime: float | None = Field(default=None, ge=0)
    recovery_outcome: str | None = None
    recorded_at: datetime = Field(default_factory=utc_now)


class AgentExecutionRecord(DomainModel):
    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    incident_id: str
    workflow_run_id: str
    agent_name: str
    tool_name: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    status: WorkflowStatus
    error: str | None = None
    retry_count: int = Field(default=0, ge=0)
    model_identifier: str | None = None
    token_usage: dict[str, int] | None = None

