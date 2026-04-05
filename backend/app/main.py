"""Unified MCP Platform — FastAPI application."""

import glob
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import mcp_manager, storage, auth, chat
from app.config import settings


def _clear_mcp_remote_tokens():
    """Delete cached mcp-remote OAuth tokens so Zomato forces re-auth."""
    pattern = os.path.expanduser("~/.mcp-auth/mcp-remote-*/*_tokens.json")
    for path in glob.glob(pattern):
        try:
            os.remove(path)
            print(f"[BOOT] Removed cached Zomato token: {path}")
        except OSError:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    # Per-session auth: clear all stored tokens so users must sign in fresh
    for provider in ("github", "notion", "figma", "hubspot"):
        mcp_manager.set_token(provider, None)
    # Also clear mcp-remote's cached Zomato tokens
    _clear_mcp_remote_tokens()
    print("[BOOT] Session started — all OAuth tokens cleared (per-session auth)")
    yield
    # On shutdown: clean up all MCP connections
    await mcp_manager.cleanup_all()


app = FastAPI(title="Unified MCP Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router, tags=["Auth"])
app.include_router(chat.router, tags=["Chat"])


# ── Core endpoints ───────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "Unified MCP Platform is running."}


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Server management ────────────────────────────────────────────────────────
@app.get("/api/servers")
async def list_servers():
    """Return status of all MCP servers."""
    return mcp_manager.get_all_server_status()


@app.post("/api/servers/{server_id}/connect")
async def connect_server(server_id: str):
    """Connect to a specific MCP server."""
    result = await mcp_manager.connect_server(server_id)
    return result


@app.post("/api/servers/{server_id}/disconnect")
async def disconnect_server(server_id: str):
    """Disconnect from a specific MCP server."""
    result = await mcp_manager.disconnect_server(server_id)
    return result


@app.get("/api/servers/zomato/auth-url")
async def get_zomato_auth_url():
    """Return the captured Zomato OAuth URL (for polling fallback)."""
    url = mcp_manager.get_zomato_auth_url()
    return {"auth_url": url}


@app.get("/api/servers/{server_id}/tools")
async def list_tools(server_id: str):
    """List tools available on a connected server."""
    tools = await mcp_manager.list_tools(server_id)
    return {
        "server": server_id,
        "tools": [
            {"name": t.name if hasattr(t, "name") else t.get("name", ""),
             "description": t.description if hasattr(t, "description") else t.get("description", "")}
            for t in tools
        ],
    }


# ── Chat history ─────────────────────────────────────────────────────────────
@app.get("/api/chats")
async def list_chats():
    return storage.get_all_chats()


@app.post("/api/chats/new")
async def create_chat(server: str = "", title: str = "New Chat"):
    return storage.create_chat(server, title)


@app.get("/api/chats/{chat_id}")
async def get_chat(chat_id: str):
    chat_data = storage.get_chat(chat_id)
    if not chat_data:
        return {"error": "Chat not found"}, 404
    return chat_data


@app.delete("/api/chats/{chat_id}")
async def delete_chat(chat_id: str):
    storage.delete_chat(chat_id)
    return {"success": True}
