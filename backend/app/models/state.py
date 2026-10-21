from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .domain import (
    ConstraintResult,
    EvidenceItem,
    HumanDecision,
    Incident,
    RecoveryStrategy,
    ReflectionResult,
    RiskAssessment,
    StrategyEvaluation,
    SupplierCandidate,
    WorkflowStatus,
)


class IncidentState(BaseModel):
    """Typed shared workflow state; parallel outputs are isolated by agent name."""

    incident: Incident
    workflow_run_id: str
    workflow_status: WorkflowStatus = WorkflowStatus.PENDING
    investigation_outputs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    verified_facts: list[EvidenceItem] = Field(default_factory=list)
    calculated_facts: list[EvidenceItem] = Field(default_factory=list)
    inferred_risks: list[EvidenceItem] = Field(default_factory=list)
    risk_assessment: RiskAssessment | None = None
    risk_interpretation: dict[str, Any] | None = None
    historical_context: list[dict[str, Any]] = Field(default_factory=list)
    alternative_suppliers: list[SupplierCandidate] = Field(default_factory=list)
    candidate_strategies: list[RecoveryStrategy] = Field(default_factory=list)
    evaluated_strategies: list[StrategyEvaluation] = Field(default_factory=list)
    recommended_strategy: RecoveryStrategy | None = None
    constraint_results: list[ConstraintResult] = Field(default_factory=list)
    reflection_result: ReflectionResult | None = None
    human_decision: HumanDecision | None = None
    rejection_feedback: list[str] = Field(default_factory=list)
    revision_count: int = Field(default=0, ge=0)
    execution_plan: dict[str, Any] | None = None
    final_report: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)

