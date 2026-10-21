from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import delete

from app.config import Settings
from app.database import build_engine, create_schema, session_factory
from app.database.tables import (
    DemandRecordRow,
    InventoryRow,
    ProductionRequirementRow,
    PurchaseOrderRow,
    ShipmentRow,
    SupplierRow,
)


ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def optional_int(value: str) -> int | None:
    return int(value) if value else None


def optional_float(value: str) -> float | None:
    return float(value) if value else None


def seed(database_url: str | None = None, data_dir: Path | None = None) -> dict[str, int]:
    settings = Settings(database_url=database_url or f"sqlite:///{ROOT / 'bottleneck.db'}", data_dir=data_dir or ROOT / "data")
    engine = build_engine(settings.database_url)
    create_schema(engine)
    Session = session_factory(engine)
    counts: dict[str, int] = {}

    suppliers = [SupplierRow(
        supplier_id=r["supplier_id"], supplier_name=r["supplier_name"], component_id=r["component_id"],
        unit_price=float(r["unit_price"]), lead_time_days=int(r["lead_time_days"]), available_capacity=int(r["available_capacity"]),
        capacity_period=r["capacity_period"], quality_score=float(r["quality_score"]), reliability_score=float(r["reliability_score"]),
        on_time_delivery_rate=float(r["on_time_delivery_rate"]), location=r["location"], status=r["status"],
        expedite_supported=r["expedite_supported"].lower() == "true", expedite_lead_time_days=optional_int(r["expedite_lead_time_days"]),
        expedite_unit_surcharge=optional_float(r["expedite_unit_surcharge"]),
    ) for r in read_csv(settings.data_dir / "suppliers.csv")]
    orders = [PurchaseOrderRow(
        order_id=r["order_id"], supplier_id=r["supplier_id"], component_id=r["component_id"], ordered_quantity=int(r["ordered_quantity"]),
        received_quantity=int(r["received_quantity"]), unit_price=float(r["unit_price"]), order_date=date.fromisoformat(r["order_date"]),
        expected_delivery=date.fromisoformat(r["expected_delivery"]), status=r["status"],
    ) for r in read_csv(settings.data_dir / "orders.csv")]
    inventory = [InventoryRow(
        component_id=r["component_id"], warehouse_id=r["warehouse_id"], on_hand_quantity=int(r["on_hand_quantity"]),
        reserved_quantity=int(r["reserved_quantity"]), safety_stock=int(r["safety_stock"]), last_updated=datetime.fromisoformat(r["last_updated"]),
    ) for r in read_csv(settings.data_dir / "inventory.csv")]
    shipments = [ShipmentRow(
        shipment_id=r["shipment_id"], order_id=r["order_id"], shipped_quantity=int(r["shipped_quantity"]),
        received_quantity=int(r["received_quantity"]), shipment_status=r["shipment_status"],
        dispatch_date=date.fromisoformat(r["dispatch_date"]) if r["dispatch_date"] else None,
        original_eta=date.fromisoformat(r["original_eta"]), revised_eta=date.fromisoformat(r["revised_eta"]),
        transport_mode=r["transport_mode"], route=r["route"],
    ) for r in read_csv(settings.data_dir / "shipments.csv")]
    production = [ProductionRequirementRow(
        production_line_id=r["production_line_id"], component_id=r["component_id"], component_units_per_product=float(r["component_units_per_product"]),
        daily_production_capacity=int(r["daily_production_capacity"]), planned_daily_output=int(r["planned_daily_output"]),
        downtime_cost_per_day=float(r["downtime_cost_per_day"]), priority=int(r["priority"]),
    ) for r in read_csv(settings.data_dir / "production.csv")]
    demand = [DemandRecordRow(date=date.fromisoformat(r["date"]), component_id=r["component_id"], demand_quantity=int(r["demand_quantity"])) for r in read_csv(settings.data_dir / "demand.csv")]

    with Session.begin() as session:
        for table in (DemandRecordRow, ShipmentRow, InventoryRow, PurchaseOrderRow, ProductionRequirementRow, SupplierRow):
            session.execute(delete(table))
        for name, rows in (("suppliers", suppliers), ("purchase_orders", orders), ("inventory", inventory), ("shipments", shipments), ("production_requirements", production), ("demand_records", demand)):
            session.add_all(rows)
            counts[name] = len(rows)
    engine.dispose()
    return counts


if __name__ == "__main__":
    result = seed()
    print("seeded " + ", ".join(f"{name}={count}" for name, count in result.items()))

