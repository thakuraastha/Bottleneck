from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.tables import IncidentRow, PurchaseOrderRow, SupplierRow, SupplyChainEventRow
from app.models.domain import IncidentStatus, SupplyChainEvent, utc_now


class EventValidationError(ValueError):
    pass


@dataclass(frozen=True)
class EventIngestionResult:
    event_id: str
    incident_id: str
    duplicate: bool
    incident_created: bool


class EventService:
    """Persist-first, idempotent event ingestion with explicit incident matching."""

    MATCH_WINDOW_DAYS = 7

    def __init__(self, session: Session) -> None:
        self.session = session

    def ingest(self, event: SupplyChainEvent) -> EventIngestionResult:
        existing = self.session.scalar(select(SupplyChainEventRow).where(
            SupplyChainEventRow.idempotency_key == event.idempotency_key
        ))
        if existing is not None:
            if existing.incident_id is None:
                raise EventValidationError("duplicate event exists but has not been linked to an incident")
            return EventIngestionResult(existing.event_id, existing.incident_id, True, False)

        self._validate_entity_references(event)
        row = SupplyChainEventRow(
            event_id=event.event_id,
            event_type=event.event_type.value,
            source_system=event.source_system,
            entity_id=event.entity_id,
            timestamp=event.timestamp,
            payload=event.payload,
            correlation_id=event.correlation_id,
            idempotency_key=event.idempotency_key,
        )
        self.session.add(row)
        self.session.commit()  # Persist before incident matching or processing.

        incident = self._match_active_incident(event)
        created = incident is None
        now = utc_now()
        if incident is None:
            incident = IncidentRow(
                incident_id=str(uuid4()),
                title=event.payload.get("title") or f"{event.event_type.value}: {event.entity_id}",
                description=event.payload.get("description") or f"Incident created from {event.source_system} event {event.event_id}",
                event_type=event.event_type.value,
                status=IncidentStatus.NEW.value,
                supplier_id=event.payload.get("supplier_id"),
                component_id=event.payload.get("component_id"),
                order_id=event.payload.get("order_id"),
                source_event_id=event.event_id,
                detected_at=event.timestamp,
                created_at=now,
                updated_at=now,
            )
            self.session.add(incident)
        else:
            incident.updated_at = now
            incident.description = f"{incident.description}\nCorrelated event {event.event_id}: {event.event_type.value}"
        row.incident_id = incident.incident_id
        row.processed_at = now
        self.session.commit()
        return EventIngestionResult(event.event_id, incident.incident_id, False, created)

    def _match_active_incident(self, event: SupplyChainEvent) -> IncidentRow | None:
        supplier_id = event.payload.get("supplier_id")
        component_id = event.payload.get("component_id")
        if not supplier_id and not component_id:
            return None
        statement = (
            select(IncidentRow)
            .where(IncidentRow.event_type == event.event_type.value)
            .where(IncidentRow.status.in_([
                IncidentStatus.NEW.value,
                IncidentStatus.INVESTIGATING.value,
                IncidentStatus.WAITING_FOR_APPROVAL.value,
                IncidentStatus.REJECTED.value,
            ]))
            .where(IncidentRow.detected_at >= event.timestamp - timedelta(days=self.MATCH_WINDOW_DAYS))
            .order_by(IncidentRow.created_at.desc())
        )
        if supplier_id:
            statement = statement.where(IncidentRow.supplier_id == supplier_id)
        if component_id:
            statement = statement.where(IncidentRow.component_id == component_id)
        return self.session.scalar(statement.limit(1))

    def _validate_entity_references(self, event: SupplyChainEvent) -> None:
        supplier_id = event.payload.get("supplier_id")
        order_id = event.payload.get("order_id")
        component_id = event.payload.get("component_id")
        if not any((supplier_id, order_id, component_id)):
            raise EventValidationError("payload requires at least one supplier_id, order_id, or component_id")
        if supplier_id and self.session.get(SupplierRow, supplier_id) is None:
            raise EventValidationError(f"unknown supplier_id: {supplier_id}")
        if order_id:
            order = self.session.get(PurchaseOrderRow, order_id)
            if order is None:
                raise EventValidationError(f"unknown order_id: {order_id}")
            if supplier_id and order.supplier_id != supplier_id:
                raise EventValidationError("order_id does not belong to supplier_id")
            if component_id and order.component_id != component_id:
                raise EventValidationError("order_id does not match component_id")

