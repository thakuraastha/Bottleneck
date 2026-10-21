from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import func, select
from uvicorn import run

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

from app.config import get_settings
from app.database import build_engine, create_schema, session_factory
from app.database.tables import SupplierRow
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


if __name__ == "__main__":
    initialize()
    run("app.api.main:app", host="0.0.0.0", port=8000)
