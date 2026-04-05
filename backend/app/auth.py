"""OAuth flows for Notion and Figma in the Unified MCP Platform."""

import base64
import hashlib
import secrets
import uuid
from urllib.parse import urlencode, quote

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.config import settings
from app import storage, mcp_manager

router = APIRouter()

# Temporary in-memory PKCE verifier store keyed by OAuth state
_hubspot_pkce_verifiers: dict[str, str] = {}


# ═════════════════════════════════════════════════════════════════════════════
#  Notion OAuth
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/auth/notion/login")
async def notion_login():
    """Redirect user to Notion OAuth authorization page."""
    if not settings.NOTION_CLIENT_ID:
        raise HTTPException(status_code=500, detail="NOTION_CLIENT_ID is not configured.")

    redirect_uri = f"http://localhost:{settings.BACKEND_PORT}/auth/notion/callback"
    state = str(uuid.uuid4())
    return RedirectResponse(
        f"https://api.notion.com/v1/oauth/authorize?"
        f"client_id={settings.NOTION_CLIENT_ID}&"
        f"response_type=code&"
        f"owner=user&"
        f"redirect_uri={quote(redirect_uri, safe='')}&"
        f"state={state}"
    )


@router.get("/auth/notion/callback")
async def notion_callback(code: str, state: str):
    """Handle Notion OAuth callback — exchange code for access token."""
    if not settings.NOTION_CLIENT_ID or not settings.NOTION_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Notion OAuth credentials not configured.")

    auth_str = base64.b64encode(
        f"{settings.NOTION_CLIENT_ID}:{settings.NOTION_CLIENT_SECRET}".encode()
    ).decode()

    redirect_uri = f"http://localhost:{settings.BACKEND_PORT}/auth/notion/callback"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.notion.com/v1/oauth/token",
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={
                "Authorization": f"Basic {auth_str}",
                "Notion-Version": "2022-06-28",
            },
        )
        data = resp.json()

        if "error" in data:
            raise HTTPException(status_code=400, detail=data.get("error"))

        access_token = data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token received from Notion")

        # Persist token and set it in MCP manager
        storage.save_token("notion", state, access_token)
        mcp_manager.set_token("notion", access_token)

        return RedirectResponse(f"{settings.FRONTEND_URL}?notion_connected=true")


@router.get("/auth/notion/status")
async def notion_status():
    """Check if Notion is connected."""
    token = mcp_manager.get_token("notion")
    return {"connected": token is not None}


# ═════════════════════════════════════════════════════════════════════════════
#  Figma OAuth
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/auth/figma/login")
async def figma_login():
    """Redirect user to Figma OAuth authorization page."""
    if not settings.FIGMA_CLIENT_ID:
        raise HTTPException(status_code=500, detail="FIGMA_CLIENT_ID is not configured.")

    redirect_uri = f"http://localhost:{settings.BACKEND_PORT}/auth/figma/callback"
    state = str(uuid.uuid4())
    return RedirectResponse(
        f"https://www.figma.com/oauth?"
        f"client_id={settings.FIGMA_CLIENT_ID}&"
        f"redirect_uri={redirect_uri}&"
        f"scope=current_user:read,file_content:read,file_metadata:read,file_comments:read,file_comments:write,file_versions:read&"
        f"state={state}&"
        f"response_type=code"
    )


