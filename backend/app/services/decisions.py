from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.tables import (
    ExecutionPlanRow,
    HumanDecisionRow,
    IncidentRow,
    RecoveryStrategyRow,
    ReflectionRunRow,
    StrategyEvaluationRow,
)
from app.models.domain import DecisionType, HumanDecision, IncidentStatus, utc_now


class DecisionConflictError(ValueError):
    pass


@dataclass(frozen=True)
class DecisionResult:
    decision_id: int
    incident_status: str
    execution_plan_id: str | None
    duplicate: bool


class HumanDecisionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(self, decision: HumanDecision) -> DecisionResult:
        existing = self.session.scalar(select(HumanDecisionRow).where(
            HumanDecisionRow.incident_id == decision.incident_id,
            HumanDecisionRow.strategy_id == decision.strategy_id,
            HumanDecisionRow.decision == decision.decision.value,
            HumanDecisionRow.decided_by == decision.decided_by,
        ))
        if existing:
            plan = self.session.scalar(select(ExecutionPlanRow).where(ExecutionPlanRow.incident_id == decision.incident_id))
            incident = self._incident(decision.incident_id)
            return DecisionResult(existing.decision_id, incident.status, plan.execution_plan_id if plan else None, True)

        incident = self._incident(decision.incident_id)
        if incident.status not in {IncidentStatus.WAITING_FOR_APPROVAL.value, IncidentStatus.REJECTED.value}:
            raise DecisionConflictError(f"incident status {incident.status} does not accept a human decision")
        strategy = self.session.get(RecoveryStrategyRow, decision.strategy_id)
        if strategy is None or strategy.incident_id != decision.incident_id:
            raise DecisionConflictError("strategy does not belong to incident")

        execution_plan_id = None
        if decision.decision == DecisionType.APPROVE:
            evaluation = self.session.scalar(select(StrategyEvaluationRow).where(
                StrategyEvaluationRow.strategy_id == decision.strategy_id
            ).order_by(StrategyEvaluationRow.evaluated_at.desc()))
            reflection = self.session.scalar(select(ReflectionRunRow).where(
                ReflectionRunRow.incident_id == decision.incident_id
            ).order_by(ReflectionRunRow.revision_number.desc()))
            if evaluation is None or not evaluation.valid:
                raise DecisionConflictError("an invalid or unevaluated strategy cannot be approved")
            if reflection is None or not reflection.passed:
                raise DecisionConflictError("reflection must pass before approval")
            incident.status = IncidentStatus.APPROVED.value
            plan = ExecutionPlanRow(
                execution_plan_id=str(uuid4()),
                incident_id=decision.incident_id,
                strategy_id=decision.strategy_id,
                plan_data={
                    "strategy": strategy.strategy_data,
                    "authorization": "HUMAN_APPROVED_PLAN_ONLY",
                    "real_orders_executed": False,
                },
                created_at=utc_now(),
            )
            self.session.add(plan)
            execution_plan_id = plan.execution_plan_id
        else:
            incident.status = IncidentStatus.REJECTED.value

        row = HumanDecisionRow(**decision.model_dump(mode="python"))
        self.session.add(row)
        incident.updated_at = utc_now()
        self.session.commit()
        self.session.refresh(row)
        return DecisionResult(row.decision_id, incident.status, execution_plan_id, False)

    def _incident(self, incident_id: str) -> IncidentRow:
        incident = self.session.get(IncidentRow, incident_id)
        if incident is None:
            raise LookupError(f"incident not found: {incident_id}")
        return incident

