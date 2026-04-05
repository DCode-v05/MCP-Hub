# MCP Hub

## Project Description
A unified chat interface that integrates **5 MCP (Model Context Protocol) servers** — GitHub, Zomato, Notion, Figma & HubSpot — into a single conversational AI platform powered by OpenAI. Users can seamlessly interact with multiple services from one place using natural language and slash commands, with per-server OAuth management, persistent chat history, and an intelligent multi-server task planner.

---

## Project Details

### Problem Statement
Modern developers and teams juggle multiple platforms daily — code hosting, design tools, CRMs, note-taking apps, and more. Switching between dashboards is time-consuming and breaks focus. This project solves that by providing a single AI-powered chat interface that connects to multiple services via the Model Context Protocol, enabling users to manage repos, inspect designs, track deals, and order food — all from one conversation.

### Architecture Overview
The platform follows a decoupled client-server architecture:
- **Backend (FastAPI + Python):** Manages MCP server connections, OAuth flows, tool discovery, AI-powered planning, and chat persistence.
- **Frontend (React + Vite):** A dark-themed single-page app with a chat UI, server sidebar, slash-command picker, and real-time server status.
- **AI Layer (OpenAI GPT-4o-mini):** Handles natural language understanding, tool calling, and multi-server execution planning.

### Key Features
- **Single Chat Interface** — talk to any MCP server from one place
- **`/` Slash Commands** — type `/` to see and switch between MCP servers
- **5 MCP Server Integrations:**
  - **GitHub** — manage repos, issues, PRs, branches, code search
  - **Zomato** — browse restaurants, order food, track deliveries
  - **Notion** — manage pages, databases, workspace content
  - **Figma** — inspect designs, extract tokens, download images
  - **HubSpot** — manage contacts, deals, companies, and tickets
- **Multi-Server Planner** — AI analyzes intent and generates execution plans across multiple servers
- **Per-Server Connection Management** — connect/disconnect each server independently via OAuth or PAT
- **Chat History** — persistent conversations with auto-titling
- **Dark Theme UI** — clean, professional interface

### Server Connection Types

| Server   | Auth Type             | How to Connect                                         |
|----------|-----------------------|--------------------------------------------------------|
| GitHub   | Personal Access Token | Set `GITHUB_PERSONAL_ACCESS_TOKEN` in `.env`, then Connect |
| Notion   | OAuth                 | Click Connect → authorize in Notion                    |
| Figma    | OAuth                 | Click Connect → authorize in Figma                     |
| Zomato   | OAuth                 | Click Connect → complete Zomato login in browser       |
| HubSpot  | OAuth                 | Click Connect → authorize in HubSpot                   |

### API Endpoints

| Method | Endpoint                       | Description               |
|--------|--------------------------------|---------------------------|
| GET    | `/api/servers`                 | List all servers + status |
| POST   | `/api/servers/{id}/connect`    | Connect to a server       |
| POST   | `/api/servers/{id}/disconnect` | Disconnect from a server  |
| GET    | `/api/servers/{id}/tools`      | List server tools         |
| POST   | `/api/chat`                    | Send chat message         |
| GET    | `/api/chats`                   | List chat history         |
| POST   | `/api/chats/new`               | Create new chat           |
| DELETE | `/api/chats/{id}`              | Delete a chat             |

---

## Tech Stack
- **Backend:** Python 3.x, FastAPI, Uvicorn, Pydantic
- **AI/LLM:** OpenAI (GPT-4o-mini), MCP SDK, FastMCP
- **Frontend:** React 18, Vite 5, Lucide React (icons), Marked (markdown)
- **Auth:** OAuth 2.0 (Notion, Figma, HubSpot, Zomato), Personal Access Token (GitHub)
- **HTTP Client:** HTTPX
- **Environment:** python-dotenv

---

## Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/DCode-v05/MCP-Hub.git
cd MCP-Hub
```

### 2. Backend Setup
```bash
cd backend
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory with your API keys:
```env
OPENAI_API_KEY=your_openai_api_key

# GitHub
GITHUB_PERSONAL_ACCESS_TOKEN=your_github_pat

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

Start the backend:
```bash
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

---

## Usage
- **Connect servers** — click "Connect" on any server in the sidebar
- **Switch servers** — type `/` in the chat input to see the server picker
- **Chat** — type your message and it routes to the active MCP server
- **Slash commands** — `/github list my repos` or `/notion search meeting notes`
- **Multi-server tasks** — the planner automatically routes complex requests across connected servers

---

## Project Structure
```
MCP-Hub/
│
├── backend/                        # FastAPI + Python backend
│   ├── app/
│   │   ├── main.py                 # FastAPI app, endpoints & lifespan
│   │   ├── config.py               # Environment settings & API keys
│   │   ├── mcp_manager.py          # Unified MCP server manager
│   │   ├── chat.py                 # OpenAI + MCP tool-calling loop
│   │   ├── planner.py              # Multi-server execution planner
│   │   ├── auth.py                 # OAuth flows (Notion, Figma, HubSpot)
│   │   ├── storage.py              # Session & chat persistence
│   │   ├── github_client.py        # GitHub MCP client
│   │   ├── figma_client.py         # Figma MCP client
│   │   ├── hubspot_client.py       # HubSpot MCP client
│   │   ├── zomato_wrapper.py       # Zomato MCP wrapper
│   │   └── __init__.py
│   ├── .env                        # API keys & config (not committed)
│   └── requirements.txt            # Python dependencies
│
├── frontend/                       # React + Vite frontend
│   ├── src/
│   │   ├── main.jsx                # React entry point
│   │   ├── App.jsx                 # Main UI with slash command support
│   │   └── App.css                 # Dark theme styles
│   ├── index.html                  # HTML entry point
│   ├── package.json                # Node dependencies
│   └── vite.config.js              # Vite configuration
│
└── README.md                       # Project documentation
```

---

## Contributing

Contributions are welcome! To contribute:
1. Fork the repository
2. Create a new branch:
   ```bash
   git checkout -b feature/your-feature
   ```
3. Commit your changes:
   ```bash
   git commit -m "Add your feature"
   ```
4. Push to your branch:
   ```bash
   git push origin feature/your-feature
   ```
5. Open a pull request describing your changes.

---

## Contact
- **GitHub:** [DCode-v05](https://github.com/DCode-v05)
- **Email:** denistanb05@gmail.com
