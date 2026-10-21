from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, Field

from app.models.domain import DemandRecord, InventoryRecord, ProductionRequirement, Shipment, SupplierAllocation


class Receipt(BaseModel):
    receipt_id: str
    arrival_date: date
    quantity: int = Field(ge=0)
    usable: bool = True
    source: str


class DailyProjection(BaseModel):
    date: date
    starting_available_stock: int
    confirmed_usable_receipts: int
    required_consumption: int
    projected_ending_stock: int
    safety_stock: int
    below_safety_stock: bool
    shortage_quantity: int
    production_interrupted: bool


class SimulationResult(BaseModel):
    component_id: str
    start_date: date
    end_date: date
    first_safety_stock_breach_date: date | None
    first_actual_shortage_date: date | None
    total_shortage_quantity: int
    unfulfilled_production_demand: int
    estimated_downtime_days: float
    financial_exposure: float
    no_shortage_within_horizon: bool
    daily_projection: list[DailyProjection]


class SupplySimulator:
    """Daily material-flow simulation shared by baseline and recovery strategies."""

    def simulate(
        self,
        *,
        start_date: date,
        horizon_days: int,
        inventory: list[InventoryRecord],
        demand: list[DemandRecord],
        receipts: list[Receipt] | None = None,
        shipments: list[Shipment] | None = None,
        strategy_allocations: list[SupplierAllocation] | None = None,
        production_requirements: list[ProductionRequirement] | None = None,
    ) -> SimulationResult:
        if horizon_days < 1:
            raise ValueError("horizon_days must be at least 1")
        if not inventory:
            raise ValueError("at least one inventory record is required")
        component_ids = {record.component_id for record in inventory}
        if len(component_ids) != 1:
            raise ValueError("inventory records must belong to one component")
        component_id = next(iter(component_ids))
        if any(record.component_id != component_id for record in demand):
            raise ValueError("demand component does not match inventory component")

        available = sum(record.available_quantity for record in inventory)
        safety_stock = sum(record.safety_stock for record in inventory)
        demand_by_date: dict[date, int] = {}
        for record in demand:
            demand_by_date[record.date] = demand_by_date.get(record.date, 0) + record.demand_quantity

        all_receipts = list(receipts or [])
        all_receipts.extend(self._shipment_receipts(shipments or []))
        all_receipts.extend(self._allocation_receipts(strategy_allocations or []))
        receipt_by_date: dict[date, int] = {}
        for receipt in all_receipts:
            if receipt.usable:
                receipt_by_date[receipt.arrival_date] = receipt_by_date.get(receipt.arrival_date, 0) + receipt.quantity

        requirements = production_requirements or []
        daily_component_requirement = sum(
            req.planned_daily_output * req.component_units_per_product for req in requirements
        )
        daily_downtime_cost = sum(req.downtime_cost_per_day for req in requirements)

        first_safety_breach = None
        first_shortage = None
        total_shortage = 0
        timeline: list[DailyProjection] = []
        for offset in range(horizon_days):
            current_date = start_date + timedelta(days=offset)
            starting = available
            inbound = receipt_by_date.get(current_date, 0)
            required = demand_by_date.get(current_date, 0)
            balance = starting + inbound - required
            shortage = max(0, -balance)
            available = max(0, balance)
            below_safety = available < safety_stock
            interrupted = shortage > 0
            if below_safety and first_safety_breach is None:
                first_safety_breach = current_date
            if interrupted and first_shortage is None:
                first_shortage = current_date
            total_shortage += shortage
            timeline.append(DailyProjection(
                date=current_date,
                starting_available_stock=starting,
                confirmed_usable_receipts=inbound,
                required_consumption=required,
                projected_ending_stock=available,
                safety_stock=safety_stock,
                below_safety_stock=below_safety,
                shortage_quantity=shortage,
                production_interrupted=interrupted,
            ))

        downtime_days = total_shortage / daily_component_requirement if daily_component_requirement > 0 else 0.0
        financial_exposure = downtime_days * daily_downtime_cost
        return SimulationResult(
            component_id=component_id,
            start_date=start_date,
            end_date=start_date + timedelta(days=horizon_days - 1),
            first_safety_stock_breach_date=first_safety_breach,
            first_actual_shortage_date=first_shortage,
            total_shortage_quantity=total_shortage,
            unfulfilled_production_demand=total_shortage,
            estimated_downtime_days=round(downtime_days, 4),
            financial_exposure=round(financial_exposure, 2),
            no_shortage_within_horizon=first_shortage is None,
            daily_projection=timeline,
        )

    @staticmethod
    def _shipment_receipts(shipments: list[Shipment]) -> list[Receipt]:
        receipts = []
        for shipment in shipments:
            remaining = max(0, shipment.shipped_quantity - shipment.received_quantity)
            if remaining and shipment.shipment_status not in {"CANCELLED", "LOST", "QUALITY_HOLD"}:
                receipts.append(Receipt(
                    receipt_id=shipment.shipment_id,
                    arrival_date=shipment.revised_eta,
                    quantity=remaining,
                    source="shipment",
                ))
        return receipts

    @staticmethod
    def _allocation_receipts(allocations: list[SupplierAllocation]) -> list[Receipt]:
        return [Receipt(
            receipt_id=f"strategy:{allocation.supplier_id}:{index}",
            arrival_date=allocation.expected_arrival_date,
            quantity=allocation.quantity,
            source="strategy_allocation",
        ) for index, allocation in enumerate(allocations)]

