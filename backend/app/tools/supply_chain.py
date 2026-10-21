from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.tables import (
    DemandRecordRow,
    InventoryRow,
    ProductionRequirementRow,
    PurchaseOrderRow,
    ShipmentRow,
    SupplierRow,
)
from app.models.domain import (
    DemandRecord,
    InventoryRecord,
    ProductionRequirement,
    PurchaseOrder,
    Shipment,
    Supplier,
)


class EntityNotFoundError(LookupError):
    pass


class SupplyChainTools:
    """Validated, read-only deterministic access to authorized source records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_supplier(self, supplier_id: str) -> Supplier:
        row = self.session.get(SupplierRow, self._require_id(supplier_id, "supplier_id"))
        if row is None:
            raise EntityNotFoundError(f"supplier not found: {supplier_id}")
        return Supplier.model_validate(row, from_attributes=True)

    def get_component_suppliers(self, component_id: str, *, active_only: bool = True) -> list[Supplier]:
        statement = select(SupplierRow).where(SupplierRow.component_id == self._require_id(component_id, "component_id"))
        if active_only:
            statement = statement.where(SupplierRow.status == "ACTIVE")
        return [Supplier.model_validate(row, from_attributes=True) for row in self.session.scalars(statement)]

    def get_supplier_orders(self, supplier_id: str) -> list[PurchaseOrder]:
        self.get_supplier(supplier_id)
        statement = select(PurchaseOrderRow).where(PurchaseOrderRow.supplier_id == supplier_id)
        return [PurchaseOrder.model_validate(row, from_attributes=True) for row in self.session.scalars(statement)]

    def get_shipments(self, order_id: str) -> list[Shipment]:
        if self.session.get(PurchaseOrderRow, self._require_id(order_id, "order_id")) is None:
            raise EntityNotFoundError(f"order not found: {order_id}")
        statement = select(ShipmentRow).where(ShipmentRow.order_id == order_id)
        return [Shipment.model_validate(row, from_attributes=True) for row in self.session.scalars(statement)]

    def get_inventory(self, component_id: str) -> list[InventoryRecord]:
        statement = select(InventoryRow).where(InventoryRow.component_id == self._require_id(component_id, "component_id"))
        records = [InventoryRecord.model_validate(row, from_attributes=True) for row in self.session.scalars(statement)]
        if not records:
            raise EntityNotFoundError(f"inventory not found for component: {component_id}")
        return records

    def get_demand(self, component_id: str, start: date, end: date) -> list[DemandRecord]:
        if end < start:
            raise ValueError("end date cannot be before start date")
        statement = (
            select(DemandRecordRow)
            .where(DemandRecordRow.component_id == self._require_id(component_id, "component_id"))
            .where(DemandRecordRow.date.between(start, end))
            .order_by(DemandRecordRow.date)
        )
        return [DemandRecord.model_validate(row, from_attributes=True) for row in self.session.scalars(statement)]

    def get_production_requirements(self, component_id: str) -> list[ProductionRequirement]:
        statement = select(ProductionRequirementRow).where(
            ProductionRequirementRow.component_id == self._require_id(component_id, "component_id")
        )
        return [ProductionRequirement.model_validate(row, from_attributes=True) for row in self.session.scalars(statement)]

    @staticmethod
    def calculate_delay_days(shipment: Shipment) -> int:
        return max(0, (shipment.revised_eta - shipment.original_eta).days)

    @staticmethod
    def _require_id(value: str, field: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(f"{field} cannot be empty")
        if len(value) > 128:
            raise ValueError(f"{field} is too long")
        return value

