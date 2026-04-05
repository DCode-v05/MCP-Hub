"""Figma MCP client — uses direct stdio transport with clean environment."""

import json
import os
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class FigmaMCPClient:
    """Client for interacting with the Figma MCP server (figma-developer-mcp)."""

    def __init__(self, token: str) -> None:
        if not token:
            raise RuntimeError("Figma OAuth token is missing")
        self.token = token
        self._tools_cache = None

    def _build_env(self) -> dict[str, str]:
        """Build a clean environment for the Figma subprocess.

        Excludes PORT so figma-developer-mcp runs in stdio mode
        instead of starting an HTTP server.
        """
        env = {k: v for k, v in os.environ.items() if k.upper() != "PORT"}
        env["FIGMA_OAUTH_TOKEN"] = self.token
        return env

    def _server_params(self) -> StdioServerParameters:
        """Build StdioServerParameters.

        The MCP SDK merges server.env ON TOP of get_default_environment()
        (which includes os.environ).  Setting NODE_ENV=cli tells
        figma-developer-mcp to use stdio transport instead of HTTP.
        Setting PORT to empty string ensures no port conflict even if
        the tool falls back to HTTP mode.
        """
        return StdioServerParameters(
            command="npx",
            args=["-y", "figma-developer-mcp", "--stdio", "--env", "/dev/null"],
            env={
                "FIGMA_OAUTH_TOKEN": self.token,
                "NODE_ENV": "cli",     # forces stdio mode in figma-developer-mcp
                "PORT": "",            # safety: override PORT=8000 from dotenv
            },
        )

    async def list_tools_async(self):
        """Return list of available Figma MCP tools."""
        if self._tools_cache is not None:
            return self._tools_cache
        self._tools_cache = await self._fetch_tools()
        return self._tools_cache

    async def _fetch_tools(self):
        """Fetch tool definitions from the Figma MCP server."""
        server_params = self._server_params()
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_response = await session.list_tools()
                    return tools_response.tools
        except Exception as exc:
            print(f"[Figma] Failed to fetch tools: {exc}")
            return []

    async def call_tool_async(self, tool: str, arguments: dict[str, Any]) -> Any:
        """Call a Figma MCP tool and return the result."""
        server_params = self._server_params()
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool, arguments=arguments)
                    return self._format_tool_result(result)
        except Exception as exc:
            raise RuntimeError(f"Figma MCP tool call failed for {tool}: {exc}") from exc

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
