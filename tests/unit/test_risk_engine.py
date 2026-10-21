from datetime import date

import pytest

from app.engines.risk import RiskEngine, RiskThresholds
from app.models.domain import Severity
from app.simulation import DailyProjection, SimulationResult


@pytest.mark.parametrize(("score", "severity"), [(0, Severity.LOW), (29.999, Severity.LOW), (30, Severity.MEDIUM), (60, Severity.HIGH), (80, Severity.CRITICAL), (100, Severity.CRITICAL)])
def test_non_overlapping_risk_boundaries(score: float, severity: Severity) -> None:
    assert RiskEngine.classify(score) == severity


def test_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        RiskThresholds(delivery_weight=0.5)


def test_assessment_is_formula_driven() -> None:
    daily = [DailyProjection(date=date(2026, 1, 15), starting_available_stock=0, confirmed_usable_receipts=0, required_consumption=100, projected_ending_stock=0, safety_stock=100, below_safety_stock=True, shortage_quantity=100, production_interrupted=True)]
    simulation = SimulationResult(
        component_id="MOTOR-X7", start_date=date(2026, 1, 15), end_date=date(2026, 1, 15),
        first_safety_stock_breach_date=date(2026, 1, 15), first_actual_shortage_date=date(2026, 1, 15),
        total_shortage_quantity=100, unfulfilled_production_demand=100, estimated_downtime_days=1,
        financial_exposure=250_000, no_shortage_within_horizon=False, daily_projection=daily,
    )
    result = RiskEngine().assess(incident_id="INC-1", delay_days=20, simulation=simulation, total_required_demand=100)
    assert result.delivery_score == 100
    assert result.inventory_score == 100
    assert result.financial_score == 100
    assert result.production_score == 100
    assert result.overall_score == 100
    assert result.severity == Severity.CRITICAL

