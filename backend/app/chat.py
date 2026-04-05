"""Unified Chat endpoint — OpenAI + MCP tool-calling loop for any server."""

import json
from typing import Any, List, Dict, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI

from app.config import settings
from app import mcp_manager, storage, planner

router = APIRouter()


# ── Request / Response models ────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    server: Optional[str] = None  # "github" | "zomato" | "notion" | "figma" (now optional for multi-server)
    chatId: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None


# ── OpenAI client (lazy) ────────────────────────────────────────────────────
_openai_client: OpenAI | None = None


def _get_openai():
    global _openai_client
    if _openai_client is None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in .env")
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


# ── Tool-name mapping (OpenAI tool name → server + actual MCP tool name) ─────
TOOL_NAME_MAP: dict[str, dict[str, str]] = {}


def _clean_schema(schema: Any) -> Any:
    """Recursively clean JSON schema to conform to OpenAI requirements."""
    if not schema or not isinstance(schema, dict):
        return schema

    if "anyOf" in schema:
        return _clean_schema(schema["anyOf"][0])
    if "oneOf" in schema:
        return _clean_schema(schema["oneOf"][0])

    clean: dict[str, Any] = {}

    if "type" in schema:
        val = schema["type"]
        if isinstance(val, list):
            types = [t for t in val if t != "null"]
            clean["type"] = types[0].lower() if types else "string"
        else:
            clean["type"] = val.lower() if isinstance(val, str) else "object"

    # Array items
    schema_type = schema.get("type")
    is_array = schema_type == "array" or (isinstance(schema_type, list) and "array" in schema_type)
    if is_array and "items" in schema:
        clean["items"] = _clean_schema(schema["items"])

    if "description" in schema:
        clean["description"] = schema["description"] or "No description."

    if "properties" in schema:
        clean["properties"] = {k: _clean_schema(v) for k, v in schema["properties"].items()}

    if "required" in schema:
        clean["required"] = schema["required"]

    return clean


def _schema_has_invalid_array(schema: Any) -> bool:
    """Detect arrays without 'items' which OpenAI rejects."""
    if isinstance(schema, dict):
        if schema.get("type") == "array" and "items" not in schema:
            return True
        for v in schema.values():
            if _schema_has_invalid_array(v):
                return True
    elif isinstance(schema, list):
        for item in schema:
            if _schema_has_invalid_array(item):
                return True
    return False


def _convert_mcp_tools_for_server(server_id: str, mcp_tools: list) -> list[dict]:
    """
    Convert MCP tools for a single server into OpenAI function-calling format.

    Tool names are *namespaced* by server so the model can call tools from
    different servers in a single turn, e.g.:
      github_list_repos, notion_search_pages, figma_get_file, ...
    """
    tools: list[dict] = []

    for tool in mcp_tools:
        raw_schema = tool.inputSchema if hasattr(tool, "inputSchema") else (
            tool.get("inputSchema") if isinstance(tool, dict) else {"type": "object", "properties": {}}
        )
        schema = raw_schema or {"type": "object", "properties": {}}

        # Remove problematic Notion properties
        if server_id == "notion" and "properties" in schema:
            schema["properties"].pop("icon", None)
            schema["properties"].pop("cover", None)
            if "required" in schema:
                schema["required"] = [r for r in schema["required"] if r in schema["properties"]]

        params = _clean_schema(schema)
        if _schema_has_invalid_array(params):
            continue

        name = tool.name if hasattr(tool, "name") else tool.get("name", "unknown")
        desc = tool.description if hasattr(tool, "description") else tool.get("description", "")

        base_safe_name = name.replace("-", "_").replace(".", "_")
        # Namespaced tool name ensures uniqueness across servers
        safe_name = f"{server_id}_{base_safe_name}"

        TOOL_NAME_MAP[safe_name] = {
            "server": server_id,
            "name": name,
        }

        tools.append({
            "type": "function",
            "function": {
                "name": safe_name,
                "description": desc or f"{server_id} MCP tool: {name}",
                "parameters": params,
            },
        })

    return tools


async def _build_unified_tools() -> Tuple[list[dict], list[str]]:
    """
    Build OpenAI tools for *all connected* MCP servers.

    Returns a tuple of:
    - tools: list of OpenAI tool definitions
    - servers: list of server_ids that contributed tools
    """
    global TOOL_NAME_MAP
    TOOL_NAME_MAP = {}

    unified_tools: list[dict] = []
    contributing_servers: list[str] = []

    all_tools = await mcp_manager.get_all_connected_tools()
    tools_by_server: dict[str, list] = {}

    for entry in all_tools:
        sid = entry.get("server")
        tool = entry.get("tool")
        if not sid or tool is None:
            continue
        tools_by_server.setdefault(sid, []).append(tool)

    for server_id, mcp_tools in tools_by_server.items():
        server_tools = _convert_mcp_tools_for_server(server_id, mcp_tools)
        if server_tools:
            unified_tools.extend(server_tools)
            contributing_servers.append(server_id)

    return unified_tools, contributing_servers


