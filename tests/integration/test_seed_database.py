from pathlib import Path

from sqlalchemy import func, select

from app.database import build_engine, create_schema, session_factory
from app.database.tables import (
    DemandRecordRow,
    InventoryRow,
    PurchaseOrderRow,
    ShipmentRow,
    SupplierRow,
)
from scripts.seed_database import seed


ROOT = Path(__file__).resolve().parents[2]


def test_seed_is_repeatable_and_relationships_are_consistent(tmp_path: Path) -> None:
    database_path = tmp_path / "test.db"
    database_url = f"sqlite:///{database_path}"
    first = seed(database_url=database_url, data_dir=ROOT / "data")
    second = seed(database_url=database_url, data_dir=ROOT / "data")
    assert first == second
    assert first == {
        "suppliers": 6,
        "purchase_orders": 2,
        "inventory": 2,
        "shipments": 2,
        "production_requirements": 2,
        "demand_records": 62,
    }

    engine = build_engine(database_url)
    create_schema(engine)
    Session = session_factory(engine)
    with Session() as session:
        order = session.get(PurchaseOrderRow, "PO-X7-1001")
        supplier = session.get(SupplierRow, order.supplier_id)
        shipment = session.get(ShipmentRow, "SHP-X7-1001")
        inventory = session.scalar(select(InventoryRow).where(InventoryRow.component_id == "MOTOR-X7"))
        demand_count = session.scalar(select(func.count()).select_from(DemandRecordRow))

        assert supplier.supplier_name == "Supplier A"
        assert order.ordered_quantity == shipment.shipped_quantity == 1000
        assert shipment.revised_eta > shipment.original_eta
        assert inventory.on_hand_quantity - inventory.reserved_quantity == 600
        assert demand_count == 62
    engine.dispose()

