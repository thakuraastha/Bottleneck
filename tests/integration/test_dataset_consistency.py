import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def rows(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_csv_foreign_keys_and_component_compatibility() -> None:
    suppliers = rows("suppliers.csv")
    orders = rows("orders.csv")
    shipments = rows("shipments.csv")
    inventory = rows("inventory.csv")
    production = rows("production.csv")
    demand = rows("demand.csv")

    suppliers_by_id = {row["supplier_id"]: row for row in suppliers}
    orders_by_id = {row["order_id"]: row for row in orders}
    inventory_components = {row["component_id"] for row in inventory}

    assert all(order["supplier_id"] in suppliers_by_id for order in orders)
    assert all(order["component_id"] == suppliers_by_id[order["supplier_id"]]["component_id"] for order in orders)
    assert all(shipment["order_id"] in orders_by_id for shipment in shipments)
    assert all(row["component_id"] in inventory_components for row in production)
    assert all(row["component_id"] in inventory_components for row in demand)


def test_motor_x7_scenario_has_required_tradeoffs() -> None:
    candidates = [row for row in rows("suppliers.csv") if row["component_id"] == "MOTOR-X7"]
    primary = next(row for row in candidates if row["supplier_id"] == "SUP-A")
    faster_expensive = next(row for row in candidates if row["supplier_id"] == "SUP-B")
    quality_hold = next(row for row in candidates if row["supplier_id"] == "SUP-E")

    assert int(faster_expensive["lead_time_days"]) < int(primary["lead_time_days"])
    assert float(faster_expensive["unit_price"]) > float(primary["unit_price"])
    assert int(faster_expensive["available_capacity"]) < 1000
    assert quality_hold["status"] == "QUALITY_HOLD"
    assert float(quality_hold["quality_score"]) < 80

