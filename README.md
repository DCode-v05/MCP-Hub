# MCP Hub

**One chat window that talks to five different services through the Model Context Protocol — GitHub, Notion, Figma, HubSpot and Zomato — with an LLM deciding which tools to call.**

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white) ![OpenAI](https://img.shields.io/badge/GPT--4o--mini-412991?style=flat&logo=openai&logoColor=white) ![MCP](https://img.shields.io/badge/Model_Context_Protocol-000000?style=flat&logo=anthropic&logoColor=white) ![React](https://img.shields.io/badge/React_18-20232A?style=flat&logo=react&logoColor=61DAFB) ![Vite](https://img.shields.io/badge/Vite_5-646CFF?style=flat&logo=vite&logoColor=white) ![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat&logo=javascript&logoColor=black)

## Overview

MCP Hub is a conversational AI app that connects to five separate Model Context Protocol (MCP) servers and exposes all of them through a single chat. You sign in to the services you want — GitHub, Notion, Figma, HubSpot, Zomato — and then talk to them in plain English from one place. Instead of jumping between a code host, a CRM, a design tool, a notes workspace and a food-delivery app, you ask once and the model figures out which server and which tool to call.

The idea is that each of those services already ships (or can be wrapped as) an MCP server with its own set of tools. MCP Hub is the orchestration layer on top: it manages the connections and OAuth, discovers each server's tools at runtime, normalizes their schemas so OpenAI's function-calling can use them, and runs a tool-calling loop that can hit tools from more than one server in a single turn. There's also a separate planner path that first writes an explicit multi-step execution plan before running anything.

I built this during my AI engineering internship at September Platforms ("September AI") as part of work on MCP integrations and agentic backends. The repo here is the standalone hub: a FastAPI backend plus a React/Vite frontend.

## Key Features

- **Five MCP servers behind one chat** — GitHub (repos, issues, PRs, branches, code search), Notion (pages, databases, workspace content), Figma (files, components, design tokens, image export), HubSpot (CRM contacts, deals, companies, tickets) and Zomato (restaurants, menus, ordering).
- **Slash-command server picker** — type `/` in the chat box to open a menu of servers and filter/switch between them; e.g. `/github list my repos` or `/notion search meeting notes`.
- **Unified tool-calling loop** — the backend pulls tools from every connected server, namespaces them (`github_create_issue`, `notion_search`, `figma_get_file`), and lets GPT-4o-mini call tools from multiple servers in the same conversation turn (up to 5 rounds per message).
- **Schema-cleaning layer** — MCP tool schemas don't always match what OpenAI's function-calling accepts, so the hub rewrites them: it collapses `anyOf`/`oneOf`, strips `null` from union types, drops arrays missing an `items` definition, and removes Notion's `icon`/`cover` properties that break validation.
- **AI multi-server planner** — a second endpoint (`/api/chat/multi`) where the model first produces a structured JSON plan (`steps` of `server` + `tool` + `arguments`), each step is validated against the actually-connected servers and tools, then executed in order and summarized.
- **Per-server connection management** — connect and disconnect each server independently; GitHub uses a Personal Access Token, Notion/Figma/HubSpot use OAuth 2.0 (HubSpot with PKCE), Zomato uses `mcp-remote`'s browser-based OAuth.
- **Per-session auth by default** — on every backend startup all stored tokens are cleared (including cached `mcp-remote` Zomato tokens), so each session starts signed-out.
- **Persistent chat history with auto-titling** — conversations are saved to a JSON store and the chat title is set automatically from the first ~60 characters of your message.
- **Tool-call logging** — each response records which server and tool ran with what arguments, so you can see what the model actually did.
- **Dark-themed single-page UI** — React 18 + Vite app with a server sidebar, per-server color coding, markdown rendering and live connection status.

## How It Works

The app is split into a Python backend that owns all the MCP/LLM logic and a React frontend that's mostly a chat surface.

### Backend (FastAPI)

`main.py` boots the FastAPI app. Its lifespan hook is where the per-session auth policy lives: on startup it wipes the stored token for every provider and deletes any cached `mcp-remote` OAuth token files under `~/.mcp-auth`, so nobody inherits a previous session's logins. It mounts two routers (`auth`, `chat`) and exposes the server-management and chat-history endpoints directly.

### MCP server manager

`mcp_manager.py` is the core. It holds a `SERVER_REGISTRY` describing the five servers (name, description, connect label) and keeps runtime state for which are connected, which are mid-connection, the per-server tool cache, and the OAuth/PAT tokens. Connection logic is per-server because each MCP server is reached differently:

- **GitHub** — a dedicated `GitHubMCPClient` that spawns `npx @modelcontextprotocol/server-github` over stdio, passing the PAT as `GITHUB_TOKEN`. (OAuth is supported too if `GITHUB_CLIENT_ID` is set, otherwise it falls back to the PAT.)
- **Figma** and **HubSpot** — dedicated stdio clients (`FigmaMCPClient`, `HubSpotMCPClient`) so each gets full control over its environment and token.
- **Notion** — a `fastmcp` `Client` running `npx @notionhq/notion-mcp-server` with the OAuth token injected as `NOTION_TOKEN`.
- **Zomato** — a `fastmcp` `Client` pointed through a small `zomato_wrapper.py` at `npx mcp-remote https://mcp-server.zomato.com/mcp`. Because `mcp-remote` opens a browser and blocks on OAuth, the connection runs as a background asyncio task; the wrapper captures the OAuth URL to a temp file so the frontend can poll for it, and the manager cleans up stale `mcp-remote` lockfiles/orphan processes before connecting.

The manager exposes a uniform interface to the rest of the app — `connect_server`, `disconnect_server`, `list_tools`, `call_tool`, `get_all_connected_tools`, `get_all_server_status` — so the chat and planner code doesn't care how a given server is wired up.

### Chat: the unified tool-calling loop

`chat.py` handles `/api/chat`. The flow:

1. Gather tools from every connected server via the manager.
2. For each tool, convert its MCP input schema into OpenAI function-calling format. Tool names are namespaced with the server id (`<server>_<tool>`) so names stay unique across servers, and a `TOOL_NAME_MAP` records how to translate the namespaced name back to a real `(server, tool)` pair.
3. Run the conversation against `gpt-4o-mini` with `tool_choice="auto"`. When the model returns tool calls, each is dispatched through `mcp_manager.call_tool`, the text result is fed back as a `tool` message, and the loop repeats — up to 5 rounds.
4. If the loop runs out of rounds without a clean final answer, a fallback call asks the model to summarize the tool results into one final response.

A `UNIFIED_SYSTEM_PROMPT` tells the model it's connected to several services and may use tools from more than one. There are also per-server system prompts (GitHub, Zomato, Notion, Figma, HubSpot) available for single-server framing, and an optional `server` hint in the request is treated as a soft preference rather than a hard route.

### Planner: explicit multi-server plans

`planner.py` powers the alternative `/api/chat/multi` endpoint. Here the model is asked to *plan* before acting: given the connected servers and their tool lists, it returns JSON of the form `{"steps": [{"server", "tool", "arguments"}, ...]}` at temperature 0.5 for more deterministic output. The plan is validated — every step's server must be connected and every tool must actually exist on that server — then `chat.py` executes the steps in order, collects results, and runs a final summarization pass. This path is for requests that clearly span multiple services, where you want the routing decided up front instead of inside a free-form loop.

### Auth

`auth.py` implements the OAuth flows. Notion and Figma use standard authorization-code flows; HubSpot uses authorization-code with PKCE (the verifier is kept in memory keyed by OAuth state). Each callback exchanges the code for an access token, persists it, and registers it with the MCP manager. GitHub skips OAuth and uses a PAT from the environment.

### Storage

`storage.py` is deliberately simple — JSON files on disk. `sessions.json` holds per-provider tokens; `chats.json` holds conversations. Adding a message auto-titles a "New Chat" from the first user message and stamps timestamps. No database, which keeps the project easy to run locally.

### Frontend (React + Vite)

A single `App.jsx` drives everything: it fetches server status from `/api/servers`, renders the color-coded server sidebar with live connected/connecting state, and handles the chat. Typing `/` opens a filterable slash menu to pick a server; messages POST to `/api/chat`; assistant replies are rendered as markdown via `marked`; icons come from inline SVGs and `lucide-react`. Chat history is listed and switchable in the sidebar.

## Tech Stack

- **Languages:** Python (backend), JavaScript / JSX (frontend), CSS, HTML.
- **Backend frameworks:** FastAPI, Uvicorn, Pydantic, HTTPX, python-dotenv.
- **AI / MCP:** OpenAI `gpt-4o-mini` (function calling), the MCP Python SDK (`mcp`) and `fastmcp` as MCP clients, `mcp-remote` for the hosted Zomato server, plus the GitHub/Notion MCP servers run via `npx`.
- **Frontend:** React 18, Vite 5, `marked` (markdown), `lucide-react` (icons).
- **Auth:** OAuth 2.0 (Notion, Figma, HubSpot with PKCE, Zomato via `mcp-remote`), GitHub Personal Access Token.
- **Storage:** flat JSON files (no external database).

## Getting Started

### Prerequisites

- Python 3.10+ and Node.js 18+ (the GitHub, Notion and Zomato servers are launched with `npx`, so Node has to be on PATH).
- An OpenAI API key.
- A GitHub Personal Access Token, plus OAuth app credentials for whichever of Notion / Figma / HubSpot you want to connect.

### Installation

```bash
git clone https://github.com/DCode-v05/MCP-Hub.git
cd MCP-Hub
```

Backend:

```bash
cd backend
pip install -r requirements.txt
```

Create `backend/.env`:

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini

# GitHub (PAT mode)
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token

# Notion OAuth
NOTION_CLIENT_ID=your_notion_client_id
NOTION_CLIENT_SECRET=your_notion_client_secret

# Figma OAuth
FIGMA_CLIENT_ID=your_figma_client_id
FIGMA_CLIENT_SECRET=your_figma_client_secret

# HubSpot OAuth
HUBSPOT_CLIENT_ID=your_hubspot_client_id
HUBSPOT_CLIENT_SECRET=your_hubspot_client_secret
```

Frontend:

```bash
cd ../frontend
npm install
```

### Running

Backend (from `backend/`):

```bash
uvicorn app.main:app --reload --port 8000
```

Frontend (from `frontend/`):

```bash
npm run dev
```

Then open http://localhost:5173. The frontend talks to the backend at `http://localhost:8000`.

## Usage

1. **Connect a server** — click *Connect* on a server in the sidebar. GitHub connects from your `.env` PAT; Notion/Figma/HubSpot open an OAuth flow; Zomato opens a browser window for its login.
2. **Pick a server inline** — type `/` in the chat box to open the slash menu, then keep typing to filter (e.g. `/git`). The rest of your message is the request: `/github open issues in DCode-v05/MCP-Hub`.
3. **Just ask** — with servers connected you can also skip the slash command and let the model route. It will call tools from whichever connected servers fit the request.
4. **Multi-server requests** — the planner endpoint (`/api/chat/multi`) builds and runs an explicit cross-server plan when a request spans several services.
5. **History** — past chats appear in the sidebar, auto-titled from your first message; you can switch between them or delete them.

Useful API endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/servers` | Status of all five servers |
| POST | `/api/servers/{id}/connect` | Connect a server |
| POST | `/api/servers/{id}/disconnect` | Disconnect a server |
| GET | `/api/servers/{id}/tools` | List a connected server's tools |
| POST | `/api/chat` | Unified tool-calling chat |
| POST | `/api/chat/multi` | Planner-based multi-server chat |
| GET | `/api/chats` | List chat history |
| POST | `/api/chats/new` | Create a chat |
| DELETE | `/api/chats/{id}` | Delete a chat |

## Project Structure

```
MCP-Hub/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, lifespan (per-session token clearing), server + history endpoints
│   │   ├── config.py          # Settings loaded from .env (OpenAI key/model, OAuth creds, ports)
│   │   ├── mcp_manager.py     # Server registry, connection state, token store, connect/list/call routing
│   │   ├── chat.py            # Unified OpenAI tool-calling loop + /api/chat/multi planner execution
│   │   ├── planner.py         # Builds & validates JSON multi-server execution plans
│   │   ├── auth.py            # OAuth flows: Notion, Figma, HubSpot (PKCE)
│   │   ├── storage.py         # JSON-file persistence for sessions + chats, auto-titling
│   │   ├── github_client.py   # GitHub MCP client over stdio (npx server-github)
│   │   ├── figma_client.py    # Figma MCP client
│   │   ├── hubspot_client.py  # HubSpot MCP client
│   │   └── zomato_wrapper.py  # Wraps mcp-remote, captures the Zomato OAuth URL
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Chat UI, server sidebar, slash-command menu, markdown rendering
│   │   ├── App.css            # Dark theme
│   │   └── main.jsx           # React entry point
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
└── README.md
```

---

## Contact

<table>
  <tr><td><b>Portfolio:</b> <a href="https://www.denistan.me">Denistan</a></td><td><b>LinkedIn:</b> <a href="https://www.linkedin.com/in/denistanb">denistanb</a></td></tr>
  <tr><td><b>GitHub:</b> <a href="https://github.com/DCode-v05">DCode-v05</a></td><td><b>LeetCode:</b> <a href="https://leetcode.com/u/Denistan_B">Denistan_B</a></td></tr>
  <tr><td colspan="2" align="center"><b>Email:</b> <a href="mailto:denistanb05@gmail.com">denistanb05@gmail.com</a></td></tr>
</table>

Made with ❤️ by **Denistan B**
