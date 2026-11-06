from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import os
from types import SimpleNamespace

from dotenv import load_dotenv
from sqlalchemy import func, select
from uvicorn import run

from runtime_config import configure_platform_environment

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


configure_platform_environment()

from app.config import get_settings
from app.database import build_engine, create_schema, session_factory
from app.database.tables import IncidentRow, SupplierRow
from app.events import EmailIncidentService
from seed_database import seed


def initialize() -> None:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    create_schema(engine)
    sessions = session_factory(engine)
    with sessions() as session:
        supplier_count = session.scalar(select(func.count()).select_from(SupplierRow)) or 0
    engine.dispose()
    if supplier_count == 0:
        seed(database_url=settings.database_url, data_dir=settings.data_dir)
    with sessions() as session:
        incident_count = session.scalar(select(func.count()).select_from(IncidentRow)) or 0
        if incident_count == 0:
            EmailIncidentService(session).ingest(
                SimpleNamespace(
                    message_id="demo-supplier-a-delay-2026-01-15",
                    sender="operations@supplier-a.example",
                    subject="Urgent: SUP-A cannot deliver PO-X7-1001 on schedule",
                    body=(
                        "Supplier A reports a factory capacity failure affecting MOTOR-X7. "
                        "Purchase order PO-X7-1001 for 1,000 units will be delayed beyond "
                        "the 20 January commitment. Please identify qualified replacement "
                        "suppliers and protect Motor X7 production."
                    ),
                    received_at=datetime(2026, 1, 15, 9, tzinfo=timezone.utc),
                )
            )
    engine.dispose()


if __name__ == "__main__":
    initialize()
    run("app.api.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
