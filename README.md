# MCP Hub

A chat app that talks to GitHub, Notion, Figma, HubSpot and Zomato through their MCP servers. You connect the services you want, then ask for things in plain English and GPT-4o-mini decides which tools to call.

I built it during my internship at September Platforms while working on MCP integrations. It is a FastAPI backend plus a React/Vite frontend.

## How it works

**Backend (`backend/app`)**

- `mcp_manager.py` keeps a registry of the five servers, their connection state, cached tool lists and tokens. Each server is reached differently:
  - GitHub, Figma and HubSpot have their own stdio clients (`github_client.py`, `figma_client.py`, `hubspot_client.py`). GitHub runs `@modelcontextprotocol/server-github` through `npx` with a personal access token.
  - Notion runs `@notionhq/notion-mcp-server` through a `fastmcp` client with the OAuth token passed in.
  - Zomato goes through `mcp-remote` (`zomato_wrapper.py`). It needs a browser login, so the connection runs as a background task and the wrapper saves the OAuth URL for the frontend to pick up.
- `chat.py` serves `POST /api/chat`. It collects tools from every connected server, namespaces them as `<server>_<tool>`, converts the MCP schemas to OpenAI function-calling format, and runs a tool-calling loop of up to 5 rounds. If the loop ends without a final answer, one more call summarises the tool results.
- The schema conversion cleans up what OpenAI rejects: it collapses `anyOf`/`oneOf`, strips `null` from unions, drops arrays with no `items`, and removes Notion's `icon` and `cover` properties.
- `planner.py` backs `POST /api/chat/multi`. The model first returns a JSON plan (`steps` of server, tool, arguments). Each step is checked against the servers and tools that are actually connected, then the steps run in order and the results are summarised.
- `auth.py` handles OAuth for Notion, Figma and HubSpot (HubSpot with PKCE). GitHub uses the token from `.env`.
- `storage.py` keeps tokens and chats in JSON files. Chats are titled from the first message. On every startup `main.py` clears the stored tokens and the cached `mcp-remote` tokens, so each run starts signed out.

**Frontend (`frontend/src`)**

A single `App.jsx` with the server sidebar, the chat, chat history and a slash menu: typing `/` lets you pick a server, for example `/github list my repos`. Replies are rendered as markdown with `marked`.

## Tech stack

Python, FastAPI, Uvicorn, OpenAI (`gpt-4o-mini`), `mcp`, `fastmcp`, React 18, Vite 5, `marked`, `lucide-react`.

## Setup

You need Python 3.10+, Node.js (the servers are launched with `npx`), an OpenAI API key, a GitHub personal access token, and OAuth app credentials for whichever of Notion, Figma and HubSpot you want.

```bash
cd backend
pip install -r requirements.txt
```

Create `backend/.env`:

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
GITHUB_PERSONAL_ACCESS_TOKEN=
NOTION_CLIENT_ID=
NOTION_CLIENT_SECRET=
FIGMA_CLIENT_ID=
FIGMA_CLIENT_SECRET=
HUBSPOT_CLIENT_ID=
HUBSPOT_CLIENT_SECRET=
```

Run the backend from `backend/`:

```bash
uvicorn app.main:app --reload --port 8000
```

Run the frontend from `frontend/`:

```bash
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` and `/auth` to port 8000.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/servers` | Status of all servers |
| POST | `/api/servers/{id}/connect` | Connect a server |
| POST | `/api/servers/{id}/disconnect` | Disconnect a server |
| GET | `/api/servers/{id}/tools` | List a server's tools |
| POST | `/api/chat` | Tool-calling chat |
| POST | `/api/chat/multi` | Planner-based multi-server chat |
| GET | `/api/chats` | List chats |
| POST | `/api/chats/new` | Create a chat |
| DELETE | `/api/chats/{id}` | Delete a chat |

## Structure

```
backend/app/    FastAPI app, MCP manager, chat loop, planner, OAuth, storage, per-server clients
frontend/src/   React UI (App.jsx, App.css, main.jsx)
```
