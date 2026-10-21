from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str
    detail: str


class EventIngestionResponse(BaseModel):
    event_id: str
    incident_id: str
    duplicate: bool
    incident_created: bool


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

