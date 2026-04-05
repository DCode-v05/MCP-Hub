"""HubSpot MCP client for executing tool calls."""

import json
import os
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class HubSpotMCPClient:
    """Client for interacting with HubSpot MCP server."""

    def __init__(self, token: str) -> None:
        """Initialize the HubSpot MCP client."""
        if not token:
            raise RuntimeError("HubSpot OAuth token is missing")
        self.token = token
        self._tools_cache = None

    def _server_params(self) -> StdioServerParameters:
        package = os.getenv("HUBSPOT_MCP_PACKAGE", "@hubspot/mcp-server")
        env = os.environ.copy()
        env["PRIVATE_APP_ACCESS_TOKEN"] = self.token
        return StdioServerParameters(
            command="npx",
            args=["-y", package],
            env=env,
        )

    async def list_tools_async(self):
        """Return list of available HubSpot MCP tools with full schemas."""
        if self._tools_cache is not None:
            return self._tools_cache

        self._tools_cache = await self._fetch_tools_async()
        return self._tools_cache

    async def _fetch_tools_async(self):
        """Fetch tool definitions from HubSpot MCP server."""
        server_params = self._server_params()
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_response = await session.list_tools()
                    return tools_response.tools
        except Exception as exc:
            print(f"[HubSpot] Failed to fetch tools: {exc}")
            return []

    async def call_tool_async(self, tool: str, arguments: dict[str, Any]) -> str:
        """Call a HubSpot MCP tool asynchronously and return formatted result."""
        server_params = self._server_params()
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool, arguments=arguments)
                    return self._format_tool_result(result)
        except Exception as exc:
            raise RuntimeError(f"HubSpot MCP tool call failed for {tool}: {exc}") from exc

    def _format_tool_result(self, result: Any) -> str:
        """Format the MCP tool result into a readable string."""
        structured = getattr(result, "structuredContent", None)
        if structured:
            try:
                return json.dumps(structured, indent=2)
            except Exception:
                return str(structured)

        content = getattr(result, "content", None) or []
        parts: list[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
            else:
                parts.append(str(block))

        if not parts:
            return "{}"
        joined = "\n".join(parts)
        try:
            obj = json.loads(joined)
            return json.dumps(obj, indent=2)
        except Exception:
            return joined
