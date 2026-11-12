from app.orchestration.adk_state_supervisor import run_adk_state_supervisor


def test_adk_state_supervisor_validates_required_outputs() -> None:
    result = run_adk_state_supervisor(
        incident_id="INC-1",
        shared_state={"triage_output": {"ok": True}, "investigation_supplier": {"ok": True}},
        required_outputs=["triage_output", "investigation_supplier"],
    )
    assert result.status == "READY"
    assert result.missing_outputs == []
    assert "ADK session state" in result.framework_handoffs[0]


def test_adk_state_supervisor_reports_missing_handoffs() -> None:
    result = run_adk_state_supervisor(
        incident_id="INC-1",
        shared_state={"triage_output": {"ok": True}},
        required_outputs=["triage_output", "investigation_supplier"],
    )
    assert result.status == "INCOMPLETE"
    assert result.missing_outputs == ["investigation_supplier"]
