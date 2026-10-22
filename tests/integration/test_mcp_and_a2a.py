from __future__ import annotations

import asyncio

import httpx

from app.a2a.client import SupplierResearchA2AClient
from app.a2a.contracts import SupplierResearchA2ARequest
from app.a2a.server import build_a2a_app
from app.crews.supplier_research import ResearchedSupplier, SupplierResearchResult
from app.mcp import build_mcp_toolset


class FakeCrewAdapter:
    def run(
        self, *, component_id: str, requested_quantity: int, minimum_quality: float
    ) -> SupplierResearchResult:
        return SupplierResearchResult(
            component_id=component_id,
            requested_quantity=requested_quantity,
            candidates=[
                ResearchedSupplier(
                    supplier_id="SUP-B",
                    component_id=component_id,
                    unit_price=112.0,
                    lead_time_days=5,
                    available_capacity=600,
                    quality_score=max(minimum_quality, 92.0),
                    reliability_score=94.0,
                    status="ACTIVE",
                    eligible=True,
                    feasible_quantity=min(requested_quantity, 600),
                    source_record_id="SUP-B",
                )
            ],
            review_notes=["Validated by fake CrewAI adapter for protocol test."],
        )


def test_adk_discovers_four_tools_from_real_mcp_server() -> None:
    async def inspect_tools() -> set[str]:
        toolset = build_mcp_toolset(
            [
                "lookup_supplier",
                "lookup_supplier_orders",
                "lookup_order_shipments",
                "calculate_delay_days",
            ]
        )
        try:
            return {tool.name for tool in await toolset.get_tools()}
        finally:
            await toolset.close()

    names = asyncio.run(inspect_tools())
    assert names == {
        "lookup_supplier",
        "lookup_supplier_orders",
        "lookup_order_shipments",
        "calculate_delay_days",
    }


def test_adk_client_and_crewai_adapter_exchange_a2a_message() -> None:
    async def invoke():
        app = build_a2a_app(FakeCrewAdapter(), base_url="http://test")
        client = SupplierResearchA2AClient(
            "http://test",
            transport=httpx.ASGITransport(app=app),
        )
        return await client.research(
            SupplierResearchA2ARequest(
                component_id="MOTOR-X7",
                requested_quantity=500,
                minimum_quality=80,
            )
        )

    response = asyncio.run(invoke())
    assert response.protocol == "A2A"
    assert response.sender_framework == "CrewAI"
    assert response.receiver_framework == "Google ADK"
    assert response.result.candidates[0].supplier_id == "SUP-B"