@router.get("/auth/figma/callback")
async def figma_callback(code: str, state: str):
    """Handle Figma OAuth callback — exchange code for access token."""
    if not settings.FIGMA_CLIENT_ID or not settings.FIGMA_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Figma OAuth credentials not configured.")

    redirect_uri = f"http://localhost:{settings.BACKEND_PORT}/auth/figma/callback"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.figma.com/v1/oauth/token",
            data={
                "client_id": settings.FIGMA_CLIENT_ID,
                "client_secret": settings.FIGMA_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "code": code,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        data = resp.json()

        if "error" in data or resp.status_code != 200:
            raise HTTPException(status_code=400, detail=data.get("message", data.get("error", "Figma OAuth failed")))

        access_token = data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token received from Figma")

        # Persist token and set it in MCP manager
        storage.save_token("figma", state, access_token)
        mcp_manager.set_token("figma", access_token)

        return RedirectResponse(f"{settings.FRONTEND_URL}?figma_connected=true")


@router.get("/auth/figma/status")
async def figma_status():
    """Check if Figma is connected (has OAuth token)."""
    token = mcp_manager.get_token("figma")
    return {"connected": token is not None}


# ═════════════════════════════════════════════════════════════════════════════
#  HubSpot OAuth
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/auth/hubspot/login")
async def hubspot_login():
    """Redirect user to HubSpot OAuth authorization page."""
    if not settings.HUBSPOT_CLIENT_ID:
        raise HTTPException(status_code=500, detail="HUBSPOT_CLIENT_ID is not configured.")

    redirect_uri = f"http://localhost:{settings.BACKEND_PORT}/auth/hubspot/callback"
    state = str(uuid.uuid4())

    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode("utf-8")).digest()
    ).decode("utf-8").rstrip("=")
    _hubspot_pkce_verifiers[state] = code_verifier

    params = {
        "client_id": settings.HUBSPOT_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    query = urlencode(params, quote_via=quote)
    return RedirectResponse(
        f"https://app.hubspot.com/oauth/authorize?{query}"
    )


@router.get("/auth/hubspot/callback")
async def hubspot_callback(code: str, state: str):
    """Handle HubSpot OAuth callback — exchange code for access token."""
    if not settings.HUBSPOT_CLIENT_ID or not settings.HUBSPOT_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="HubSpot OAuth credentials not configured.")

    redirect_uri = f"http://localhost:{settings.BACKEND_PORT}/auth/hubspot/callback"
    code_verifier = _hubspot_pkce_verifiers.pop(state, None)
    if not code_verifier:
        raise HTTPException(status_code=400, detail="Missing or expired HubSpot PKCE verifier.")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.hubapi.com/oauth/v1/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.HUBSPOT_CLIENT_ID,
                "client_secret": settings.HUBSPOT_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "code": code,
                "code_verifier": code_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        data = resp.json()

        if "error" in data or resp.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=data.get("message", data.get("error", "HubSpot OAuth failed")),
            )

        access_token = data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token received from HubSpot")

        storage.save_token("hubspot", state, access_token)
        mcp_manager.set_token("hubspot", access_token)

        return RedirectResponse(f"{settings.FRONTEND_URL}?hubspot_connected=true")


@router.get("/auth/hubspot/status")
async def hubspot_status():
    """Check if HubSpot is connected via OAuth."""
    token = mcp_manager.get_token("hubspot")
    return {"connected": token is not None}


# ═════════════════════════════════════════════════════════════════════════════
#  GitHub OAuth  (optional — only works when GITHUB_CLIENT_ID is set)
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/auth/github/login")
async def github_login():
    """Redirect user to GitHub OAuth authorization page."""
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GITHUB_CLIENT_ID is not configured.")

    redirect_uri = f"http://localhost:{settings.BACKEND_PORT}/auth/github/callback"
    state = str(uuid.uuid4())
    return RedirectResponse(
        f"https://github.com/login/oauth/authorize?"
        f"client_id={settings.GITHUB_CLIENT_ID}&"
        f"redirect_uri={redirect_uri}&"
        f"scope=repo,user,read:org&"
        f"state={state}&"
        f"login="
    )


@router.get("/auth/github/callback")
async def github_callback(code: str, state: str):
    """Handle GitHub OAuth callback — exchange code for access token."""
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="GitHub OAuth credentials not configured.")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        data = resp.json()

        if "error" in data:
            raise HTTPException(
                status_code=400,
                detail=data.get("error_description", data.get("error")),
            )

        access_token = data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token received from GitHub")

        storage.save_token("github", state, access_token)
        mcp_manager.set_token("github", access_token)

        return RedirectResponse(f"{settings.FRONTEND_URL}?github_connected=true")


@router.get("/auth/github/status")
async def github_status():
    """Check if GitHub is connected via OAuth."""
    token = mcp_manager.get_token("github")
    return {"connected": token is not None}
