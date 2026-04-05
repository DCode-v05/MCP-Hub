"""JSON-file storage for sessions and chat history."""

import json
import os
import uuid
from datetime import datetime

STORAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSIONS_FILE = os.path.join(STORAGE_DIR, "sessions.json")
CHATS_FILE = os.path.join(STORAGE_DIR, "chats.json")


# ── Sessions (OAuth tokens for all providers) ───────────────────────────────
def _load_sessions() -> dict:
    if not os.path.exists(SESSIONS_FILE):
        return {"sessions": {}}
    try:
        with open(SESSIONS_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) and "sessions" in data else {"sessions": {}}
    except Exception:
        return {"sessions": {}}


def _save_sessions(data: dict):
    with open(SESSIONS_FILE, "w") as f:
        json.dump(data, f, indent=2)


# -- Generic token helpers (provider = "notion", "github", "figma") ---------
def save_token(provider: str, session_id: str, token: str):
    """Save an OAuth token for any provider."""
    data = _load_sessions()
    data["sessions"][f"{provider}_{session_id}"] = {
        "provider": provider,
        "token": token,
        "created_at": datetime.now().isoformat(),
    }
    _save_sessions(data)


def get_latest_token(provider: str) -> str | None:
    """Get the most recently saved token for a given provider."""
    data = _load_sessions()
    sessions = data.get("sessions", {})
    provider_sessions = {
        k: v for k, v in sessions.items()
        if v.get("provider") == provider or
        (provider == "notion" and "notion_token" in v)  # backward compat
    }
    if not provider_sessions:
        return None
    latest = max(provider_sessions.items(), key=lambda x: x[1].get("created_at", ""))
    # support old format (notion_token) and new format (token)
    return latest[1].get("token") or latest[1].get("notion_token")


# -- Backward-compatible Notion helpers -------------------------------------
def save_notion_token(session_id: str, token: str):
    save_token("notion", session_id, token)


def get_notion_token(session_id: str) -> str | None:
    data = _load_sessions()
    session = data.get("sessions", {}).get(f"notion_{session_id}")
    if session:
        return session.get("token")
    # backward compat: old key format without provider prefix
    session = data.get("sessions", {}).get(session_id)
    return session.get("notion_token") if session else None


def get_latest_notion_token() -> str | None:
    return get_latest_token("notion")


def has_notion_token(session_id: str) -> bool:
    return get_notion_token(session_id) is not None


# ── Chat history ─────────────────────────────────────────────────────────────
def _load_chats() -> dict:
    if not os.path.exists(CHATS_FILE):
        return {"chats": {}}
    try:
        with open(CHATS_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) and "chats" in data else {"chats": {}}
    except Exception:
        return {"chats": {}}


def _save_chats(data: dict):
    with open(CHATS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_all_chats() -> list[dict]:
    data = _load_chats()
    chats = []
    for cid, chat in data.get("chats", {}).items():
        chats.append({
            "id": cid,
            "title": chat.get("title", "New Chat"),
            "server": chat.get("server", ""),
            "createdAt": chat.get("createdAt", ""),
            "messageCount": len(chat.get("messages", [])),
        })
    chats.sort(key=lambda c: c.get("createdAt", ""), reverse=True)
    return chats


def create_chat(server: str = "", title: str = "New Chat") -> dict:
    data = _load_chats()
    chat_id = str(uuid.uuid4())
    chat = {
        "id": chat_id,
        "title": title,
        "server": server,
        "createdAt": datetime.now().isoformat(),
        "messages": [],
    }
    data["chats"][chat_id] = chat
    _save_chats(data)
    return chat


def get_chat(chat_id: str) -> dict | None:
    data = _load_chats()
    return data.get("chats", {}).get(chat_id)


def add_message(chat_id: str, role: str, content: str, server: str = "", tool_calls: list | None = None):
    data = _load_chats()
    chat = data.get("chats", {}).get(chat_id)
    if not chat:
        return
    msg = {
        "role": role,
        "content": content,
        "server": server,
        "timestamp": datetime.now().isoformat(),
    }
    if tool_calls:
        msg["toolCalls"] = tool_calls
    chat["messages"].append(msg)

    # Auto-update title from first user message
    if role == "user" and chat.get("title") == "New Chat":
        chat["title"] = content[:60] + ("…" if len(content) > 60 else "")

    # Update server if not set
    if server and not chat.get("server"):
        chat["server"] = server

    _save_chats(data)


def delete_chat(chat_id: str):
    data = _load_chats()
    data.get("chats", {}).pop(chat_id, None)
    _save_chats(data)
