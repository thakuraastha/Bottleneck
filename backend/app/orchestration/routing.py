from __future__ import annotations

from dataclasses import dataclass

from app.models.domain import RiskAssessment, Severity
from app.simulation import SimulationResult


@dataclass(frozen=True)
class AlternativeResearchDecision:
    should_run: bool
    branch: str
    reason: str
    evaluated_values: dict[str, object]


class ConditionalRouter:
    def __init__(self, *, medium_risk_enabled: bool = True, imminent_stockout_days: int = 7) -> None:
        self.medium_risk_enabled = medium_risk_enabled
        self.imminent_stockout_days = imminent_stockout_days

    def decide(self, risk: RiskAssessment, simulation: SimulationResult) -> AlternativeResearchDecision:
        days_to_shortage = (
            (simulation.first_actual_shortage_date - simulation.start_date).days
            if simulation.first_actual_shortage_date is not None else None
        )
        imminent = days_to_shortage is not None and days_to_shortage <= self.imminent_stockout_days
        severity_trigger = risk.severity in {Severity.HIGH, Severity.CRITICAL}
        medium_trigger = risk.severity == Severity.MEDIUM and self.medium_risk_enabled
        should_run = imminent or severity_trigger or medium_trigger
        if imminent:
            reason = f"actual shortage projected in {days_to_shortage} days, within the {self.imminent_stockout_days}-day hard-rule window"
        elif severity_trigger:
            reason = f"{risk.severity.value} deterministic risk requires alternative research"
        elif medium_trigger:
            reason = "MEDIUM-risk routing is enabled"
        else:
            reason = "risk and stock coverage do not trigger alternative research"
        return AlternativeResearchDecision(
            should_run=should_run,
            branch="ALTERNATIVE_RESEARCH" if should_run else "SKIP_ALTERNATIVE_RESEARCH",
            reason=reason,
            evaluated_values={
                "severity": risk.severity.value,
                "overall_score": risk.overall_score,
                "days_to_shortage": days_to_shortage,
                "medium_risk_enabled": self.medium_risk_enabled,
                "imminent_stockout_days": self.imminent_stockout_days,
            },
        )

