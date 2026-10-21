from __future__ import annotations

from dataclasses import dataclass

from app.models.domain import RecoveryStrategy, StrategyEvaluation


@dataclass(frozen=True)
class StrategyWeights:
    cost: float = 0.30
    delivery: float = 0.30
    quality: float = 0.20
    risk: float = 0.20

    def __post_init__(self) -> None:
        if abs(self.cost + self.delivery + self.quality + self.risk - 1.0) > 1e-9:
            raise ValueError("strategy weights must sum to 1")


class StrategyScoringEngine:
    FORMULA_VERSION = "strategy-v1"

    def __init__(self, weights: StrategyWeights | None = None) -> None:
        self.weights = weights or StrategyWeights()

    def evaluate(
        self,
        strategy: RecoveryStrategy,
        *,
        valid: bool,
        maximum_modeled_cost: float,
        planning_horizon_days: int,
        expected_delivery_days: float,
        expected_downtime_cost: float,
    ) -> StrategyEvaluation:
        if maximum_modeled_cost <= 0 or planning_horizon_days <= 0:
            raise ValueError("normalization denominators must be positive")
        total_impact = strategy.estimated_additional_cost + expected_downtime_cost
        cost = self._benefit(total_impact / maximum_modeled_cost * 100)
        delivery = self._benefit(expected_delivery_days / planning_horizon_days * 100)
        quality = strategy.estimated_quality
        risk = self._benefit(strategy.residual_risk)
        weighted = cost * self.weights.cost + delivery * self.weights.delivery + quality * self.weights.quality + risk * self.weights.risk
        return StrategyEvaluation(
            strategy_id=strategy.strategy_id,
            valid=valid,
            cost_score=round(cost, 2), delivery_score=round(delivery, 2), quality_score=round(quality, 2), risk_score=round(risk, 2),
            weighted_score=round(weighted, 2), additional_procurement_cost=strategy.estimated_additional_cost,
            expected_downtime_cost=expected_downtime_cost, total_modeled_financial_impact=round(total_impact, 2),
            formula_version=self.FORMULA_VERSION,
        )

    @staticmethod
    def select_best(evaluations: list[StrategyEvaluation]) -> StrategyEvaluation | None:
        valid = [evaluation for evaluation in evaluations if evaluation.valid]
        return max(valid, key=lambda evaluation: evaluation.weighted_score, default=None)

    @staticmethod
    def _benefit(raw_penalty: float) -> float:
        return max(0.0, min(100.0, 100.0 - raw_penalty))

