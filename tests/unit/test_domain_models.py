from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.domain import (
    DecisionType,
    EvidenceItem,
    EvidenceType,
    HumanDecision,
    InventoryRecord,
    PurchaseOrder,
)


def test_available_inventory_excludes_reserved_stock() -> None:
    inventory = InventoryRecord(
        component_id="MOTOR-X7",
        warehouse_id="WH-PUNE",
        on_hand_quantity=650,
        reserved_quantity=50,
        safety_stock=200,
        last_updated=datetime(2026, 1, 15, tzinfo=timezone.utc),
    )
    assert inventory.available_quantity == 600


def test_purchase_order_rejects_over_receipt() -> None:
    with pytest.raises(ValidationError, match="cannot exceed"):
        PurchaseOrder(
            order_id="PO-1",
            supplier_id="SUP-A",
            component_id="MOTOR-X7",
            ordered_quantity=100,
            received_quantity=101,
            unit_price=100,
            order_date=date(2026, 1, 1),
            expected_delivery=date(2026, 1, 10),
            status="RECEIVED",
        )


def test_inferred_evidence_requires_confidence() -> None:
    with pytest.raises(ValidationError, match="requires confidence"):
        EvidenceItem(
            incident_id="INC-1",
            evidence_type=EvidenceType.INFERRED_RISK,
            field="supplier_disruption_likely",
            value=True,
            source_system="risk_analyst",
            source_record_id="RUN-1",
            observed_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        )


def test_rejection_requires_reason() -> None:
    with pytest.raises(ValidationError, match="rejection reason"):
        HumanDecision(
            incident_id="INC-1",
            strategy_id="STR-1",
            decision=DecisionType.REJECT,
            decided_by="manager@example.com",
        )

