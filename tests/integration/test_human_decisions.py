from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.database import build_engine, create_schema, session_factory
from app.database.tables import (
    ExecutionPlanRow,
    IncidentRow,
    RecoveryStrategyRow,
    ReflectionRunRow,
    StrategyEvaluationRow,
    WorkflowRunRow,
)
from app.models.domain import DecisionType, HumanDecision, IncidentStatus
from app.services.decisions import HumanDecisionService


def test_reapproval_replaces_stale_plan_and_rejection_revokes_it(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'decisions.db'}"
    engine = build_engine(database_url)
    create_schema(engine)
    sessions = session_factory(engine)
    now = datetime.now(timezone.utc)

    with sessions.begin() as session:
        session.add(
            IncidentRow(
                incident_id="INC-DECISION",
                title="Decision lifecycle",
                description="Regression scenario",
                event_type="SUPPLIER_DELAY",
                status=IncidentStatus.WAITING_FOR_APPROVAL.value,
                supplier_id=None,
                component_id="MOTOR-X7",
                order_id=None,
                source_event_id=None,
                detected_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            WorkflowRunRow(
                workflow_run_id="RUN-DECISION",
                incident_id="INC-DECISION",
                status="COMPLETED",
                state={},
                started_at=now,
                completed_at=now,
            )
        )
        for strategy_id in ("STRATEGY-1", "STRATEGY-2"):
            session.add(
                RecoveryStrategyRow(
                    strategy_id=strategy_id,
                    incident_id="INC-DECISION",
                    workflow_run_id="RUN-DECISION",
                    strategy_type="SPLIT_ORDER",
                    strategy_data={"strategy_id": strategy_id},
                    revision_number=0,
                    created_at=now,
                )
            )
            session.add(
                StrategyEvaluationRow(
                    strategy_id=strategy_id,
                    valid=True,
                    weighted_score=90.0,
                    evaluation_data={},
                    evaluated_at=now,
                )
            )
        session.add(
            ReflectionRunRow(
                incident_id="INC-DECISION",
                workflow_run_id="RUN-DECISION",
                passed=True,
                result_data={},
                revision_number=0,
                created_at=now,
            )
        )

    with sessions() as session:
        service = HumanDecisionService(session)
        first = service.record(
            HumanDecision(
                incident_id="INC-DECISION",
                strategy_id="STRATEGY-1",
                decision=DecisionType.APPROVE,
                decided_by="Reviewer One",
            )
        )
        first_plan_id = first.execution_plan_id

        # Test direct re-approval without resetting status to WAITING_FOR_APPROVAL
        second = service.record(
            HumanDecision(
                incident_id="INC-DECISION",
                strategy_id="STRATEGY-2",
                decision=DecisionType.APPROVE,
                decided_by="Reviewer Two",
            )
        )

        plan = session.scalar(
            select(ExecutionPlanRow).where(
                ExecutionPlanRow.incident_id == "INC-DECISION"
            )
        )
        assert second.execution_plan_id == first_plan_id
        assert plan is not None
        assert plan.strategy_id == "STRATEGY-2"
        assert plan.plan_data["strategy"]["strategy_id"] == "STRATEGY-2"

        # Test re-approval with the SAME reviewer
        same_reviewer = service.record(
            HumanDecision(
                incident_id="INC-DECISION",
                strategy_id="STRATEGY-2",
                decision=DecisionType.APPROVE,
                decided_by="Reviewer Two",
                reason="Updated approval note",
            )
        )
        assert same_reviewer.duplicate is True
        assert same_reviewer.execution_plan_id == first_plan_id

        # Test rejecting after approval
        service.record(
            HumanDecision(
                incident_id="INC-DECISION",
                strategy_id="STRATEGY-2",
                decision=DecisionType.REJECT,
                decided_by="Reviewer Three",
                reason="Revise the allocation",
            )
        )
        assert session.scalar(
            select(ExecutionPlanRow).where(
                ExecutionPlanRow.incident_id == "INC-DECISION"
            )
        ) is None

        # Test re-approving after rejection
        third = service.record(
            HumanDecision(
                incident_id="INC-DECISION",
                strategy_id="STRATEGY-1",
                decision=DecisionType.APPROVE,
                decided_by="Reviewer Four",
            )
        )
        assert third.incident_status == IncidentStatus.APPROVED.value
        assert session.scalar(
            select(ExecutionPlanRow).where(
                ExecutionPlanRow.incident_id == "INC-DECISION"
            )
        ) is not None

    engine.dispose()
