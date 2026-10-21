from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.database import build_engine, session_factory
from app.database.tables import IncidentRow
from app.models.domain import IncidentStatus
from app.models.investigations import ProposedAllocation, ProposedStrategy
from app.services import StrategyPipeline
from scripts.seed_database import seed


ROOT = Path(__file__).resolve().parents[2]


def proposal(kind: str, allocations: list[tuple[str, int, bool]]) -> ProposedStrategy:
    return ProposedStrategy(
        strategy_type=kind,
        allocations=[ProposedAllocation(supplier_id=supplier, quantity=quantity, expedite=expedite) for supplier, quantity, expedite in allocations],
        rationale="test proposal",
        supporting_evidence_ids=["EV-1"],
    )


def test_pipeline_simulates_scores_and_excludes_invalid_capacity_strategy(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'strategies.db'}"
    seed(database_url=url, data_dir=ROOT / "data")
    engine = build_engine(url)
    Session = session_factory(engine)
    with Session.begin() as session:
        incident = IncidentRow(
            incident_id="INC-X7", title="X7 delay", description="test", event_type="SUPPLIER_DELAY",
            status=IncidentStatus.INVESTIGATING.value, supplier_id="SUP-A", component_id="MOTOR-X7",
            order_id="PO-X7-1001", source_event_id=None,
            detected_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            created_at=datetime(2026, 1, 15, tzinfo=timezone.utc), updated_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        )
        session.add(incident)
    with Session() as session:
        incident = session.get(IncidentRow, "INC-X7")
        result = StrategyPipeline(session, Settings(database_url=url, data_dir=ROOT / "data")).evaluate(
            incident=incident,
            proposals=[
                proposal("WAIT", [("SUP-A", 1000, False)]),
                proposal("EXPEDITE", [("SUP-A", 1000, True)]),
                proposal("PARTIAL_SWITCH", [("SUP-A", 550, False), ("SUP-B", 450, False)]),
                proposal("SPLIT_ORDER", [("SUP-B", 450, False), ("SUP-D", 250, False), ("SUP-C", 300, False)]),
                proposal("FULL_SWITCH", [("SUP-B", 1000, False)]),
            ],
            maximum_additional_budget=100_000,
            evidence_ids=["EV-BASELINE"],
        )
        assert len(result.evaluated) == 5
        full_switch = next(item for item in result.evaluated if item.strategy.strategy_type.value == "FULL_SWITCH")
        assert full_switch.evaluation.valid is False
        assert any(v.constraint_name == "supplier_capacity" for v in full_switch.constraints.constraint_violations)
        selected = next(item for item in result.evaluated if item.strategy.strategy_id == result.recommended_strategy_id)
        assert selected.evaluation.valid is True
        assert selected.strategy.strategy_type.value == "PARTIAL_SWITCH"
    engine.dispose()
