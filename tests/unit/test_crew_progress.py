from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import select

from app.crews.progress import CrewProgressRecorder
from app.database import build_engine, create_schema, session_factory
from app.database.tables import AgentRunRow, IncidentRow, WorkflowRunRow


def test_crewai_tasks_publish_sequential_live_progress(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'crew-progress.db'}")
    create_schema(engine)
    sessions = session_factory(engine)
    now = datetime.now(timezone.utc)
    with sessions() as session:
        session.add(
            IncidentRow(
                incident_id="INC-CREW",
                title="Crew progress",
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
                workflow_run_id="RUN-CREW",
                incident_id="INC-CREW",
                status="RUNNING",
                state={"agent_outputs": {}},
                started_at=now,
            )
        )
        session.commit()

    recorder = CrewProgressRecorder(
        sessions, incident_id="INC-CREW", workflow_run_id="RUN-CREW"
    )
    recorder.start()
    with sessions() as session:
        rows = session.scalars(
            select(AgentRunRow).order_by(AgentRunRow.start_time)
        ).all()
        assert [row.status for row in rows] == ["RUNNING", "PENDING", "PENDING"]

    recorder.task_completed(
        SimpleNamespace(name="retrieve_supplier_candidates", raw="five suppliers")
    )
    with sessions() as session:
        rows = {
            row.agent_name: row
            for row in session.scalars(select(AgentRunRow)).all()
        }
        assert rows["crewai_supplier_researcher"].status == "COMPLETED"
        assert rows["crewai_supplier_analyst"].status == "RUNNING"
        workflow = session.get(WorkflowRunRow, "RUN-CREW")
        assert workflow is not None
        assert (
            workflow.state["agent_outputs"]["crewai_supplier_researcher"]["output"]
            == "five suppliers"
        )

    recorder.task_completed(
        SimpleNamespace(name="compare_supplier_candidates", raw="comparison")
    )
    recorder.task_completed(
        SimpleNamespace(name="review_supplier_candidates", raw="validated")
    )
    with sessions() as session:
        rows = session.scalars(select(AgentRunRow)).all()
        assert {row.status for row in rows} == {"COMPLETED"}
        assert all(row.duration_ms is not None for row in rows)
        workflow = session.get(WorkflowRunRow, "RUN-CREW")
        assert workflow is not None
        assert len(workflow.state["agent_outputs"]) == 3
    engine.dispose()