# ── System prompts per server / unified assistant ────────────────────────────
SYSTEM_PROMPTS = {
    "github": (
        "You are a GitHub assistant integrated via MCP. "
        "You can manage repositories, issues, pull requests, branches, code search, and more. "
        "Use the available tools to fulfil the user's GitHub requests. "
        "Always provide clear, structured responses. Use markdown formatting."
    ),
    "zomato": (
        "You are Zomato AI — a smart food ordering assistant. "
        "You can search restaurants, browse menus, manage cart, apply offers, and place orders. "
        "Always show multiple restaurant options when searching. "
        "Show prices with tax breakdown. Proactively check for offers/coupons. "
        "Use markdown formatting for clean presentation."
    ),
    "notion": (
        "You are a Notion assistant integrated via MCP. "
        "You can search pages, read content, manage databases, create pages, and more. "
        "When the user provides a Notion URL, pass it directly to the tools. "
        "If a tool returns a validation error, try using search/fetch tools to resolve IDs. "
        "Always provide clear, helpful responses based on tool results."
    ),
    "figma": (
        "You are a Figma design assistant integrated via MCP. "
        "You can access Figma files, inspect components, extract design tokens, and download images. "
        "Help users understand their designs, extract CSS properties, review components, and more. "
        "Always provide clear, structured responses with relevant design details."
    ),
    "hubspot": (
        "You are a HubSpot CRM assistant integrated via MCP. "
        "You can manage contacts, deals, companies, tickets, and CRM workflows. "
        "Use the available tools to create, update, retrieve and summarize HubSpot data. "
        "Always provide clear, structured responses with actionable business context."
    ),
}

UNIFIED_SYSTEM_PROMPT = (
    "You are a unified assistant connected to multiple MCP servers: GitHub, "
    "Zomato, Notion, Figma, HubSpot and others. You can decide which tools "
    "to use based on the user's request, and you may call tools from multiple "
    "servers in a single conversation turn. Prefer using tools whenever they "
    "will improve accuracy or provide up-to-date data. Always explain briefly "
    "what you did with each service, and respond with clear, well-structured "
    "markdown."
)


def _clean_history(history: list[dict], limit: int = 15) -> list[dict]:
    """Convert frontend chat history to OpenAI message format."""
    messages = []
    trimmed = history[-limit:] if history else []
    for msg in trimmed:
        role = msg.get("role", "")
        content = msg.get("content", "") or msg.get("text", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    return messages


def _extract_text(result: Any) -> str:
    """Extract text content from an MCP tool result."""
    if hasattr(result, "content"):
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts) if parts else str(result)
    return str(result)


