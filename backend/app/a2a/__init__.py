"""A2A protocol bridge between the ADK orchestrator and CrewAI service."""

from .client import SupplierResearchA2AClient
from .server import build_a2a_app

__all__ = ["SupplierResearchA2AClient", "build_a2a_app"]
