from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import select

from app.database.base import build_engine, create_schema, session_factory
from app.database.tables import AgentRunRow, IncidentRow, WorkflowRunRow
from app.observability import AdkObservabilityCallbacks


def _context(*, function_call_id: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        state={"incident_id": "INC-OBS", "workflow_run_id": "RUN-OBS"},
        invocation_id="INV-1",
        agent_name="supplier_intelligence_agent",
        attempt_count=2,
        function_call_id=function_call_id,
    )


def _callbacks(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'observability.db'}")
    create_schema(engine)
    sessions = session_factory(engine)
    now = datetime.now(timezone.utc)
    with sessions() as session:
        session.add(
            IncidentRow(
                incident_id="INC-OBS",
                title="Observability test",
                description="test",
                event_type="SUPPLIER_DELAY",
                status="INVESTIGATING",
                detected_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            WorkflowRunRow(
                workflow_run_id="RUN-OBS",
                incident_id="INC-OBS",
                status="RUNNING",
                state={},
                started_at=now,
            )
        )
        session.commit()
    return AdkObservabilityCallbacks(sessions, model_identifier="gemini-test"), sessions


def test_agent_callbacks_persist_completed_lifecycle(tmp_path) -> None:
    callbacks, sessions = _callbacks(tmp_path)
    context = _context()

    callbacks.before_agent(context)
    callbacks.after_agent(context)

    with sessions() as session:
        row = session.scalar(select(AgentRunRow))
        assert row is not None
        assert row.agent_name == "supplier_intelligence_agent"
        assert row.status == "COMPLETED"
        assert row.duration_ms is not None and row.duration_ms >= 0
        assert row.retry_count == 1
        assert row.model_identifier == "gemini-test"


def test_tool_error_callback_persists_failure(tmp_path) -> None:
    callbacks, sessions = _callbacks(tmp_path)
    context = _context(function_call_id="CALL-1")
    tool = SimpleNamespace(name="get_supplier")

    callbacks.before_tool(tool, {"supplier_id": "SUP-A"}, context)
    callbacks.on_tool_error(tool, {}, context, RuntimeError("tool unavailable"))

    with sessions() as session:
        row = session.scalar(select(AgentRunRow))
        assert row is not None
        assert row.tool_name == "get_supplier"
        assert row.status == "FAILED"
        assert row.error == "tool unavailable"


def test_callbacks_without_workflow_scope_do_not_fabricate_events(tmp_path) -> None:
    callbacks, sessions = _callbacks(tmp_path)
    context = _context()
    context.state = {}

    callbacks.before_agent(context)
    callbacks.after_agent(context)

    with sessions() as session:
        assert session.scalar(select(AgentRunRow)) is None


def test_retried_agent_attempts_receive_persisted_ordinals(tmp_path) -> None:
    callbacks, sessions = _callbacks(tmp_path)
    context = _context()
    context.attempt_count = 1

    callbacks.before_agent(context)
    callbacks.on_model_error(context, None, RuntimeError("temporary"))
    callbacks.before_agent(context)
    callbacks.after_agent(context)

    with sessions() as session:
        rows = session.scalars(select(AgentRunRow).order_by(AgentRunRow.start_time)).all()
        assert [row.retry_count for row in rows] == [0, 1]
        assert [row.status for row in rows] == ["FAILED", "COMPLETED"]
