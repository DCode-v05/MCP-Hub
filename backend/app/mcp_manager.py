"""Unified MCP Server Manager — connects to GitHub, Zomato, Notion, Figma."""

import asyncio
import glob
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any
import tempfile

from fastmcp import Client
from app.config import settings
from app.github_client import GitHubMCPClient
from app.figma_client import FigmaMCPClient
from app.hubspot_client import HubSpotMCPClient

# Background task handle for Zomato connection (so it isn't garbage collected)
_zomato_connect_task: asyncio.Task | None = None


# ── Server metadata ──────────────────────────────────────────────────────────
SERVER_REGISTRY = {
    "github": {
        "name": "GitHub",
        "description": "Repositories, issues, pull requests & code",
        "connect_label": "Sign in",
    },
    "zomato": {
        "name": "Zomato",
        "description": "Restaurants, food ordering & delivery",
        "connect_label": "Sign in",
    },
    "notion": {
        "name": "Notion",
        "description": "Pages, databases & workspace content",
        "connect_label": "Sign in",
    },
    "figma": {
        "name": "Figma",
        "description": "Designs, components & design tokens",
        "connect_label": "Sign in",
    },
    "hubspot": {
        "name": "HubSpot",
        "description": "CRM contacts, deals, companies and marketing",
        "connect_label": "Sign in",
    },
}


# ── Runtime state ────────────────────────────────────────────────────────────
_clients: dict[str, Client] = {}
_tools_cache: dict[str, list] = {}
_connected: dict[str, bool] = {}
_connecting: dict[str, bool] = {}

# GitHub client (uses personal access token)
_github_client: GitHubMCPClient | None = None

# Figma client (uses OAuth token, direct stdio to avoid PORT conflicts)
_figma_client: FigmaMCPClient | None = None

# HubSpot client (uses OAuth token)
_hubspot_client: HubSpotMCPClient | None = None

# OAuth tokens (set after user signs in)
_tokens: dict[str, str | None] = {
    "github": None,
    "notion": None,
    "figma": None,
    "hubspot": None,
}

# Zomato OAuth URL capture (written by zomato_wrapper.py)
_ZOMATO_URL_FILE = "/tmp/_unified_mcp_zomato_auth_url.txt"


def get_zomato_auth_url() -> str | None:
    """Read the Zomato OAuth URL captured by the wrapper, if available."""
    try:
        if os.path.exists(_ZOMATO_URL_FILE):
            return open(_ZOMATO_URL_FILE).read().strip() or None
    except Exception:
        pass
    return None


def _clear_zomato_auth_url():
    """Remove the captured URL file so a fresh URL can be written."""
    try:
        if os.path.exists(_ZOMATO_URL_FILE):
            os.remove(_ZOMATO_URL_FILE)
    except Exception:
        pass


def set_token(provider: str, token: str | None):
    """Store (or clear) an OAuth token for any provider."""
    _tokens[provider] = token


def get_token(provider: str) -> str | None:
    """Get the stored OAuth token for a provider."""
    return _tokens.get(provider)


# Backward-compatible Notion helpers
def set_notion_token(token: str):
    set_token("notion", token)


def get_notion_token() -> str | None:
    return get_token("notion")


# ── Config builders ──────────────────────────────────────────────────────────
def _build_config(server_id: str) -> dict:
    """Build fastmcp Client config for a given server."""
    if server_id == "notion":
        token = _tokens.get("notion") or ""
        return {
            "notion": {
                "command": "npx",
                "args": ["-y", "@notionhq/notion-mcp-server"],
                "env": {"NOTION_TOKEN": token},
            }
        }
    elif server_id == "zomato":
        wrapper_path = str(Path(__file__).parent / "zomato_wrapper.py")
        return {
            "zomato": {
                "command": "python3",
                "args": [
                    wrapper_path, _ZOMATO_URL_FILE,
                    "npx", "-y", "mcp-remote",
                    "https://mcp-server.zomato.com/mcp",
                ],
            }
        }
    raise ValueError(f"Unknown server: {server_id}")