# ── Main chat endpoint ──────────────────────────────────────────────────────
@router.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    message = request.message
    history = request.history or []
    chat_id = request.chatId
    server_hint = request.server  # Optional, used only as a soft preference hint

    try:
        # Build unified tool set across all connected servers
        openai_tools, contributing_servers = await _build_unified_tools()

        # Build messages
        system_prompt = UNIFIED_SYSTEM_PROMPT
        messages = [{"role": "system", "content": system_prompt}]

        # If a legacy client passed `server`, treat it as a soft routing hint
        if server_hint:
            hint = (
                f"The user prefers tools from the '{server_hint}' server for this "
                "request when appropriate, but you may still use other servers."
            )
            messages.append({"role": "system", "content": hint})

        messages.extend(_clean_history(history))
        messages.append({"role": "user", "content": message})

        client = _get_openai()
        final_text = None
        last_content = None
        tool_calls_log: list[dict] = []

        # Tool-calling loop (max 5 rounds)
        for _ in range(5):
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                tools=openai_tools if openai_tools else None,
                tool_choice="auto" if openai_tools else None,
                temperature=0.7,
            )

            resp_msg = response.choices[0].message
            messages.append(resp_msg)

            if resp_msg.content:
                last_content = resp_msg.content

            # No tool calls → done
            if not resp_msg.tool_calls:
                final_text = resp_msg.content
                break

            # Execute each tool call
            for tc in resp_msg.tool_calls:
                safe_name = tc.function.name
                mapping = TOOL_NAME_MAP.get(safe_name)
                if not mapping:
                    # Unknown tool mapping — skip but log
                    tool_calls_log.append({
                        "tool": safe_name,
                        "server": None,
                        "args": {},
                        "error": "Unknown tool mapping",
                    })
                    continue

                server_id = mapping["server"]
                actual_name = mapping["name"]
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                tool_calls_log.append({
                    "tool": actual_name,
                    "server": server_id,
                    "args": args,
                })

                try:
                    result = await mcp_manager.call_tool(server_id, actual_name, args)
                    result_text = _extract_text(result)
                except Exception as e:
                    result_text = f"Error executing tool: {str(e)}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": safe_name,
                    "content": result_text,
                })

        # Fallback: if loop ended without a tool-free response
        if final_text is None:
            messages.append({
                "role": "system",
                "content": (
                    "Summarise the tool results above into a clear, final answer "
                    "for the user. Do not call any more tools."
                ),
            })
            fallback = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                tools=None,
                temperature=0.7,
            )
            final_text = (
                fallback.choices[0].message.content
                or last_content
                or "Sorry, I couldn't generate a response."
            )

        # Persist to chat history
        if chat_id:
            storage.add_message(chat_id, "user", message, "multi")
            storage.add_message(chat_id, "assistant", final_text, "multi", tool_calls_log or None)

        return {
            "response": final_text,
            "server": "multi",
            "toolCalls": tool_calls_log,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


# ── Multi-server orchestration ──────────────────────────────────────────────
async def _execute_plan(plan_steps: list[dict]) -> list[dict]:
    """
    Execute a plan by calling MCP tools on the appropriate servers.
    
    Returns a list of execution results:
    [
        {
            "server": "github",
            "tool": "create_repository",
            "arguments": {...},
            "result": "...",
            "error": None
        },
        ...
    ]
    """
    results = []
    
    for step in plan_steps:
        server_id = step.get("server")
        tool_name = step.get("tool")
        arguments = step.get("arguments", {})
        
        try:
            if not mcp_manager.is_connected(server_id):
                result_text = f"Error: Server '{server_id}' is not connected"
                error = result_text
            else:
                result = await mcp_manager.call_tool(server_id, tool_name, arguments)
                result_text = _extract_text(result)
                error = None
        except Exception as e:
            result_text = f"Error executing tool: {str(e)}"
            error = str(e)
        
        results.append({
            "server": server_id,
            "tool": tool_name,
            "arguments": arguments,
            "result": result_text,
            "error": error,
        })
    
    return results


def _format_execution_results(results: list[dict]) -> str:
    """Format execution results for LLM summarization."""
    formatted = []
    for r in results:
        formatted.append(
            f"**{r['server']} → {r['tool']}**\n"
            f"Arguments: {json.dumps(r['arguments'], indent=2)}\n"
            f"Result: {r['result']}"
        )
    return "\n\n".join(formatted)


async def _summarize_results(
    user_message: str,
    execution_results: list[dict],
    history: list[dict]
) -> str:
    """
    Send execution results back to LLM for summarization and final response.
    """
    formatted_results = _format_execution_results(execution_results)
    
    # Build messages
    messages = [{"role": "system", "content": (
        "You are a helpful assistant that summarizes the results of multi-tool executions. "
        "Present the results clearly and concisely to the user, highlighting key information. "
        "Use markdown formatting for readability."
    )}]
    
    # Add chat history
    messages.extend(_clean_history(history))
    
    # Add user message and execution results
    messages.append({
        "role": "user",
        "content": (
            f"User request: {user_message}\n\n"
            f"Execution results from multiple servers:\n\n"
            f"{formatted_results}"
        )
    })
    
    client = _get_openai()
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        temperature=0.7,
    )
    
    return response.choices[0].message.content or "Unable to generate response"


@router.post("/api/chat/multi")
async def chat_multi_endpoint(request: ChatRequest):
    """
    Intent-based multi-server orchestration endpoint.
    
    Takes a user message, detects which servers are needed,
    creates an execution plan, runs tools on multiple servers,
    and summarizes results.
    """
    message = request.message
    history = request.history or []
    chat_id = request.chatId
    
    try:
        # Step 1: Create execution plan
        plan_result = await planner.plan_execution(message)
        
        if plan_result.get("error"):
            raise HTTPException(
                status_code=400,
                detail=f"Planning error: {plan_result['error']}"
            )
        
        plan_steps = plan_result.get("steps", [])
        
        if not plan_steps:
            return {
                "response": (
                    "I couldn't identify any tasks to perform. "
                    "Please ensure you have at least one server connected and describe what you'd like me to do."
                ),
                "plan": {"steps": []},
                "executionResults": [],
                "toolCalls": [],
            }
        
        # Step 2: Execute the plan
        execution_results = await _execute_plan(plan_steps)
        
        # Step 3: Summarize results
        final_response = await _summarize_results(message, execution_results, history)
        
        # Step 4: Persist to chat history
        if chat_id:
            storage.add_message(chat_id, "user", message, "multi", None)
            storage.add_message(
                chat_id,
                "assistant",
                final_response,
                "multi",
                [{"step": s["tool"], "server": s["server"], "args": s["arguments"]} for s in plan_steps]
            )
        
        return {
            "response": final_response,
            "plan": {"steps": plan_steps},
            "executionResults": execution_results,
            "toolCalls": [
                {
                    "server": r["server"],
                    "tool": r["tool"],
                    "args": r["arguments"]
                }
                for r in execution_results
            ],
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multi-server chat error: {str(e)}")

