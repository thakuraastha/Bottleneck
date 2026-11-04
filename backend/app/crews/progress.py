from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database.tables import AgentRunRow, WorkflowRunRow


class CrewProgressRecorder:
    """Publish sequential CrewAI task progress into the shared workflow trace."""

    TASKS = (
        (
            "retrieve_supplier_candidates",
            "crewai_supplier_researcher",
            "Supplier Researcher",
            "crewai_supplier_researcher",
        ),
        (
            "compare_supplier_candidates",
            "crewai_supplier_analyst",
            "Supplier Analyst",
            "crewai_supplier_analyst",
        ),
        (
            "review_supplier_candidates",
            "crewai_supplier_reviewer",
            "Supplier Reviewer",
            "crewai_supplier_reviewer",
        ),
    )

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        incident_id: str,
        workflow_run_id: str,
    ) -> None:
        self.sessions = sessions
        self.incident_id = incident_id
        self.workflow_run_id = workflow_run_id

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def start(self) -> None:
        now = self._now()
        with self.sessions() as session:
            if session.get(WorkflowRunRow, self.workflow_run_id) is None:
                return
            for index, (_, agent_name, _, _) in enumerate(self.TASKS):
                row = self._row(session, agent_name)
                if row is None:
                    session.add(
                        AgentRunRow(
                            execution_id=str(uuid4()),
                            incident_id=self.incident_id,
                            workflow_run_id=self.workflow_run_id,
                            agent_name=agent_name,
                            start_time=now,
                            status="RUNNING" if index == 0 else "PENDING",
                            retry_count=0,
                            model_identifier="crewai/sequential-role",
                            token_usage={},
                        )
                    )
            session.commit()

    def task_completed(self, task_output: Any) -> None:
        task_name = str(getattr(task_output, "name", "") or "")
        task_index = next(
            (index for index, item in enumerate(self.TASKS) if item[0] == task_name),
            None,
        )
        if task_index is None:
            return
        _, agent_name, role, output_key = self.TASKS[task_index]
        now = self._now()
        raw = str(getattr(task_output, "raw", task_output)).strip()[:6000]
        role_output = {
            "role": role,
            "task_name": task_name,
            "status": "COMPLETED",
            "output": raw,
        }
        with self.sessions() as session:
            row = self._row(session, agent_name)
            if row is not None:
                row.status = "COMPLETED"
                row.end_time = now
                started_at = row.start_time
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                row.duration_ms = max((now - started_at).total_seconds() * 1000, 0)
            workflow = session.get(WorkflowRunRow, self.workflow_run_id)
            if workflow is not None:
                state = dict(workflow.state or {})
                outputs = dict(state.get("agent_outputs") or {})
                outputs[output_key] = jsonable_encoder(role_output)
                workflow.state = {**state, "agent_outputs": outputs}
            if task_index + 1 < len(self.TASKS):
                next_row = self._row(session, self.TASKS[task_index + 1][1])
                if next_row is not None and next_row.status == "PENDING":
                    next_row.status = "RUNNING"
                    next_row.start_time = now
            session.commit()

    def fail(self, error: Exception) -> None:
        now = self._now()
        with self.sessions() as session:
            rows = session.scalars(
                select(AgentRunRow).where(
                    AgentRunRow.workflow_run_id == self.workflow_run_id,
                    AgentRunRow.agent_name.in_([item[1] for item in self.TASKS]),
                    AgentRunRow.status.in_(["RUNNING", "PENDING"]),
                )
            ).all()
            for row in rows:
                row.status = "FAILED"
                row.error = str(error)[:500]
                row.end_time = now
            session.commit()

    def _row(self, session: Session, agent_name: str) -> AgentRunRow | None:
        return session.scalar(
            select(AgentRunRow).where(
                AgentRunRow.workflow_run_id == self.workflow_run_id,
                AgentRunRow.agent_name == agent_name,
                AgentRunRow.tool_name.is_(None),
            )
        )
