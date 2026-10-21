from __future__ import annotations

from datetime import timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.tables import IncidentRow, PurchaseOrderRow
from app.engines import ConstraintContext, ConstraintValidationEngine, StrategyScoringEngine
from app.models.domain import (
    ConstraintResult,
    RecoveryStrategy,
    StrategyEvaluation,
    StrategyType,
    SupplierAllocation,
)
from app.models.investigations import ProposedStrategy
from app.simulation import SimulationResult, SupplySimulator
from app.tools import SupplyChainTools


class EvaluatedStrategy(BaseModel):
    strategy: RecoveryStrategy
    simulation: SimulationResult
    constraints: ConstraintResult
    evaluation: StrategyEvaluation


class StrategyPipelineResult(BaseModel):
    evaluated: list[EvaluatedStrategy] = Field(default_factory=list)
    rejected_proposals: list[dict[str, Any]] = Field(default_factory=list)
    recommended_strategy_id: str | None = None


class StrategyPipeline:
    """Converts AI allocation proposals into deterministic simulations and scores."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.tools = SupplyChainTools(session)
        self.simulator = SupplySimulator()
        self.constraints = ConstraintValidationEngine()
        self.scoring = StrategyScoringEngine()

    def evaluate(
        self,
        *,
        incident: IncidentRow,
        proposals: list[ProposedStrategy],
        maximum_additional_budget: float,
        evidence_ids: list[str],
    ) -> StrategyPipelineResult:
        if not incident.component_id or not incident.order_id or not incident.supplier_id:
            raise ValueError("strategy evaluation requires component_id, order_id, and supplier_id")
        order = self.session.get(PurchaseOrderRow, incident.order_id)
        if order is None:
            raise ValueError(f"purchase order not found: {incident.order_id}")
        required_quantity = max(0, order.ordered_quantity - order.received_quantity)
        suppliers = {supplier.supplier_id: supplier for supplier in self.tools.get_component_suppliers(incident.component_id, active_only=False)}
        start = self.settings.simulation_date
        end = start + timedelta(days=self.settings.planning_horizon_days - 1)
        demand = self.tools.get_demand(incident.component_id, start, end)
        inventory = self.tools.get_inventory(incident.component_id)
        shipments = self.tools.get_shipments(incident.order_id)
        production = self.tools.get_production_requirements(incident.component_id)
        total_demand = sum(row.demand_quantity for row in demand)

        modeled: list[tuple[RecoveryStrategy, SimulationResult, ConstraintResult, float]] = []
        rejected: list[dict[str, Any]] = []
        for proposal in proposals:
            try:
                strategy_type = StrategyType(proposal.strategy_type)
                allocations: list[SupplierAllocation] = []
                for proposed in proposal.allocations:
                    supplier = suppliers.get(proposed.supplier_id)
                    if supplier is None:
                        raise ValueError(f"unknown or component-incompatible supplier: {proposed.supplier_id}")
                    arrival = self._arrival_date(
                        strategy_type=strategy_type,
                        supplier_id=proposed.supplier_id,
                        primary_supplier_id=incident.supplier_id,
                        expedite=proposed.expedite,
                        supplier=supplier,
                        shipments=shipments,
                    )
                    allocations.append(SupplierAllocation(
                        supplier_id=supplier.supplier_id,
                        quantity=proposed.quantity,
                        expected_arrival_date=arrival,
                        unit_price=supplier.unit_price,
                        expedite=proposed.expedite,
                    ))
                new_expenditure = self._additional_expenditure(strategy_type, allocations, incident.supplier_id, suppliers)
                simulated_shipments = shipments if strategy_type == StrategyType.WAIT else []
                simulated_allocations = [] if strategy_type == StrategyType.WAIT else allocations
                simulation = self.simulator.simulate(
                    start_date=start,
                    horizon_days=self.settings.planning_horizon_days,
                    inventory=inventory,
                    demand=demand,
                    shipments=simulated_shipments,
                    strategy_allocations=simulated_allocations,
                    production_requirements=production,
                )
                total_quantity = sum(allocation.quantity for allocation in allocations)
                quality = (
                    sum(suppliers[allocation.supplier_id].quality_score * allocation.quantity for allocation in allocations)
                    / total_quantity if total_quantity else 0
                )
                residual_risk = min(100.0, simulation.total_shortage_quantity / max(1, total_demand) * 100)
                strategy = RecoveryStrategy(
                    incident_id=incident.incident_id,
                    strategy_type=strategy_type,
                    supplier_allocations=allocations,
                    expected_arrival_dates=sorted({allocation.expected_arrival_date for allocation in allocations}),
                    expedite_assumptions=["Supplier source record explicitly supports expedite"] if any(a.expedite for a in allocations) else [],
                    estimated_additional_cost=round(new_expenditure, 2),
                    estimated_downtime=simulation.estimated_downtime_days,
                    estimated_quality=round(quality, 2),
                    residual_risk=round(residual_risk, 2),
                    supporting_evidence=sorted(set(evidence_ids + proposal.supporting_evidence_ids)),
                    assumptions=proposal.assumptions,
                )
                constraint_result = self.constraints.validate(strategy, ConstraintContext(
                    component_id=incident.component_id,
                    required_quantity=required_quantity,
                    suppliers=suppliers,
                    minimum_quality=self.settings.minimum_quality_score,
                    maximum_additional_budget=maximum_additional_budget,
                    planning_end_date=end,
                ))
                delivery_days = (
                    sum((allocation.expected_arrival_date - start).days * allocation.quantity for allocation in allocations)
                    / max(1, sum(allocation.quantity for allocation in allocations))
                    if allocations else self.settings.planning_horizon_days
                )
                modeled.append((strategy, simulation, constraint_result, float(delivery_days)))
            except (ValueError, KeyError) as exc:
                rejected.append({"proposal": proposal.model_dump(mode="json"), "reason": str(exc)})

        maximum_cost = max(
            [strategy.estimated_additional_cost + simulation.financial_exposure for strategy, simulation, _, _ in modeled]
            + [1.0]
        )
        evaluated: list[EvaluatedStrategy] = []
        for strategy, simulation, constraint_result, delivery_days in modeled:
            evaluation = self.scoring.evaluate(
                strategy,
                valid=constraint_result.status.value == "PASS",
                maximum_modeled_cost=maximum_cost,
                planning_horizon_days=self.settings.planning_horizon_days,
                expected_delivery_days=delivery_days,
                expected_downtime_cost=simulation.financial_exposure,
            )
            evaluated.append(EvaluatedStrategy(
                strategy=strategy, simulation=simulation,
                constraints=constraint_result, evaluation=evaluation,
            ))
        best = self.scoring.select_best([item.evaluation for item in evaluated])
        return StrategyPipelineResult(
            evaluated=evaluated,
            rejected_proposals=rejected,
            recommended_strategy_id=best.strategy_id if best else None,
        )

    def _arrival_date(self, *, strategy_type: StrategyType, supplier_id: str, primary_supplier_id: str, expedite: bool, supplier, shipments) -> Any:
        if supplier_id == primary_supplier_id and not expedite:
            if not shipments:
                raise ValueError("WAIT requires a confirmed inbound shipment")
            return max(shipment.revised_eta for shipment in shipments)
        lead_time = supplier.expedite_lead_time_days if expedite and supplier.expedite_lead_time_days is not None else supplier.lead_time_days
        return self.settings.simulation_date + timedelta(days=lead_time)

    @staticmethod
    def _additional_expenditure(strategy_type: StrategyType, allocations: list[SupplierAllocation], primary_supplier_id: str, suppliers: dict) -> float:
        if strategy_type == StrategyType.WAIT:
            return 0.0
        if strategy_type == StrategyType.EXPEDITE:
            return sum((suppliers[a.supplier_id].expedite_unit_surcharge or 0) * a.quantity for a in allocations)
        primary_price = suppliers[primary_supplier_id].unit_price
        return sum(
            max(0.0, allocation.unit_price - primary_price) * allocation.quantity
            for allocation in allocations
            if allocation.supplier_id != primary_supplier_id
        )
