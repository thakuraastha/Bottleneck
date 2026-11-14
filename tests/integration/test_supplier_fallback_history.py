from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.database import build_engine, session_factory
from app.database.tables import IncidentRow
from app.services.workflow_runs import IncidentWorkflowService
from scripts.seed_database import seed


ROOT = Path(__file__).resolve().parents[2]


def test_recovery_options_respect_prior_supplier_failures(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'supplier-history.db'}"
    seed(database_url=url, data_dir=ROOT / "data")
    engine = build_engine(url)
    sessions = session_factory(engine)
    now = datetime.now(timezone.utc)
    with sessions.begin() as session:
        session.add_all(
            [
                IncidentRow(
                    incident_id="INC-A",
                    title="Supplier A failed",
                    description="Capacity failure",
                    event_type="SUPPLIER_CAPACITY_FAILURE",
                    status="WAITING_FOR_APPROVAL",
                    supplier_id="SUP-A",
                    component_id="MOTOR-X7",
                    order_id="PO-X7-1001",
                    detected_at=now,
                    created_at=now,
                    updated_at=now,
                ),
                IncidentRow(
                    incident_id="INC-B",
                    title="Supplier B failed",
                    description="Capacity failure",
                    event_type="SUPPLIER_CAPACITY_FAILURE",
                    status="NEW",
                    supplier_id="SUP-B",
                    component_id="MOTOR-X7",
                    order_id="PO-X7-1001",
                    detected_at=now,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )

    service = IncidentWorkflowService(sessions, settings=Settings(database_url=url))
    plan = service._deterministic_recovery_plan("INC-B", "MOTOR-X7", 1000)
    allocated_supplier_sets = [
        {allocation["supplier_id"] for allocation in proposal["allocations"]}
        for proposal in plan["proposals"]
    ]

    assert allocated_supplier_sets
    assert all("SUP-A" not in suppliers for suppliers in allocated_supplier_sets)
    assert all("SUP-B" not in suppliers for suppliers in allocated_supplier_sets)
    assert any("SUP-C" in suppliers for suppliers in allocated_supplier_sets)


def test_supplier_a_failure_offers_full_and_split_choices(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'supplier-choices.db'}"
    seed(database_url=url, data_dir=ROOT / "data")
    engine = build_engine(url)
    sessions = session_factory(engine)
    now = datetime.now(timezone.utc)
    with sessions.begin() as session:
        session.add(
            IncidentRow(
                incident_id="INC-A",
                title="Supplier A failed",
                description="Capacity failure",
                event_type="SUPPLIER_CAPACITY_FAILURE",
                status="NEW",
                supplier_id="SUP-A",
                component_id="MOTOR-X7",
                order_id="PO-X7-1001",
                detected_at=now,
                created_at=now,
                updated_at=now,
            )
        )

    service = IncidentWorkflowService(sessions, settings=Settings(database_url=url))
    plan = service._deterministic_recovery_plan("INC-A", "MOTOR-X7", 1000)
    choices = {
        proposal["strategy_type"]: {
            allocation["supplier_id"] for allocation in proposal["allocations"]
        }
        for proposal in plan["proposals"]
    }

    assert choices["FULL_SWITCH"] == {"SUP-C"}
    assert choices["SPLIT_ORDER"] == {"SUP-B", "SUP-C"}
