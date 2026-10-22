from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable

from app.config import get_settings
from app.database import build_engine, session_factory
from app.simulation import SupplySimulator
from app.tools.supply_chain import SupplyChainTools


def _with_tools(operation: Callable[[SupplyChainTools], Any]) -> Any:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    Session = session_factory(engine)
    try:
        with Session() as session:
            return operation(SupplyChainTools(session))
    finally:
        engine.dispose()


def get_supplier_record(supplier_id: str) -> dict[str, Any]:
    """Return one authorized supplier record by its exact supplier ID."""
    return _with_tools(lambda tools: tools.get_supplier(supplier_id).model_dump(mode="json"))


def get_supplier_orders(supplier_id: str) -> list[dict[str, Any]]:
    """Return purchase orders committed to an authorized supplier."""
    return _with_tools(lambda tools: [row.model_dump(mode="json") for row in tools.get_supplier_orders(supplier_id)])


def get_component_suppliers(component_id: str) -> list[dict[str, Any]]:
    """Return active, component-qualified suppliers from the synthetic supplier database."""
    return _with_tools(lambda tools: [row.model_dump(mode="json") for row in tools.get_component_suppliers(component_id)])


def get_order_shipments(order_id: str) -> list[dict[str, Any]]:
    """Return shipments and deterministic delay days for an exact purchase-order ID."""
    def operation(tools: SupplyChainTools) -> list[dict[str, Any]]:
        results = []
        for shipment in tools.get_shipments(order_id):
            record = shipment.model_dump(mode="json")
            record["delay_days"] = tools.calculate_delay_days(shipment)
            record["remaining_quantity"] = max(0, shipment.shipped_quantity - shipment.received_quantity)
            results.append(record)
        return results
    return _with_tools(operation)


def get_component_inventory(component_id: str) -> list[dict[str, Any]]:
    """Return warehouse inventory including deterministically calculated available quantity."""
    def operation(tools: SupplyChainTools) -> list[dict[str, Any]]:
        results = []
        for inventory in tools.get_inventory(component_id):
            record = inventory.model_dump(mode="json")
            record["available_quantity"] = inventory.available_quantity
            results.append(record)
        return results
    return _with_tools(operation)


def project_component_supply(component_id: str, order_id: str, horizon_days: int = 30) -> dict[str, Any]:
    """Run the deterministic daily supply simulation; never estimate quantities in the model."""
    settings = get_settings()

    def operation(tools: SupplyChainTools) -> dict[str, Any]:
        start = settings.simulation_date
        end = start + timedelta(days=horizon_days - 1)
        result = SupplySimulator().simulate(
            start_date=start,
            horizon_days=horizon_days,
            inventory=tools.get_inventory(component_id),
            demand=tools.get_demand(component_id, start, end),
            shipments=tools.get_shipments(order_id),
            production_requirements=tools.get_production_requirements(component_id),
        )
        return result.model_dump(mode="json")
    return _with_tools(operation)


def get_production_requirements(component_id: str) -> list[dict[str, Any]]:
    """Return production-line requirements linked to an exact component ID."""
    return _with_tools(lambda tools: [row.model_dump(mode="json") for row in tools.get_production_requirements(component_id)])


async def run_supplier_research(
    component_id: str,
    requested_quantity: int,
    minimum_quality: float = 80.0,
) -> dict[str, Any]:
    """Call the remote CrewAI research agent through A2A JSON-RPC."""
    from app.a2a import SupplierResearchA2AClient
    from app.a2a.contracts import SupplierResearchA2ARequest

    response = await SupplierResearchA2AClient().research(
        SupplierResearchA2ARequest(
            component_id=component_id,
            requested_quantity=requested_quantity,
            minimum_quality=minimum_quality,
        )
    )
    return {
        **response.result.model_dump(mode="json"),
        "interoperability": {
            "protocol": response.protocol,
            "protocol_version": response.protocol_version,
            "sender_framework": response.sender_framework,
            "receiver_framework": response.receiver_framework,
            "agent_name": response.agent_name,
            "status": response.status,
        },
    }


SUPPLIER_TOOLS = [get_supplier_record, get_supplier_orders]
LOGISTICS_TOOLS = [get_order_shipments]
INVENTORY_TOOLS = [get_component_inventory, project_component_supply]
PRODUCTION_TOOLS = [get_production_requirements, project_component_supply]
ALTERNATIVE_SUPPLIER_TOOLS = [run_supplier_research]
