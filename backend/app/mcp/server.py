from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.database import build_engine, session_factory
from app.tools import SupplyChainTools


mcp = FastMCP(
    "bottleneck-supply-chain",
    instructions=(
        "Read-only access to authorized synthetic supplier and logistics records. "
        "Returned numbers are source data and must not be changed."
    ),
)


def _read(operation):
    settings = get_settings()
    engine = build_engine(settings.database_url)
    Session = session_factory(engine)
    try:
        with Session() as session:
            return operation(SupplyChainTools(session))
    finally:
        engine.dispose()


@mcp.tool()
def lookup_supplier(supplier_id: str) -> dict[str, Any]:
    """Look up one authorized supplier record by exact supplier ID."""
    return _read(
        lambda tools: tools.get_supplier(supplier_id).model_dump(mode="json")
    )


@mcp.tool()
def lookup_supplier_orders(supplier_id: str) -> list[dict[str, Any]]:
    """Look up purchase orders committed to an exact supplier ID."""
    return _read(
        lambda tools: [
            row.model_dump(mode="json")
            for row in tools.get_supplier_orders(supplier_id)
        ]
    )


@mcp.tool()
def lookup_order_shipments(order_id: str) -> list[dict[str, Any]]:
    """Look up shipment records for an exact purchase-order ID."""
    def operation(tools: SupplyChainTools) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for shipment in tools.get_shipments(order_id):
            record = shipment.model_dump(mode="json")
            record["delay_days"] = tools.calculate_delay_days(shipment)
            record["remaining_quantity"] = max(
                0, shipment.shipped_quantity - shipment.received_quantity
            )
            records.append(record)
        return records

    return _read(operation)


@mcp.tool()
def calculate_delay_days(original_eta: str, revised_eta: str) -> dict[str, Any]:
    """Calculate non-negative calendar delay days from ISO dates."""
    original = date.fromisoformat(original_eta)
    revised = date.fromisoformat(revised_eta)
    return {
        "original_eta": original.isoformat(),
        "revised_eta": revised.isoformat(),
        "delay_days": max((revised - original).days, 0),
        "calculation": "max(revised_eta - original_eta, 0)",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
