from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.tables import IncidentMemoryRow


class IncidentMemoryService:
    """Historical context that keeps planned, predicted, and observed data distinct."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_context(self, *, supplier_id: str | None, component_id: str | None, limit: int = 10) -> list[dict]:
        statement = select(IncidentMemoryRow)
        if supplier_id:
            statement = statement.where(IncidentMemoryRow.supplier_id == supplier_id)
        if component_id:
            statement = statement.where(IncidentMemoryRow.component_id == component_id)
        rows = self.session.scalars(statement.order_by(IncidentMemoryRow.record_timestamp.desc()).limit(limit)).all()
        return [{column.name: getattr(row, column.name) for column in row.__table__.columns} for row in rows]

    def record_approved_plan(
        self,
        *,
        incident_id: str,
        supplier_id: str | None,
        component_id: str | None,
        incident_type: str,
        selected_strategy: str,
        approved_allocations: list[dict],
        estimated_cost: float,
        estimated_downtime: float,
        historical_delay: int | None = None,
    ) -> IncidentMemoryRow:
        row = IncidentMemoryRow(
            incident_id=incident_id, supplier_id=supplier_id, component_id=component_id,
            incident_type=incident_type, historical_delay=historical_delay,
            historical_impact={"status": "PREDICTED"}, selected_strategy=selected_strategy,
            approved_allocations=approved_allocations, estimated_cost=estimated_cost,
            actual_cost_if_known=None, estimated_downtime=estimated_downtime,
            actual_downtime_if_known=None, recovery_outcome=None,
            record_timestamp=datetime.now(timezone.utc),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def record_observed_outcome(self, *, memory_id: int, actual_cost: float, actual_downtime: float, recovery_outcome: str) -> IncidentMemoryRow:
        row = self.session.get(IncidentMemoryRow, memory_id)
        if row is None:
            raise LookupError(f"incident memory not found: {memory_id}")
        row.actual_cost_if_known = actual_cost
        row.actual_downtime_if_known = actual_downtime
        row.recovery_outcome = recovery_outcome
        historical = dict(row.historical_impact or {})
        historical["status"] = "OBSERVED"
        row.historical_impact = historical
        self.session.commit()
        return row

