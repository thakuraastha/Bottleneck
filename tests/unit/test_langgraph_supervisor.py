from app.orchestration.langgraph_supervisor import run_langgraph_supervisor


def test_langgraph_supervisor_validates_required_adk_outputs() -> None:
    result = run_langgraph_supervisor(
        incident_id="INC-GRAPH",
        shared_state={"triage_output": {"can_proceed": True}, "supplier": {}},
        required_outputs=["triage_output", "supplier"],
    )

    assert result.status == "READY"
    assert result.completed_outputs == ["triage_output", "supplier"]
    assert result.missing_outputs == []
    assert "Google ADK session state -> LangGraph supervisor" in result.framework_handoffs


def test_langgraph_supervisor_reports_missing_handoffs() -> None:
    result = run_langgraph_supervisor(
        incident_id="INC-GRAPH",
        shared_state={"triage_output": {"can_proceed": True}},
        required_outputs=["triage_output", "supplier"],
    )

    assert result.status == "INCOMPLETE"
    assert result.missing_outputs == ["supplier"]
