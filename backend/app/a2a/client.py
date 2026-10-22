from __future__ import annotations

from uuid import uuid4

import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart
from a2a.utils import get_message_text

from app.a2a.contracts import (
    SupplierResearchA2ARequest,
    SupplierResearchA2AResponse,
)
from app.config import get_settings


class SupplierResearchA2AClient:
    """Typed A2A client used by the Google ADK alternative-supplier agent."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout_seconds: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.a2a_supplier_url).rstrip("/")
        self.timeout_seconds = (
            timeout_seconds or settings.a2a_request_timeout_seconds
        )
        self.transport = transport

    async def research(
        self, request: SupplierResearchA2ARequest
    ) -> SupplierResearchA2AResponse:
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as http_client:
            client = await ClientFactory.connect(
                self.base_url,
                client_config=ClientConfig(
                    streaming=False,
                    polling=False,
                    httpx_client=http_client,
                ),
            )
            message = Message(
                role=Role.user,
                parts=[
                    Part(
                        root=TextPart(text=request.model_dump_json())
                    )
                ],
                messageId=str(uuid4()),
            )
            async for event in client.send_message(message):
                if isinstance(event, Message):
                    return SupplierResearchA2AResponse.model_validate_json(
                        get_message_text(event)
                    )
        raise RuntimeError("A2A supplier agent returned no final message")
