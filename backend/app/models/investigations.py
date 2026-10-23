from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_serializer


class SourceReference(BaseModel):
    source_system: str
    source_record_id: str
    fields: list[str] = Field(default_factory=list)


class InvestigationFact(BaseModel):
    field: str
    value: Any
    unit: str | None = None
    source: SourceReference


class InvestigationOutput(BaseModel):
    summary: str
    verified_facts: list[InvestigationFact] = Field(default_factory=list)
    calculated_facts: list[InvestigationFact] = Field(default_factory=list)
    inferred_risks: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    tool_calls_used: list[str] = Field(default_factory=list)


class TriageOutput(BaseModel):
    incident_id: str
    affected_supplier_ids: list[str] = Field(default_factory=list)
    affected_component_ids: list[str] = Field(default_factory=list)
    affected_order_ids: list[str] = Field(default_factory=list)
    investigation_scope: list[str]
    missing_required_identifiers: list[str] = Field(default_factory=list)
    can_proceed: bool
    rationale: str


class SupplierInvestigation(InvestigationOutput):
    supplier_id: str
    active: bool
    available_capacity: int | None = None
    quality_score: float | None = None
    reliability_score: float | None = None


class LogisticsInvestigation(InvestigationOutput):
    order_id: str
    original_eta: date | None = None
    revised_eta: date | None = None
    delay_days: int | None = None
    remaining_inbound_quantity: int = 0

    @field_serializer("original_eta", "revised_eta")
    def serialize_dates(self, value: date | None) -> str | None:
        """Keep ADK's internal structured-response payload JSON serializable."""
        return value.isoformat() if value else None


class InventoryInvestigation(InvestigationOutput):
    component_id: str
    on_hand_quantity: int
    reserved_quantity: int
    available_quantity: int
    safety_stock: int
    first_safety_stock_breach_date: date | None = None
    first_shortage_date: date | None = None
    total_shortage_quantity: int = 0

    @field_serializer("first_safety_stock_breach_date", "first_shortage_date")
    def serialize_dates(self, value: date | None) -> str | None:
        """Keep ADK's internal structured-response payload JSON serializable."""
        return value.isoformat() if value else None


class ProductionInvestigation(InvestigationOutput):
    component_id: str
    affected_line_ids: list[str] = Field(default_factory=list)
    planned_daily_component_requirement: float
    estimated_downtime_days: float
    estimated_financial_exposure: float


class RiskInterpretation(BaseModel):
    incident_id: str
    primary_drivers: list[str]
    secondary_consequences: list[str] = Field(default_factory=list)
    unresolved_uncertainties: list[str] = Field(default_factory=list)
    narrative: str
    evidence_ids: list[str]
    deterministic_score_unchanged: bool


class ProposedAllocation(BaseModel):
    supplier_id: str
    quantity: int = Field(ge=0)
    expedite: bool = False


class ProposedStrategy(BaseModel):
    strategy_type: str
    allocations: list[ProposedAllocation]
    rationale: str
    assumptions: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)


class RecoveryPlanningOutput(BaseModel):
    incident_id: str
    proposals: list[ProposedStrategy] = Field(default_factory=list)
    escalation_required: bool = False
    escalation_reason: str | None = None


class ReflectionReview(BaseModel):
    incident_id: str
    passed: bool
    issues: list[str] = Field(default_factory=list)
    revision_guidance: list[str] = Field(default_factory=list)
    unsupported_assumptions: list[str] = Field(default_factory=list)
    contradictory_recommendations: list[str] = Field(default_factory=list)
    revision_number: int = Field(ge=0)
