from __future__ import annotations

import os
import sys
from collections.abc import Sequence

from google.adk.dependencies._mcp import StdioServerParameters
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams

from app.config.settings import PROJECT_ROOT


def build_mcp_toolset(tool_names: Sequence[str]) -> McpToolset:
    """Create an ADK MCP client for the trusted local read-only tool server."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "backend")
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", "app.mcp.server"],
                cwd=PROJECT_ROOT,
                env=environment,
            ),
            timeout=15.0,
        ),
        tool_filter=list(tool_names),
        tool_list_cache_ttl_seconds=60.0,
    )