# ── Connection management ────────────────────────────────────────────────────
async def connect_server(server_id: str) -> dict[str, Any]:
    """Connect to an MCP server. Returns status dict."""
    global _github_client, _hubspot_client
    
    if server_id not in SERVER_REGISTRY:
        return {"success": False, "error": f"Unknown server: {server_id}"}

    if _connected.get(server_id):
        tool_count = len(_tools_cache.get(server_id, []))
        return {"success": True, "message": "Already connected", "tools": tool_count}

    if _connecting.get(server_id):
        return {"success": False, "connecting": True, "message": "Connection in progress…"}

    # Pre-flight checks
    if server_id == "github":
        if settings.GITHUB_CLIENT_ID:
            # OAuth mode — require OAuth token
            token = _tokens.get("github")
            if not token:
                return {
                    "success": False,
                    "needs_auth": True,
                    "auth_url": "/auth/github/login",
                }
        else:
            # PAT mode — use personal access token from .env
            token = settings.GITHUB_PERSONAL_ACCESS_TOKEN.strip()
            if not token:
                return {"success": False, "error": "GITHUB_PERSONAL_ACCESS_TOKEN not set in .env"}

        _connecting[server_id] = True
        try:
            _github_client = GitHubMCPClient(token)
            tools = await _github_client.list_tools_async()
            _tools_cache[server_id] = tools
            _connected[server_id] = True
            _connecting[server_id] = False
            print(f"[MCP] Connected to GitHub — {len(tools)} tools available")
            return {
                "success": True,
                "tools": len(tools),
                "message": f"Connected to {SERVER_REGISTRY[server_id]['name']}",
            }
        except Exception as exc:
            _connecting[server_id] = False
            _connected[server_id] = False
            print(f"[MCP] Failed to connect GitHub: {exc}")
            return {"success": False, "error": str(exc)}

    if server_id in ("notion", "figma", "hubspot") and not _tokens.get(server_id):
        return {
            "success": False,
            "needs_auth": True,
            "auth_url": f"/auth/{server_id}/login",
        }

    # Figma: use dedicated client (like GitHub) for full env control
    if server_id == "figma":
        _connecting[server_id] = True
        try:
            _figma_client = FigmaMCPClient(_tokens.get("figma", ""))
            tools = await _figma_client.list_tools_async()
            _tools_cache[server_id] = tools
            _connected[server_id] = True
            _connecting[server_id] = False
            print(f"[MCP] Connected to Figma — {len(tools)} tools available")
            return {
                "success": True,
                "tools": len(tools),
                "message": f"Connected to {SERVER_REGISTRY[server_id]['name']}",
            }
        except Exception as exc:
            _connecting[server_id] = False
            _connected[server_id] = False
            print(f"[MCP] Failed to connect Figma: {exc}")
            return {"success": False, "error": str(exc)}

    if server_id == "hubspot":
        _connecting[server_id] = True
        try:
            _hubspot_client = HubSpotMCPClient(_tokens.get("hubspot", ""))
            tools = await _hubspot_client.list_tools_async()
            if not tools:
                _connecting[server_id] = False
                _connected[server_id] = False
                _hubspot_client = None
                return {
                    "success": False,
                    "error": (
                        "HubSpot MCP server returned no tools. "
                        "Verify HUBSPOT_MCP_PACKAGE and token compatibility."
                    ),
                }
            _tools_cache[server_id] = tools
            _connected[server_id] = True
            _connecting[server_id] = False
            print(f"[MCP] Connected to HubSpot — {len(tools)} tools available")
            return {
                "success": True,
                "tools": len(tools),
                "message": f"Connected to {SERVER_REGISTRY[server_id]['name']}",
            }
        except Exception as exc:
            _connecting[server_id] = False
            _connected[server_id] = False
            print(f"[MCP] Failed to connect HubSpot: {exc}")
            return {"success": False, "error": str(exc)}

    # Zomato uses mcp-remote which does its own browser-based OAuth.
    # This blocks until the user authorises in their browser, so we
    # run it in a background task and return immediately.
    if server_id == "zomato":
        global _zomato_connect_task
        _connecting[server_id] = True
        _clear_zomato_auth_url()
        _zomato_connect_task = asyncio.create_task(_connect_zomato_background())

        # Wait briefly for the OAuth URL to be captured from mcp-remote stderr
        auth_url = None
        for _ in range(8):  # 8 × 0.5 s = 4 s max
            await asyncio.sleep(0.5)
            auth_url = get_zomato_auth_url()
            if auth_url:
                break

        return {
            "success": True,
            "connecting": True,
            "auth_url": auth_url,
            "message": "Complete Zomato authorization in the opened window.",
        }

    _connecting[server_id] = True

    try:
        config = _build_config(server_id)
        client = Client(config)
        await client.__aenter__()

        tools = await client.list_tools()

        _clients[server_id] = client
        _tools_cache[server_id] = tools
        _connected[server_id] = True
        _connecting[server_id] = False

        print(f"[MCP] Connected to {server_id} — {len(tools)} tools available")
        return {
            "success": True,
            "tools": len(tools),
            "message": f"Connected to {SERVER_REGISTRY[server_id]['name']}",
        }
    except Exception as exc:
        _connecting[server_id] = False
        _connected[server_id] = False
        print(f"[MCP] Failed to connect {server_id}: {exc}")
        return {"success": False, "error": str(exc)}


