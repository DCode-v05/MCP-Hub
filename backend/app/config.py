"""Unified MCP Platform — Configuration."""

import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).parent.parent
load_dotenv(dotenv_path=BACKEND_DIR / ".env", override=True)


class Settings:
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    # GitHub Personal Access Token (from mcp folder approach)
    GITHUB_PERSONAL_ACCESS_TOKEN: str = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")

    # Notion OAuth
    NOTION_CLIENT_ID: str = os.environ.get("NOTION_CLIENT_ID", "")
    NOTION_CLIENT_SECRET: str = os.environ.get("NOTION_CLIENT_SECRET", "")

    # Figma OAuth
    FIGMA_CLIENT_ID: str = os.environ.get("FIGMA_CLIENT_ID", "")
    FIGMA_CLIENT_SECRET: str = os.environ.get("FIGMA_CLIENT_SECRET", "")

    # HubSpot OAuth
    HUBSPOT_CLIENT_ID: str = os.environ.get("HUBSPOT_CLIENT_ID", "")
    HUBSPOT_CLIENT_SECRET: str = os.environ.get("HUBSPOT_CLIENT_SECRET", "")
    HUBSPOT_SCOPES: str = os.environ.get(
        "HUBSPOT_SCOPES",
        "",
    )

    # GitHub OAuth (optional — falls back to PAT if not set)
    GITHUB_CLIENT_ID: str = os.environ.get("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET: str = os.environ.get("GITHUB_CLIENT_SECRET", "")

    # App
    FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    BACKEND_PORT: int = int(os.environ.get("PORT", "8000"))


settings = Settings()
