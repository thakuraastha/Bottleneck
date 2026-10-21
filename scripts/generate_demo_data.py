from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SIMULATION_DATE = date(2026, 1, 15)


def write_csv(name: str, rows: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / name
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_datasets() -> dict[str, list[dict]]:
    suppliers = [
        {"supplier_id": "SUP-A", "supplier_name": "Supplier A", "component_id": "MOTOR-X7", "unit_price": 100, "lead_time_days": 10, "available_capacity": 1400, "capacity_period": "30_DAYS", "quality_score": 94, "reliability_score": 72, "on_time_delivery_rate": 0.78, "location": "Pune, IN", "status": "ACTIVE", "expedite_supported": "false", "expedite_lead_time_days": "", "expedite_unit_surcharge": ""},
        {"supplier_id": "SUP-B", "supplier_name": "Supplier B", "component_id": "MOTOR-X7", "unit_price": 118, "lead_time_days": 4, "available_capacity": 450, "capacity_period": "30_DAYS", "quality_score": 91, "reliability_score": 93, "on_time_delivery_rate": 0.96, "location": "Chennai, IN", "status": "ACTIVE", "expedite_supported": "false", "expedite_lead_time_days": "", "expedite_unit_surcharge": ""},
        {"supplier_id": "SUP-C", "supplier_name": "Supplier C", "component_id": "MOTOR-X7", "unit_price": 91, "lead_time_days": 24, "available_capacity": 1200, "capacity_period": "30_DAYS", "quality_score": 86, "reliability_score": 81, "on_time_delivery_rate": 0.84, "location": "Shenzhen, CN", "status": "ACTIVE", "expedite_supported": "false", "expedite_lead_time_days": "", "expedite_unit_surcharge": ""},
        {"supplier_id": "SUP-D", "supplier_name": "Supplier D", "component_id": "MOTOR-X7", "unit_price": 108, "lead_time_days": 6, "available_capacity": 250, "capacity_period": "30_DAYS", "quality_score": 97, "reliability_score": 90, "on_time_delivery_rate": 0.94, "location": "Bengaluru, IN", "status": "ACTIVE", "expedite_supported": "true", "expedite_lead_time_days": 3, "expedite_unit_surcharge": 22},
        {"supplier_id": "SUP-E", "supplier_name": "Supplier E", "component_id": "MOTOR-X7", "unit_price": 84, "lead_time_days": 5, "available_capacity": 900, "capacity_period": "30_DAYS", "quality_score": 74, "reliability_score": 76, "on_time_delivery_rate": 0.80, "location": "Hanoi, VN", "status": "QUALITY_HOLD", "expedite_supported": "false", "expedite_lead_time_days": "", "expedite_unit_surcharge": ""},
        {"supplier_id": "SUP-F", "supplier_name": "Supplier F", "component_id": "CONTROL-Z2", "unit_price": 42, "lead_time_days": 7, "available_capacity": 2000, "capacity_period": "30_DAYS", "quality_score": 95, "reliability_score": 94, "on_time_delivery_rate": 0.97, "location": "Noida, IN", "status": "ACTIVE", "expedite_supported": "false", "expedite_lead_time_days": "", "expedite_unit_surcharge": ""},
    ]
    orders = [
        {"order_id": "PO-X7-1001", "supplier_id": "SUP-A", "component_id": "MOTOR-X7", "ordered_quantity": 1000, "received_quantity": 0, "unit_price": 100, "order_date": "2026-01-05", "expected_delivery": "2026-01-20", "status": "DELAYED"},
        {"order_id": "PO-Z2-2001", "supplier_id": "SUP-F", "component_id": "CONTROL-Z2", "ordered_quantity": 800, "received_quantity": 200, "unit_price": 42, "order_date": "2026-01-08", "expected_delivery": "2026-01-18", "status": "PARTIALLY_RECEIVED"},
    ]
    inventory = [
        {"component_id": "MOTOR-X7", "warehouse_id": "WH-PUNE", "on_hand_quantity": 650, "reserved_quantity": 50, "safety_stock": 200, "last_updated": "2026-01-15T08:00:00+00:00"},
        {"component_id": "CONTROL-Z2", "warehouse_id": "WH-PUNE", "on_hand_quantity": 900, "reserved_quantity": 100, "safety_stock": 250, "last_updated": "2026-01-15T08:00:00+00:00"},
    ]
    shipments = [
        {"shipment_id": "SHP-X7-1001", "order_id": "PO-X7-1001", "shipped_quantity": 1000, "received_quantity": 0, "shipment_status": "DELAYED_IN_TRANSIT", "dispatch_date": "2026-01-10", "original_eta": "2026-01-20", "revised_eta": "2026-01-30", "transport_mode": "ROAD", "route": "Pune Supplier Hub -> WH-PUNE"},
        {"shipment_id": "SHP-Z2-2001", "order_id": "PO-Z2-2001", "shipped_quantity": 800, "received_quantity": 200, "shipment_status": "IN_TRANSIT", "dispatch_date": "2026-01-12", "original_eta": "2026-01-18", "revised_eta": "2026-01-18", "transport_mode": "ROAD", "route": "Noida -> WH-PUNE"},
    ]
    production = [
        {"production_line_id": "LINE-1", "component_id": "MOTOR-X7", "component_units_per_product": 1, "daily_production_capacity": 120, "planned_daily_output": 100, "downtime_cost_per_day": 25000, "priority": 1},
        {"production_line_id": "LINE-2", "component_id": "CONTROL-Z2", "component_units_per_product": 2, "daily_production_capacity": 140, "planned_daily_output": 100, "downtime_cost_per_day": 18000, "priority": 2},
    ]
    demand = []
    for offset in range(31):
        day = SIMULATION_DATE + timedelta(days=offset)
        x7_demand = 80 if day.weekday() >= 5 else (120 if day.day in {19, 26} else 100)
        demand.extend([
            {"date": day.isoformat(), "component_id": "MOTOR-X7", "demand_quantity": x7_demand},
            {"date": day.isoformat(), "component_id": "CONTROL-Z2", "demand_quantity": 200 if day.weekday() < 5 else 120},
        ])
    return {"suppliers.csv": suppliers, "orders.csv": orders, "inventory.csv": inventory, "shipments.csv": shipments, "production.csv": production, "demand.csv": demand}


def main() -> None:
    datasets = build_datasets()
    for name, rows in datasets.items():
        write_csv(name, rows)
        print(f"wrote {len(rows):>3} rows to {DATA_DIR / name}")


if __name__ == "__main__":
    main()
