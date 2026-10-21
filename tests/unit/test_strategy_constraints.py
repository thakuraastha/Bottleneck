from datetime import date

from app.engines.constraints import ConstraintContext, ConstraintValidationEngine
from app.engines.strategy import StrategyScoringEngine
from app.models.domain import RecoveryStrategy, StrategyType, Supplier, SupplierAllocation, ValidationStatus


def supplier(supplier_id: str, capacity: int, quality: float = 90, status: str = "ACTIVE") -> Supplier:
    return Supplier(
        supplier_id=supplier_id, supplier_name=supplier_id, component_id="MOTOR-X7", unit_price=110,
        lead_time_days=5, available_capacity=capacity, capacity_period="30_DAYS", quality_score=quality,
        reliability_score=90, on_time_delivery_rate=0.95, location="IN", status=status,
    )


def strategy(*allocations: SupplierAllocation, cost: float = 1000, risk: float = 20) -> RecoveryStrategy:
    return RecoveryStrategy(
        strategy_id="STR-1", incident_id="INC-1", strategy_type=StrategyType.SPLIT_ORDER,
        supplier_allocations=list(allocations), expected_arrival_dates=[allocation.expected_arrival_date for allocation in allocations],
        estimated_additional_cost=cost, estimated_downtime=0, estimated_quality=90, residual_risk=risk,
        supporting_evidence=["EV-1"],
    )


def allocation(supplier_id: str, quantity: int) -> SupplierAllocation:
    return SupplierAllocation(supplier_id=supplier_id, quantity=quantity, expected_arrival_date=date(2026, 1, 20), unit_price=110)


def test_constraints_aggregate_capacity_by_supplier() -> None:
    suppliers = {"SUP-B": supplier("SUP-B", 450)}
    candidate = strategy(allocation("SUP-B", 300), allocation("SUP-B", 200))
    result = ConstraintValidationEngine().validate(candidate, ConstraintContext(
        component_id="MOTOR-X7", required_quantity=500, suppliers=suppliers,
        minimum_quality=80, maximum_additional_budget=10_000,
    ))
    assert result.status == ValidationStatus.FAIL
    assert {violation.constraint_name for violation in result.constraint_violations} == {"supplier_capacity"}


def test_invalid_strategy_can_never_be_selected() -> None:
    engine = StrategyScoringEngine()
    high_invalid = engine.evaluate(strategy(allocation("SUP-B", 500), cost=0, risk=0), valid=False, maximum_modeled_cost=100_000, planning_horizon_days=30, expected_delivery_days=0, expected_downtime_cost=0)
    lower_valid = engine.evaluate(strategy(allocation("SUP-C", 500), cost=20_000, risk=30), valid=True, maximum_modeled_cost=100_000, planning_horizon_days=30, expected_delivery_days=10, expected_downtime_cost=10_000)
    assert high_invalid.weighted_score > lower_valid.weighted_score
    assert engine.select_best([high_invalid, lower_valid]) == lower_valid

