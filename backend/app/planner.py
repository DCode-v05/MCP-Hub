"""Planner — analyzes user intent and generates multi-server execution plans."""

import json
from typing import Any, List, Dict, Optional

from openai import OpenAI

from app.config import settings
from app import mcp_manager


# ── OpenAI client (lazy) ────────────────────────────────────────────────────
_openai_client: OpenAI | None = None


def _get_openai():
    global _openai_client
    if _openai_client is None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in .env")
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


async def get_available_servers_and_tools() -> Dict[str, List[Dict[str, str]]]:
    """Get all connected servers and their available tools."""
    result = {}

    for server_id in mcp_manager.SERVER_REGISTRY:
        if mcp_manager.is_connected(server_id):
            try:
                tools = await mcp_manager.list_tools(server_id)
                tool_list = []
                for tool in tools:
                    name = tool.name if hasattr(tool, "name") else tool.get("name", "")
                    desc = tool.description if hasattr(tool, "description") else tool.get("description", "")
                    tool_list.append({"name": name, "description": desc or f"MCP tool: {name}"})
                if tool_list:
                    result[server_id] = tool_list
            except Exception:
                pass

    return result


def _build_planner_prompt(servers_and_tools: Dict[str, List[Dict[str, str]]]) -> str:
    """Build the system prompt for the planner."""

    # Build server descriptions
    server_descriptions = []
    for server_id, tools in servers_and_tools.items():
        meta = mcp_manager.SERVER_REGISTRY.get(server_id, {})
        desc = meta.get("description", "")
        tool_names = [t["name"] for t in tools]
        server_descriptions.append(
            f"- **{server_id}** ({meta.get('name', server_id)}): {desc}\n"
            f"  Available tools: {', '.join(tool_names)}"
        )

    prompt = f"""You are an AI task planner for a unified MCP platform that can execute tools on multiple servers simultaneously.

Your job is to analyze a user's request and create an execution plan that determines which servers and tools are needed.

## Connected Servers and Available Tools:

{chr(10).join(server_descriptions) if server_descriptions else "No servers are currently connected."}

## Your Task:

1. Analyze the user's request
2. Identify which servers are needed to fulfill it
3. Determine which specific tools should be called on each server
4. Create a JSON execution plan with the following structure:

{{
  "steps": [
    {{
      "server": "<server_id>",
      "tool": "<tool_name>",
      "arguments": {{"<param1>": "<value1>", "<param2>": "<value2>"}}
    }},
    ...
  ]
}}

## Important Rules:

- Only use servers that are in the "Connected Servers" list above
- Only use tools that are actually available for each server
- Arrange steps in logical order (dependencies first)
- Extract arguments from the user's request
- Return ONLY the JSON structure, no other text
- If no valid plan can be created, return: {{"steps": []}}

User request: """

    return prompt


async def plan_execution(message: str) -> Dict[str, Any]:
    """
    Analyze user message and create an execution plan.

    Returns:
        {{
          "steps": [
            {{"server": "...", "tool": "...", "arguments": {{...}}}},
            ...
          ],
          "error": None  # or error message if planning failed
        }}
    """

    try:
        # Get available servers and tools
        servers_and_tools = await get_available_servers_and_tools()

        if not servers_and_tools:
            return {
                "steps": [],
                "error": "No servers are currently connected. Please connect at least one server first.",
            }

        # Build planner prompt
        base_prompt = _build_planner_prompt(servers_and_tools)
        system_prompt = base_prompt

        # Call OpenAI
        client = _get_openai()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            temperature=0.5,  # Lower temperature for more deterministic planning
        )

        response_text = response.choices[0].message.content or ""

        # Parse JSON from response
        # Try to extract JSON if it's wrapped in markdown code blocks
        if "```json" in response_text:
            json_part = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_part = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_part = response_text.strip()

        plan = json.loads(json_part)

        # Validate plan structure
        if not isinstance(plan, dict) or "steps" not in plan:
            return {"steps": [], "error": "Invalid plan structure returned by planner"}

        if not isinstance(plan["steps"], list):
            return {"steps": [], "error": "Plan steps must be a list"}

        # Validate each step
        for step in plan["steps"]:
            if not isinstance(step, dict):
                return {"steps": [], "error": "Each step must be a dictionary"}
            if "server" not in step or "tool" not in step:
                return {"steps": [], "error": "Each step must have 'server' and 'tool' keys"}

            # Verify server exists and is connected
            if step["server"] not in servers_and_tools:
                return {
                    "steps": [],
                    "error": f"Server '{step['server']}' is not connected or has no tools",
                }

            # Verify tool exists on server
            available_tools = {t["name"] for t in servers_and_tools[step["server"]]}
            if step["tool"] not in available_tools:
                return {
                    "steps": [],
                    "error": f"Tool '{step['tool']}' not available on server '{step['server']}'",
                }

        return {"steps": plan["steps"], "error": None}

    except json.JSONDecodeError as e:
        return {
            "steps": [],
            "error": f"Failed to parse planner response as JSON: {str(e)}",
        }
    except Exception as e:
        return {
            "steps": [],
            "error": f"Planner error: {str(e)}",
        }