def _cleanup_mcp_remote_lockfiles():
    """Delete stale mcp-remote lockfiles whose PIDs are no longer running.

    mcp-remote stores lockfiles like:
      ~/.mcp-auth/mcp-remote-*/…_lock.json
    Each contains {"pid": …, "port": …, "timestamp": …}.
    If the pid is dead, the lockfile is stale and will cause new
    mcp-remote instances to wait forever.
    """
    lock_pattern = os.path.expanduser("~/.mcp-auth/mcp-remote-*/*_lock.json")
    for lock_path in glob.glob(lock_pattern):
        try:
            data = json.loads(Path(lock_path).read_text())
            pid = data.get("pid")
            if pid:
                try:
                    os.kill(pid, 0)  # probe — doesn't actually kill
                except OSError:
                    # Process is dead → stale lockfile
                    os.remove(lock_path)
                    print(f"[Zomato] Removed stale lockfile (pid {pid}): {lock_path}")
                else:
                    # Process alive but from a previous server session → kill it
                    try:
                        os.kill(pid, signal.SIGTERM)
                        print(f"[Zomato] Killed orphaned mcp-remote (pid {pid})")
                    except OSError:
                        pass
                    os.remove(lock_path)
                    print(f"[Zomato] Removed lockfile: {lock_path}")
        except Exception as exc:
            print(f"[Zomato] Error cleaning lockfile {lock_path}: {exc}")


async def _connect_zomato_background():
    """Connect to Zomato in a background task.

    mcp-remote opens a browser for OAuth and blocks until the user
    authorises.  Running this as a background task prevents the HTTP
    response from hanging.
    """
    # Clean up orphaned mcp-remote processes / stale lockfiles first
    _cleanup_mcp_remote_lockfiles()

    try:
        config = _build_config("zomato")
        client = Client(config)
        await client.__aenter__()

        tools = await client.list_tools()

        _clients["zomato"] = client
        _tools_cache["zomato"] = tools
        _connected["zomato"] = True
        _connecting["zomato"] = False

        print(f"[MCP] Connected to zomato — {len(tools)} tools available")
    except asyncio.CancelledError:
        _connecting["zomato"] = False
        _connected["zomato"] = False
        print("[MCP] Zomato connection cancelled")
    except Exception as exc:
        _connecting["zomato"] = False
        _connected["zomato"] = False
        print(f"[MCP] Failed to connect zomato: {exc}")


