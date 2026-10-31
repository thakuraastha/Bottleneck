from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field


class LangGraphSupervisorOutput(BaseModel):
    """Structured result published by the LangGraph shared-state supervisor."""

    incident_id: str
    status: str
    completed_outputs: list[str] = Field(default_factory=list)
    missing_outputs: list[str] = Field(default_factory=list)
    framework_handoffs: list[str] = Field(default_factory=list)
    summary: str


class SupervisorState(TypedDict, total=False):
    incident_id: str
    shared_state: dict[str, Any]
    required_outputs: list[str]
    completed_outputs: list[str]
    missing_outputs: list[str]
    framework_handoffs: list[str]
    status: str
    summary: str


def _inspect_shared_state(state: SupervisorState) -> dict[str, Any]:
    shared_state = state.get("shared_state", {})
    required = state.get("required_outputs", [])
    completed = [key for key in required if shared_state.get(key) is not None]
    missing = [key for key in required if key not in completed]
    return {
        "completed_outputs": completed,
        "missing_outputs": missing,
        "status": "READY" if not missing else "INCOMPLETE",
    }


def _publish_supervision(state: SupervisorState) -> dict[str, Any]:
    completed = state.get("completed_outputs", [])
    missing = state.get("missing_outputs", [])
    handoffs = [
        "Google ADK session state -> LangGraph supervisor",
        "LangGraph validation -> deterministic risk engine",
    ]
    summary = (
        f"Validated {len(completed)} shared ADK outputs; all required investigation "
        "handoffs are ready."
        if not missing
        else f"Validated {len(completed)} shared ADK outputs; missing: {', '.join(missing)}."
    )
    return {"framework_handoffs": handoffs, "summary": summary}


def build_supervisor_graph():
    """Build a real LangGraph StateGraph used in every live workflow run."""

    graph = StateGraph(SupervisorState)
    graph.add_node("inspect_shared_state", _inspect_shared_state)
    graph.add_node("publish_supervision", _publish_supervision)
    graph.add_edge(START, "inspect_shared_state")
    graph.add_edge("inspect_shared_state", "publish_supervision")
    graph.add_edge("publish_supervision", END)
    return graph.compile()


def run_langgraph_supervisor(
    *,
    incident_id: str,
    shared_state: dict[str, Any],
    required_outputs: list[str],
) -> LangGraphSupervisorOutput:
    result = build_supervisor_graph().invoke(
        {
            "incident_id": incident_id,
            "shared_state": shared_state,
            "required_outputs": required_outputs,
        }
    )
    return LangGraphSupervisorOutput(
        incident_id=incident_id,
        status=str(result.get("status", "INCOMPLETE")),
        completed_outputs=list(result.get("completed_outputs", [])),
        missing_outputs=list(result.get("missing_outputs", [])),
        framework_handoffs=list(result.get("framework_handoffs", [])),
        summary=str(result.get("summary", "LangGraph supervision completed.")),
    )
