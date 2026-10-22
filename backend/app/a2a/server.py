from __future__ import annotations

import asyncio

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

from app.a2a.contracts import (
    SupplierResearchA2ARequest,
    SupplierResearchA2AResponse,
)
from app.config import get_settings
from app.crews import SupplierResearchCrewAdapter


class CrewAISupplierAgentExecutor(AgentExecutor):
    """Serve the CrewAI supplier crew through the standard A2A protocol."""

    def __init__(self, adapter: SupplierResearchCrewAdapter | None = None) -> None:
        self._adapter = adapter or SupplierResearchCrewAdapter(
            get_settings().gemini_model
        )

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        request = SupplierResearchA2ARequest.model_validate_json(
            context.get_user_input()
        )
        result = await asyncio.to_thread(
            self._adapter.run,
            component_id=request.component_id,
            requested_quantity=request.requested_quantity,
            minimum_quality=request.minimum_quality,
        )
        response = SupplierResearchA2AResponse(result=result)
        await event_queue.enqueue_event(
            new_agent_text_message(
                response.model_dump_json(),
                context_id=context.context_id,
                task_id=context.task_id,
            )
        )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        await event_queue.enqueue_event(
            new_agent_text_message(
                '{"protocol":"A2A","status":"CANCELED"}',
                context_id=context.context_id,
                task_id=context.task_id,
            )
        )


def agent_card(base_url: str) -> AgentCard:
    normalized = base_url.rstrip("/")
    return AgentCard(
        name="Bottleneck CrewAI Supplier Research Agent",
        description=(
            "A CrewAI researcher/analyst/reviewer team that returns validated "
            "supplier candidates to a Google ADK orchestrator."
        ),
        url=f"{normalized}/",
        version="1.0.0",
        protocolVersion="0.3.0",
        preferredTransport="JSONRPC",
        capabilities=AgentCapabilities(
            streaming=False,
            pushNotifications=False,
            stateTransitionHistory=False,
        ),
        defaultInputModes=["application/json", "text/plain"],
        defaultOutputModes=["application/json", "text/plain"],
        skills=[
            AgentSkill(
                id="supplier-research",
                name="Alternative supplier research",
                description=(
                    "Retrieve, compare, and review authorized supplier records."
                ),
                tags=["supply-chain", "CrewAI", "structured-output"],
                examples=[
                    '{"component_id":"MOTOR-X7","requested_quantity":500,"minimum_quality":80}'
                ],
            )
        ],
    )


def build_a2a_app(
    adapter: SupplierResearchCrewAdapter | None = None,
    *,
    base_url: str | None = None,
):
    resolved_url = base_url or get_settings().a2a_supplier_url
    handler = DefaultRequestHandler(
        agent_executor=CrewAISupplierAgentExecutor(adapter),
        task_store=InMemoryTaskStore(),
    )
    return A2AStarletteApplication(
        agent_card=agent_card(resolved_url),
        http_handler=handler,
    ).build()


app = build_a2a_app()
