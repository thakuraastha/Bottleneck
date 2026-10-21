from datetime import date, datetime, timezone

from app.models.domain import DemandRecord, InventoryRecord, ProductionRequirement
from app.simulation import Receipt, SupplySimulator


def inventory(quantity: int, *, reserved: int = 0, safety: int = 100) -> list[InventoryRecord]:
    return [InventoryRecord(
        component_id="MOTOR-X7", warehouse_id="WH-1", on_hand_quantity=quantity,
        reserved_quantity=reserved, safety_stock=safety,
        last_updated=datetime(2026, 1, 15, tzinfo=timezone.utc),
    )]


def demand(values: list[int]) -> list[DemandRecord]:
    return [DemandRecord(date=date(2026, 1, 15 + index), component_id="MOTOR-X7", demand_quantity=value) for index, value in enumerate(values)]


def production() -> list[ProductionRequirement]:
    return [ProductionRequirement(
        production_line_id="LINE-1", component_id="MOTOR-X7", component_units_per_product=1,
        daily_production_capacity=120, planned_daily_output=100, downtime_cost_per_day=25_000, priority=1,
    )]


def test_simulation_distinguishes_safety_breach_from_shortage() -> None:
    result = SupplySimulator().simulate(
        start_date=date(2026, 1, 15), horizon_days=5, inventory=inventory(450),
        demand=demand([100] * 5), production_requirements=production(),
    )
    assert result.first_safety_stock_breach_date == date(2026, 1, 18)
    assert result.first_actual_shortage_date == date(2026, 1, 19)
    assert result.total_shortage_quantity == 50
    assert result.estimated_downtime_days == 0.5
    assert result.financial_exposure == 12_500


def test_receipt_applies_before_same_day_consumption() -> None:
    result = SupplySimulator().simulate(
        start_date=date(2026, 1, 15), horizon_days=4, inventory=inventory(200),
        demand=demand([100] * 4), receipts=[Receipt(receipt_id="R-1", arrival_date=date(2026, 1, 17), quantity=300, source="test")],
        production_requirements=production(),
    )
    assert result.no_shortage_within_horizon is True
    assert result.daily_projection[2].confirmed_usable_receipts == 300
    assert result.daily_projection[-1].projected_ending_stock == 100


def test_zero_demand_has_no_division_error_or_shortage() -> None:
    result = SupplySimulator().simulate(
        start_date=date(2026, 1, 15), horizon_days=2, inventory=inventory(0, safety=0),
        demand=demand([0, 0]), production_requirements=[],
    )
    assert result.no_shortage_within_horizon is True
    assert result.estimated_downtime_days == 0

