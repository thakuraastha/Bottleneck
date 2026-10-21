from pathlib import Path

import pytest

from app.database import build_engine, create_schema, session_factory
from app.tools.supply_chain import EntityNotFoundError, SupplyChainTools
from scripts.seed_database import seed


ROOT = Path(__file__).resolve().parents[2]


def test_authorized_tools_return_typed_records(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'tools.db'}"
    seed(database_url=url, data_dir=ROOT / "data")
    engine = build_engine(url)
    create_schema(engine)
    Session = session_factory(engine)
    with Session() as session:
        tools = SupplyChainTools(session)
        supplier = tools.get_supplier("SUP-A")
        alternatives = tools.get_component_suppliers("MOTOR-X7")
        inventory = tools.get_inventory("MOTOR-X7")
        shipments = tools.get_shipments("PO-X7-1001")
        assert supplier.supplier_name == "Supplier A"
        assert {candidate.supplier_id for candidate in alternatives} == {"SUP-A", "SUP-B", "SUP-C", "SUP-D"}
        assert sum(record.available_quantity for record in inventory) == 600
        assert tools.calculate_delay_days(shipments[0]) == 10
        with pytest.raises(EntityNotFoundError):
            tools.get_supplier("UNKNOWN")
    engine.dispose()

