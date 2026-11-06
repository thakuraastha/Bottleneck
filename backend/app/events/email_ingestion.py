from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.tables import EvidenceRow, PurchaseOrderRow, SupplierRow
from app.models.domain import EventType, SupplyChainEvent, utc_now

from .service import EventIngestionResult, EventService, EventValidationError


@dataclass(frozen=True)
class EmailIngestionResult:
    ingestion: EventIngestionResult
    event_type: EventType
    supplier_id: str | None
    component_id: str | None
    order_id: str | None
    evidence_id: str | None


class EmailPayload(Protocol):
    message_id: str
    sender: str
    subject: str
    body: str
    received_at: datetime


class EmailIncidentService:
    """Convert an email payload into a validated, source-linked incident."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def ingest(self, email: EmailPayload) -> EmailIngestionResult:
        searchable = f"{email.subject}\n{email.body}".lower()
        suppliers = self.session.scalars(select(SupplierRow)).all()
        supplier = next(
            (
                row
                for row in suppliers
                if row.supplier_id.lower() in searchable
                or row.supplier_name.lower() in searchable
            ),
            None,
        )
        orders = self.session.scalars(select(PurchaseOrderRow)).all()
        order = next((row for row in orders if row.order_id.lower() in searchable), None)
        if order is None and supplier is not None:
            order = next((row for row in orders if row.supplier_id == supplier.supplier_id), None)
        if supplier is None and order is not None:
            supplier = self.session.get(SupplierRow, order.supplier_id)

        component_ids = sorted({row.component_id for row in suppliers})
        component_id = (
            order.component_id
            if order
            else supplier.component_id
            if supplier
            else next((item for item in component_ids if item.lower() in searchable), None)
        )
        if not any((supplier, order, component_id)):
            raise EventValidationError(
                "email must mention a known supplier, purchase order, or component identifier"
            )

        event_type = self._classify(searchable)
        event = SupplyChainEvent(
            event_type=event_type,
            source_system="EMAIL",
            entity_id=order.order_id if order else supplier.supplier_id if supplier else component_id or email.message_id,
            timestamp=email.received_at,
            payload={
                "title": email.subject,
                "description": email.body,
                "supplier_id": supplier.supplier_id if supplier else None,
                "component_id": component_id,
                "order_id": order.order_id if order else None,
                "email_message_id": email.message_id,
                "email_sender": email.sender,
            },
            correlation_id=f"email:{email.message_id}",
            idempotency_key=f"email:{email.message_id}",
        )
        ingestion = EventService(self.session).ingest(event)
        evidence_id = None
        if not ingestion.duplicate:
            evidence_id = str(uuid4())
            self.session.add(
                EvidenceRow(
                    evidence_id=evidence_id,
                    incident_id=ingestion.incident_id,
                    evidence_type="VERIFIED_FACT",
                    field="supplier_failure_email",
                    value={
                        "sender": email.sender,
                        "subject": email.subject,
                        "body": email.body,
                        "message_id": email.message_id,
                    },
                    unit=None,
                    source_system="EMAIL",
                    source_record_id=email.message_id,
                    observed_at=email.received_at,
                    created_at=utc_now(),
                    confidence_if_inferred=None,
                )
            )
            self.session.commit()
        return EmailIngestionResult(
            ingestion=ingestion,
            event_type=event_type,
            supplier_id=supplier.supplier_id if supplier else None,
            component_id=component_id,
            order_id=order.order_id if order else None,
            evidence_id=evidence_id,
        )

    @staticmethod
    def _classify(text: str) -> EventType:
        if any(word in text for word in ("quality", "defect", "rejected", "inspection")):
            return EventType.QUALITY_FAILURE
        if any(word in text for word in ("capacity", "shutdown", "factory failure", "cannot produce")):
            return EventType.SUPPLIER_CAPACITY_FAILURE
        if any(word in text for word in ("price", "surcharge", "cost increase")):
            return EventType.PRICE_INCREASE
        if any(word in text for word in ("shipment", "transit", "port", "logistics")):
            return EventType.SHIPMENT_DELAY
        return EventType.SUPPLIER_DELAY
