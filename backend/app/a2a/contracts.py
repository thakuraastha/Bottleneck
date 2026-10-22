from __future__ import annotations

from pydantic import BaseModel, Field

from app.crews.supplier_research import SupplierResearchResult


class SupplierResearchA2ARequest(BaseModel):
    component_id: str = Field(min_length=1, max_length=100)
    requested_quantity: int = Field(gt=0)
    minimum_quality: float = Field(ge=0, le=100)
    incident_id: str | None = Field(default=None, max_length=100)
    workflow_run_id: str | None = Field(default=None, max_length=100)


class SupplierResearchA2AResponse(BaseModel):
    protocol: str = "A2A"
    protocol_version: str = "0.3.0"
    sender_framework: str = "CrewAI"
    receiver_framework: str = "Google ADK"
    agent_name: str = "alternative_supplier_research_crew"
    status: str = "COMPLETED"
    result: SupplierResearchResult
