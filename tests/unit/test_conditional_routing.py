from datetime import date

from app.models.domain import RiskAssessment, Severity
from app.orchestration import ConditionalRouter
from app.simulation import DailyProjection, SimulationResult


def risk(severity: Severity, score: float) -> RiskAssessment:
    return RiskAssessment(
        incident_id="INC-1", delivery_score=score, inventory_score=score,
        financial_score=score, production_score=score, overall_score=score,
        severity=severity, formula_version="test",
    )


def simulation(shortage_date: date | None) -> SimulationResult:
    return SimulationResult(
        component_id="MOTOR-X7", start_date=date(2026, 1, 15), end_date=date(2026, 1, 30),
        first_safety_stock_breach_date=None, first_actual_shortage_date=shortage_date,
        total_shortage_quantity=0 if shortage_date is None else 100,
        unfulfilled_production_demand=0 if shortage_date is None else 100,
        estimated_downtime_days=0, financial_exposure=0,
        no_shortage_within_horizon=shortage_date is None, daily_projection=[],
    )


def test_low_risk_with_adequate_inventory_skips_research() -> None:
    decision = ConditionalRouter().decide(risk(Severity.LOW, 12), simulation(None))
    assert decision.should_run is False
    assert decision.branch == "SKIP_ALTERNATIVE_RESEARCH"


def test_imminent_shortage_overrides_low_weighted_score() -> None:
    decision = ConditionalRouter(imminent_stockout_days=7).decide(
        risk(Severity.LOW, 25), simulation(date(2026, 1, 20))
    )
    assert decision.should_run is True
    assert decision.branch == "ALTERNATIVE_RESEARCH"
    assert decision.evaluated_values["days_to_shortage"] == 5


def test_medium_risk_behavior_is_configurable() -> None:
    assert ConditionalRouter(medium_risk_enabled=True).decide(risk(Severity.MEDIUM, 45), simulation(None)).should_run
    assert not ConditionalRouter(medium_risk_enabled=False).decide(risk(Severity.MEDIUM, 45), simulation(None)).should_run

