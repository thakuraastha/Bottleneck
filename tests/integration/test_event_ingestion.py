from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.database import build_engine, create_schema, session_factory
from app.database.tables import IncidentRow, SupplyChainEventRow
from app.events import EventService
from app.events.service import EventValidationError
from app.models.domain import EventType, SupplyChainEvent
from scripts.seed_database import seed


ROOT = Path(__file__).resolve().parents[2]


def event(key: str, *, event_id: str, timestamp: datetime | None = None) -> SupplyChainEvent:
    return SupplyChainEvent(
        event_id=event_id,
        event_type=EventType.SUPPLIER_DELAY,
        source_system="demo_generator",
        entity_id="PO-X7-1001",
        timestamp=timestamp or datetime(2026, 1, 15, 9, tzinfo=timezone.utc),
        payload={"supplier_id": "SUP-A", "component_id": "MOTOR-X7", "order_id": "PO-X7-1001"},
        idempotency_key=key,
    )


def test_duplicate_event_returns_same_incident_without_duplicate_rows(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'events.db'}"
    seed(database_url=url, data_dir=ROOT / "data")
    engine = build_engine(url)
    Session = session_factory(engine)
    with Session() as session:
        service = EventService(session)
        first = service.ingest(event("delay-1", event_id="EV-1"))
        duplicate = service.ingest(event("delay-1", event_id="EV-DUPLICATE"))
        assert first.incident_id == duplicate.incident_id
        assert duplicate.duplicate is True
        assert session.query(SupplyChainEventRow).count() == 1
        assert session.query(IncidentRow).count() == 1
    engine.dispose()


def test_related_event_within_window_updates_existing_incident(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'matching.db'}"
    seed(database_url=url, data_dir=ROOT / "data")
    engine = build_engine(url)
    Session = session_factory(engine)
    with Session() as session:
        service = EventService(session)
        first = service.ingest(event("delay-1", event_id="EV-1"))
        second = service.ingest(event("delay-2", event_id="EV-2", timestamp=datetime(2026, 1, 17, tzinfo=timezone.utc)))
        assert second.incident_id == first.incident_id
        assert second.incident_created is False
        assert session.query(SupplyChainEventRow).count() == 2
        assert session.query(IncidentRow).count() == 1
    engine.dispose()


def test_invalid_reference_is_rejected_before_event_persistence(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'invalid.db'}"
    seed(database_url=url, data_dir=ROOT / "data")
    engine = build_engine(url)
    Session = session_factory(engine)
    with Session() as session:
        bad = event("bad", event_id="EV-BAD").model_copy(update={"payload": {"supplier_id": "UNKNOWN"}})
        with pytest.raises(EventValidationError, match="unknown supplier"):
            EventService(session).ingest(bad)
        assert session.query(SupplyChainEventRow).count() == 0
    engine.dispose()

