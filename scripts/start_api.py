from __future__ import annotations

from pathlib import Path
import os

from dotenv import load_dotenv
from sqlalchemy import func, select
from uvicorn import run

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

if os.getenv("RENDER_EXTERNAL_URL"):
    os.environ.setdefault("BOTTLENECK_A2A_SUPPLIER_URL", f"{os.environ['RENDER_EXTERNAL_URL'].rstrip('/')}/a2a")
    os.environ.setdefault("BOTTLENECK_CLOUD_DEPLOYMENT_URL", os.environ["RENDER_EXTERNAL_URL"])
if os.getenv("VERCEL"):
    os.environ.setdefault("BOTTLENECK_DATABASE_URL", "sqlite:////tmp/bottleneck.db")
    vercel_host = os.getenv("VERCEL_PROJECT_PRODUCTION_URL") or os.getenv("VERCEL_URL")
    if vercel_host:
        cloud_url = f"https://{vercel_host}"
        os.environ.setdefault("BOTTLENECK_A2A_SUPPLIER_URL", f"{cloud_url}/a2a")
        os.environ.setdefault("BOTTLENECK_CLOUD_DEPLOYMENT_URL", cloud_url)

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
    run("app.api.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
