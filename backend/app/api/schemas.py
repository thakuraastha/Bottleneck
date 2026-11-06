from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str
    detail: str


class EventIngestionResponse(BaseModel):
    event_id: str
    incident_id: str
    duplicate: bool
    incident_created: bool


class EmailIncidentRequest(BaseModel):
    message_id: str = Field(min_length=1, max_length=200)
    sender: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=3, max_length=500)
    body: str = Field(min_length=10, max_length=20_000)
    received_at: datetime


class EmailIncidentResponse(EventIngestionResponse):
    event_type: str
    supplier_id: str | None
    component_id: str | None
    order_id: str | None
    evidence_id: str | None


class DecisionRequest(BaseModel):
    strategy_id: str
    decided_by: str
    reason: str | None = None


class DecisionResponse(BaseModel):
    decision_id: int
    incident_status: str
    execution_plan_id: str | None
    duplicate: bool


class StatusResponse(BaseModel):
    incident_id: str
    status: str
    latest_workflow_status: str | None


class IncidentReportResponse(BaseModel):
    incident: dict[str, Any]
    risk_assessment: dict[str, Any] | None
    strategies: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    execution_plan: dict[str, Any] | None
    disclaimer: str


class CriterionEvidence(BaseModel):
    criterion: int
    title: str
    status: Literal["PASS", "READY", "NEEDS_ACTION"]
    implementation: str
    evidence: list[str]


class ComplianceResponse(BaseModel):
    project: str
    generated_at: datetime
    passed: int
    total: int
    criteria: list[CriterionEvidence]

