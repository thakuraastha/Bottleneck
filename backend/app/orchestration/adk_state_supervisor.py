from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AdkStateSupervisorOutput(BaseModel):
    """Structured validation of the shared Google ADK session state."""

    incident_id: str
    status: str
    completed_outputs: list[str] = Field(default_factory=list)
    missing_outputs: list[str] = Field(default_factory=list)
    framework_handoffs: list[str] = Field(default_factory=list)
    summary: str


def run_adk_state_supervisor(
    *,
    incident_id: str,
    shared_state: dict[str, Any],
    required_outputs: list[str],
) -> AdkStateSupervisorOutput:
    """Validate typed handoffs already published to the ADK session state."""

    completed = [key for key in required_outputs if shared_state.get(key) is not None]
    missing = [key for key in required_outputs if key not in completed]
    status = "READY" if not missing else "INCOMPLETE"
    summary = (
        f"Validated {len(completed)} shared ADK outputs; all required investigation "
        "handoffs are ready."
        if not missing
        else f"Validated {len(completed)} shared ADK outputs; missing: {', '.join(missing)}."
    )
    return AdkStateSupervisorOutput(
        incident_id=incident_id,
        status=status,
        completed_outputs=completed,
        missing_outputs=missing,
        framework_handoffs=[
            "Google ADK specialist outputs -> ADK session state",
            "ADK session-state validation -> deterministic risk engine",
        ],
        summary=summary,
    )