async def disconnect_server(server_id: str) -> dict[str, Any]:
    """Disconnect from an MCP server."""
    global _github_client, _figma_client, _hubspot_client, _zomato_connect_task
    
    if server_id == "github":
        _github_client = None
    elif server_id == "figma":
        _figma_client = None
    elif server_id == "hubspot":
        _hubspot_client = None
    elif server_id == "zomato":
        # Cancel background connect task if still running
        if _zomato_connect_task and not _zomato_connect_task.done():
            _zomato_connect_task.cancel()
            _zomato_connect_task = None
        # Kill any orphaned mcp-remote processes and remove lockfiles
        _cleanup_mcp_remote_lockfiles()
        if "zomato" in _clients:
            try:
                await _clients["zomato"].__aexit__(None, None, None)
            except Exception:
                pass
            del _clients["zomato"]
    elif server_id in _clients:
        try:
            await _clients[server_id].__aexit__(None, None, None)
        except Exception:
            pass
        del _clients[server_id]
    
    _connected[server_id] = False
    _connecting[server_id] = False
    _tools_cache.pop(server_id, None)
    return {"success": True, "message": f"Disconnected from {server_id}"}


def is_connected(server_id: str) -> bool:
    return _connected.get(server_id, False)


def is_connecting(server_id: str) -> bool:
    return _connecting.get(server_id, False)


async def list_tools(server_id: str) -> list:
    """List tools for a connected server."""
    if server_id in _tools_cache:
        return _tools_cache[server_id]
    if not is_connected(server_id):
        return []
    
    if server_id == "github":
        if not _github_client:
            return []
        tools = await _github_client.list_tools_async()
        _tools_cache[server_id] = tools
        return tools
    
    if server_id == "figma":
        if not _figma_client:
            return []
        tools = await _figma_client.list_tools_async()
        _tools_cache[server_id] = tools
        return tools

    if server_id == "hubspot":
        if not _hubspot_client:
            return []
        tools = await _hubspot_client.list_tools_async()
        _tools_cache[server_id] = tools
        return tools
    
    try:
        tools = await _clients[server_id].list_tools()
        _tools_cache[server_id] = tools
        return tools
    except Exception:
        return []


async def call_tool(server_id: str, tool_name: str, args: dict) -> Any:
    """Call a tool on a connected MCP server."""
    if not is_connected(server_id):
        raise RuntimeError(f"{SERVER_REGISTRY.get(server_id, {}).get('name', server_id)} is not connected")
    
    if server_id == "github":
        if not _github_client:
            raise RuntimeError("GitHub client not initialized")
        return await _github_client.call_tool_async(tool_name, args)
    
    if server_id == "figma":
        if not _figma_client:
            raise RuntimeError("Figma client not initialized")
        return await _figma_client.call_tool_async(tool_name, args)

    if server_id == "hubspot":
        if not _hubspot_client:
            raise RuntimeError("HubSpot client not initialized")
        return await _hubspot_client.call_tool_async(tool_name, args)
    
    return await _clients[server_id].call_tool(tool_name, args)


def _is_ready(server_id: str) -> bool:
    """Check whether a server has all pre-requisites to connect."""
    if server_id == "github":
        return bool(settings.GITHUB_PERSONAL_ACCESS_TOKEN.strip())
    if server_id in ("notion", "figma", "hubspot"):
        return _tokens.get(server_id) is not None
    # Zomato (oauth_browser) is always ready to attempt
    return True


def get_all_server_status() -> dict[str, Any]:
    """Return clean status of every registered server."""
    result = {}
    for sid, meta in SERVER_REGISTRY.items():
        result[sid] = {
            "id": sid,
            "name": meta["name"],
            "description": meta["description"],
            "connect_label": meta.get("connect_label", "Connect"),
            "connected": is_connected(sid),
            "connecting": is_connecting(sid),
            "toolCount": len(_tools_cache.get(sid, [])),
        }
    return result


async def cleanup_all():
    """Disconnect from all servers (shutdown hook)."""
    for sid in list(_clients.keys()):
        await disconnect_server(sid)


# ── Unified tool registry -----------------------------------------------------
async def get_all_connected_tools() -> list[dict[str, Any]]:
    """
    Return a flat list of all tools across all *connected* MCP servers.

    Each entry has the shape:
    {
        "server": "github",
        "tool": <raw_tool_object>,  # fastmcp Tool or dict
    }
    """
    results: list[dict[str, Any]] = []

    for server_id in SERVER_REGISTRY.keys():
        if not is_connected(server_id):
            continue

        try:
            tools = await list_tools(server_id)
        except Exception:
            tools = []

        for tool in tools:
            results.append({"server": server_id, "tool": tool})

    return results

