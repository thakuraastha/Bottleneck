from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.models.domain import RiskAssessment, Severity
from app.simulation.supply import SimulationResult


@dataclass(frozen=True)
class RiskThresholds:
    maximum_delay_days: int = 20
    material_financial_exposure: float = 250_000
    delivery_weight: float = 0.25
    inventory_weight: float = 0.30
    financial_weight: float = 0.20
    production_weight: float = 0.25

    def __post_init__(self) -> None:
        weights = (self.delivery_weight, self.inventory_weight, self.financial_weight, self.production_weight)
        if abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError("risk weights must sum to 1")
        if self.maximum_delay_days <= 0 or self.material_financial_exposure <= 0:
            raise ValueError("normalization thresholds must be positive")


class RiskEngine:
    FORMULA_VERSION = "risk-v1"

    def __init__(self, thresholds: RiskThresholds | None = None) -> None:
        self.thresholds = thresholds or RiskThresholds()

    def assess(
        self,
        *,
        incident_id: str,
        delay_days: int,
        simulation: SimulationResult,
        total_required_demand: int,
    ) -> RiskAssessment:
        horizon_days = len(simulation.daily_projection)
        delivery = self._bounded(delay_days / self.thresholds.maximum_delay_days * 100)
        inventory = self._bounded(
            simulation.total_shortage_quantity / max(1, total_required_demand) * 100
            + self._urgency_points(simulation.first_safety_stock_breach_date, simulation.start_date, horizon_days)
        )
        financial = self._bounded(simulation.financial_exposure / self.thresholds.material_financial_exposure * 100)
        production = self._bounded(simulation.estimated_downtime_days / max(1, horizon_days) * 100)
        overall = (
            delivery * self.thresholds.delivery_weight
            + inventory * self.thresholds.inventory_weight
            + financial * self.thresholds.financial_weight
            + production * self.thresholds.production_weight
        )
        return RiskAssessment(
            incident_id=incident_id,
            delivery_score=round(delivery, 2),
            inventory_score=round(inventory, 2),
            financial_score=round(financial, 2),
            production_score=round(production, 2),
            overall_score=round(overall, 2),
            severity=self.classify(overall),
            formula_version=self.FORMULA_VERSION,
        )

    @staticmethod
    def classify(score: float) -> Severity:
        if not 0 <= score <= 100:
            raise ValueError("risk score must be between 0 and 100")
        if score < 30:
            return Severity.LOW
        if score < 60:
            return Severity.MEDIUM
        if score < 80:
            return Severity.HIGH
        return Severity.CRITICAL

    @staticmethod
    def _bounded(value: float) -> float:
        return max(0.0, min(100.0, value))

    @staticmethod
    def _urgency_points(breach: date | None, start: date, horizon_days: int) -> float:
        if breach is None:
            return 0.0
        days_to_breach = max(0, (breach - start).days)
        return 30.0 * max(0.0, 1.0 - days_to_breach / max(1, horizon_days))

