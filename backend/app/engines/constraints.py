from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.models.domain import (
    ConstraintResult,
    ConstraintViolation,
    RecoveryStrategy,
    Supplier,
    ValidationStatus,
)


@dataclass(frozen=True)
class ConstraintContext:
    component_id: str
    required_quantity: int
    suppliers: dict[str, Supplier]
    minimum_quality: float
    maximum_additional_budget: float
    planning_end_date: date | None = None


class ConstraintValidationEngine:
    def validate(self, strategy: RecoveryStrategy, context: ConstraintContext) -> ConstraintResult:
        violations: list[ConstraintViolation] = []
        total_allocated = sum(allocation.quantity for allocation in strategy.supplier_allocations)
        if total_allocated != context.required_quantity:
            violations.append(self._violation("allocation_consistency", context.required_quantity, total_allocated, strategy.strategy_id, "Allocation quantities must exactly cover the required quantity."))
        if strategy.estimated_additional_cost > context.maximum_additional_budget:
            violations.append(self._violation("budget_limit", context.maximum_additional_budget, strategy.estimated_additional_cost, strategy.strategy_id, "Modeled additional procurement cost exceeds the approved budget."))

        allocated_by_supplier: dict[str, int] = {}
        for allocation in strategy.supplier_allocations:
            allocated_by_supplier[allocation.supplier_id] = allocated_by_supplier.get(allocation.supplier_id, 0) + allocation.quantity
        for supplier_id, quantity in allocated_by_supplier.items():
            supplier = context.suppliers.get(supplier_id)
            if supplier is None:
                violations.append(self._violation("supplier_exists", "authorized supplier", supplier_id, supplier_id, "Allocation references an unknown supplier."))
                continue
            if supplier.status != "ACTIVE":
                violations.append(self._violation("supplier_active", "ACTIVE", supplier.status, supplier_id, "Supplier is not active."))
            if supplier.component_id != context.component_id:
                violations.append(self._violation("component_compatibility", context.component_id, supplier.component_id, supplier_id, "Supplier is not qualified for the incident component."))
            if quantity > supplier.available_capacity:
                violations.append(self._violation("supplier_capacity", supplier.available_capacity, quantity, supplier_id, "Combined allocation exceeds supplier capacity for the stated period."))
            if supplier.quality_score < context.minimum_quality:
                violations.append(self._violation("minimum_quality", context.minimum_quality, supplier.quality_score, supplier_id, "Supplier quality score is below the required threshold."))
            if allocation.expedite and not supplier.expedite_supported:
                violations.append(self._violation("expedite_supported", True, False, supplier_id, "Expedite was proposed without an explicit supplier capability."))
            if context.planning_end_date and allocation.expected_arrival_date > context.planning_end_date:
                violations.append(self._violation("delivery_feasibility", f"on or before {context.planning_end_date}", allocation.expected_arrival_date, supplier_id, "Expected arrival falls outside the common planning horizon."))
        return ConstraintResult(
            strategy_id=strategy.strategy_id,
            status=ValidationStatus.FAIL if violations else ValidationStatus.PASS,
            constraint_violations=violations,
            validation_details={"required_quantity": context.required_quantity, "allocated_quantity": total_allocated},
        )

    @staticmethod
    def _violation(name: str, expected: object, actual: object, entity: str, explanation: str) -> ConstraintViolation:
        return ConstraintViolation(constraint_name=name, expected_value=expected, actual_value=actual, affected_entity=entity, explanation=explanation)
