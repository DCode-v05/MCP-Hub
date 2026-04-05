"""GitHub MCP client for executing tool calls."""

import json
import os
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class GitHubMCPClient:
    """Client for interacting with GitHub MCP server."""

    def __init__(self, token: str = None) -> None:
        """Initialize the GitHub MCP client."""
        self.token = token or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "").strip()
        if not self.token:
            raise RuntimeError("GITHUB_PERSONAL_ACCESS_TOKEN is missing")
        self._tools_cache = None

    async def list_tools_async(self):
        """Return list of available GitHub MCP tools with full schemas."""
        if self._tools_cache is not None:
            return self._tools_cache

        # Fetch tools from the actual GitHub MCP server
        self._tools_cache = await self._fetch_tools_async()
        return self._tools_cache
    
    async def _fetch_tools_async(self):
        """Fetch tool definitions from GitHub MCP server."""
        env = os.environ.copy()
        env["GITHUB_TOKEN"] = self.token

        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env=env,
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_response = await session.list_tools()
                    return tools_response.tools
        except Exception as exc:
            print(f"Warning: Failed to fetch GitHub tools: {exc}")
            # Return empty list if fetch fails
            return []

    async def call_tool_async(self, tool: str, arguments: dict[str, Any]) -> str:
        """Call a GitHub MCP tool asynchronously and return the result as a formatted string."""
        env = os.environ.copy()
        env["GITHUB_TOKEN"] = self.token

        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env=env,
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool, arguments=arguments)
                    return self._format_tool_result(result)
        except RuntimeError as exc:
            message = str(exc)
            if "401" in message or "Bad credentials" in message or "Unauthorized" in message or "GITHUB_TOKEN" in message:
                raise RuntimeError(
                    "GitHub auth failed. Ensure GITHUB_PERSONAL_ACCESS_TOKEN is a valid PAT (ghp_...)."
                ) from exc
            raise RuntimeError(f"GitHub MCP error: {message}") from exc
        except Exception as exc:
            raise RuntimeError(f"MCP tool call failed for {tool}: {exc}") from exc

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
        return self._try_pretty_json(joined)

    def _try_pretty_json(self, text: str) -> str:
        """Attempt to pretty-print JSON, fallback to raw text."""
        try:
            obj = json.loads(text)
            return json.dumps(obj, indent=2)
        except Exception:
            return text
