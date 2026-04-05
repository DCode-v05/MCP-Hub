import React, { useState, useEffect, useRef, useCallback } from "react";
import { marked } from "marked";

/* ─── Icon SVGs ──────────────────────────────────────────────────────────── */
const Icons = {
  github: (
    <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  ),
  zomato: (
    <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15H7v-2h4v2zm6-4H7v-2h10v2zm0-4H7V7h10v2z" />
    </svg>
  ),
  notion: (
    <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
      <path d="M4 4.5A2.5 2.5 0 016.5 2H18a2 2 0 012 2v16a2 2 0 01-2 2H6.5A2.5 2.5 0 014 19.5v-15zM6.5 4a.5.5 0 00-.5.5v15a.5.5 0 00.5.5H18V4H6.5zM8 7h8v2H8V7zm0 4h8v2H8v-2zm0 4h5v2H8v-2z" />
    </svg>
  ),
  figma: (
    <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
      <path d="M5 5.5A3.5 3.5 0 018.5 2H12v7H8.5A3.5 3.5 0 015 5.5zM12 2h3.5a3.5 3.5 0 110 7H12V2zm0 12.5a3.5 3.5 0 117 0 3.5 3.5 0 01-7 0zm-7 0A3.5 3.5 0 018.5 11H12v3.5a3.5 3.5 0 01-7 0zM5 19a3.5 3.5 0 013.5-3.5H12V19a3.5 3.5 0 11-7 0z" />
    </svg>
  ),
  hubspot: (
    <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
      <path d="M14.5 2a2.5 2.5 0 00-2.5 2.5V8a4 4 0 00-3 3.87H6.5a2.5 2.5 0 100 2H9a4 4 0 003 3.87V21.5a2.5 2.5 0 105 0v-1.68a4 4 0 001.66-6.3l1.78-1.03A2.5 2.5 0 1019.2 10.3l-1.79 1.03A4 4 0 0014.5 8V4.5A2.5 2.5 0 0014.5 2zM6.5 15a.5.5 0 110-1 .5.5 0 010 1zm8 2a2 2 0 110-4 2 2 0 010 4zm5-8a.5.5 0 110-1 .5.5 0 010 1zm-5 14a.5.5 0 110-1 .5.5 0 010 1z" />
    </svg>
  ),
  send: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20">
      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
    </svg>
  ),
  plus: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
      <path d="M12 5v14M5 12h14" />
    </svg>
  ),
  trash: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
      <path d="M3 6h18M8 6V4h8v2M5 6l1 14h12l1-14M10 11v6M14 11v6" />
    </svg>
  ),
  check: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="14" height="14">
      <path d="M20 6L9 17l-5-5" />
    </svg>
  ),
  link: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
      <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" />
    </svg>
  ),
};

const SERVER_COLORS = {
  github: "#8b949e",
  zomato: "#e23744",
  notion: "#ffffff",
  figma: "#a259ff",
  hubspot: "#ff7a59",
};

const API = "http://localhost:8000";

/* ─── Markdown renderer ──────────────────────────────────────────────────── */
marked.setOptions({ breaks: true, gfm: true });

function renderMarkdown(text) {
  if (!text) return "";
  return marked.parse(text);
}

/* ─── Main App ───────────────────────────────────────────────────────────── */
export default function App() {
  const [servers, setServers] = useState({});
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSlashMenu, setShowSlashMenu] = useState(false);
  const [slashFilter, setSlashFilter] = useState("");
  const [slashIndex, setSlashIndex] = useState(0);
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [connectingServer, setConnectingServer] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [toolsModal, setToolsModal] = useState({ open: false, serverId: null, serverName: "", tools: [], phase: "confirm" });

  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  /* ── Fetch servers ──────────────────────────────────────────────────────── */
  const fetchServers = useCallback(async () => {
    try {
      console.log(`[DEBUG] Fetching servers from ${API}/api/servers`);
      const res = await fetch(`${API}/api/servers`);
      const data = await res.json();
      console.log("[DEBUG] Servers fetched:", data);
      setServers(data);
    } catch (e) {
      console.error("[ERROR] Failed to fetch servers:", e);
      setServers({});
    }
  }, []);

  const fetchChats = useCallback(async () => {
    try {
      console.log(`[DEBUG] Fetching chats from ${API}/api/chats`);
      const res = await fetch(`${API}/api/chats`);
      const data = await res.json();
      console.log("[DEBUG] Chats fetched:", data);
      setChats(data);
    } catch (e) {
      console.error("[ERROR] Failed to fetch chats:", e);
      setChats([]);
    }
  }, []);

  useEffect(() => {
    console.log("[STARTUP] Fetching initial data...");
    fetchServers();
    fetchChats();
    const interval = setInterval(fetchServers, 5000);
    return () => clearInterval(interval);
  }, [fetchServers, fetchChats]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Handle OAuth callback — user returned from provider auth page
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    for (const provider of ["github", "notion", "figma", "hubspot"]) {
      if (params.get(`${provider}_connected`) === "true") {
        window.history.replaceState({}, "", "/");
        handleConnect(provider);
        break;
      }
    }
  }, []);

  /* ── Server connection ──────────────────────────────────────────────────── */
  const handleConnect = async (serverId) => {
    // For Zomato: pre-open a popup immediately (within user-gesture context)
    // so the browser doesn't block it when we set the URL later.
    let zomatoPopup = null;
    if (serverId === "zomato" && !servers[serverId]?.connected) {
      zomatoPopup = window.open("about:blank", "zomato-auth", "width=600,height=700");
    }

    setConnectingServer(serverId);
    try {
      const res = await fetch(`${API}/api/servers/${serverId}/connect`, { method: "POST" });
      const data = await res.json();

      // Backend says we need OAuth — redirect to provider's auth page (same tab)
      if (data.needs_auth && data.auth_url) {
        if (zomatoPopup) zomatoPopup.close();
        window.location.href = `${API}${data.auth_url}`;
        return;
      }

      // Zomato: navigate the pre-opened popup to the auth URL
      if (serverId === "zomato" && zomatoPopup) {
        if (data.auth_url) {
          zomatoPopup.location.href = data.auth_url;
        } else if (data.connecting) {
          // URL wasn't ready yet — poll and redirect the popup when it arrives
          (async () => {
            for (let i = 0; i < 20; i++) {
              await new Promise((r) => setTimeout(r, 1000));
              try {
                const urlRes = await fetch(`${API}/api/servers/zomato/auth-url`);
                const urlData = await urlRes.json();
                if (urlData.auth_url) {
                  zomatoPopup.location.href = urlData.auth_url;
                  return;
                }
              } catch {}
            }
            // Timed out — close the empty popup
            zomatoPopup.close();
          })();
        } else {
          zomatoPopup.close();
        }
      }

      await fetchServers();
    } catch (e) {
      console.error("Connect failed:", e);
      if (zomatoPopup) zomatoPopup.close();
    }
    setConnectingServer(null);
  };

  const handleDisconnect = async (serverId) => {
    try {
      await fetch(`${API}/api/servers/${serverId}/disconnect`, { method: "POST" });
      await fetchServers();
    } catch (e) {
      console.error("Disconnect failed:", e);
    }
  };

  /* ── Chat management ────────────────────────────────────────────────────── */
  const handleNewChat = async () => {
    try {
      const res = await fetch(`${API}/api/chats/new`, { method: "POST" });
      const chat = await res.json();
      setActiveChatId(chat.id);
      setMessages([]);
      await fetchChats();
    } catch (e) {
      console.error("New chat failed:", e);
    }
  };

  const handleLoadChat = async (chatId) => {
    try {
      const res = await fetch(`${API}/api/chats/${chatId}`);
      const data = await res.json();
      setActiveChatId(chatId);
      setMessages(
        (data.messages || []).map((m) => ({
          role: m.role,
          content: m.content,
          server: m.server,
          toolCalls: m.toolCalls,
        }))
      );
    } catch (e) {
      console.error("Load chat failed:", e);
    }
  };

  const handleDeleteChat = async (chatId, e) => {
    e.stopPropagation();
    await fetch(`${API}/api/chats/${chatId}`, { method: "DELETE" });
    if (activeChatId === chatId) {
      setActiveChatId(null);
      setMessages([]);
    }
    await fetchChats();
  };

  /* ── Send message ───────────────────────────────────────────────────────── */
  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const messageText = input.trim();

    const userMsg = { role: "user", content: messageText };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setShowSlashMenu(false);
    setLoading(true);

    let chatId = activeChatId;
    if (!chatId) {
      try {
        const res = await fetch(`${API}/api/chats/new`, { method: "POST" });
        const chat = await res.json();
        chatId = chat.id;
        setActiveChatId(chatId);
      } catch (e) { /* continue */ }
    }

    try {
      console.log("[DEBUG] Sending message to /api/chat");
      const res = await fetch(`${API}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: messageText,
          chatId,
          history: messages.map((m) => ({ role: m.role, content: m.content })),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Chat request failed");

      console.log("[DEBUG] Response from /api/chat:", data);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.response,
          server: data.server,
          toolCalls: data.toolCalls,
        },
      ]);
    } catch (e) {
      console.error("[ERROR] Chat failed:", e);
      setMessages((prev) => [
        ...prev,
        { role: "system", content: `Error: ${e.message}` },
      ]);
    }

    setLoading(false);
    await fetchChats();
  };

  /* ── Input handling ─────────────────────────────────────────────────────── */
  const handleInputChange = (e) => {
    const val = e.target.value;
    setInput(val);

    if (val === "/") {
      setShowSlashMenu(true);
      setSlashFilter("");
      setSlashIndex(0);
    } else if (val.startsWith("/") && !val.includes(" ")) {
      setShowSlashMenu(true);
      setSlashFilter(val.slice(1).toLowerCase());
      setSlashIndex(0);
    } else {
      setShowSlashMenu(false);
    }
  };

  const filteredServers = Object.entries(servers).filter(([id]) =>
    id.toLowerCase().includes(slashFilter)
  );

  const handleKeyDown = (e) => {
    if (showSlashMenu && filteredServers.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSlashIndex((prev) => (prev + 1) % filteredServers.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSlashIndex((prev) => (prev - 1 + filteredServers.length) % filteredServers.length);
      } else if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        const [selectedId] = filteredServers[slashIndex];
        selectSlashServer(selectedId);
      } else if (e.key === "Escape") {
        setShowSlashMenu(false);
      }
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const selectSlashServer = (serverId) => {
    setInput(`/${serverId} `);
    setShowSlashMenu(false);
    inputRef.current?.focus();
  };

  /* ── Tools modal ─────────────────────────────────────────────────────── */
  const handleServerCardClick = (serverId) => {
    const srv = servers[serverId];
    if (!srv?.connected) return;
    setActiveServer(serverId);
    setToolsModal({ open: true, serverId, serverName: srv.name, tools: [], phase: "confirm" });
  };

  const handleToolsConfirm = async () => {
    setToolsModal((prev) => ({ ...prev, phase: "loading" }));
    try {
      const res = await fetch(`${API}/api/servers/${toolsModal.serverId}/tools`);
      const data = await res.json();
      setToolsModal((prev) => ({ ...prev, tools: data.tools || [], phase: "list" }));
    } catch {
      setToolsModal((prev) => ({ ...prev, tools: [], phase: "list" }));
    }
  };

  const closeToolsModal = () => setToolsModal({ open: false, serverId: null, serverName: "", tools: [], phase: "confirm" });

  /* ── Render ─────────────────────────────────────────────────────────────── */
  const connectedCount = Object.values(servers).filter((s) => s.connected).length;
  const serverList = Object.entries(servers);

  return (
    <div className="app">
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className={`sidebar ${sidebarOpen ? "open" : "closed"}`}>
        <div className="sidebar-header">
          <div className="logo">
            <span className="logo-icon">⚡</span>
            <span className="logo-text">Unified MCP</span>
          </div>
          <span className="header-badge">{connectedCount}/{serverList.length}</span>
        </div>

        <div className="server-list">
          <div className="section-label">Services</div>
          {serverList.map(([id, srv]) => {
            const isConnecting = connectingServer === id || srv.connecting;
            const isConnected = srv.connected;

            return (
              <div
                key={id}
                className={`server-card ${isConnected ? "connected" : ""}`}
                onClick={() => isConnected && handleServerCardClick(id)}
              >
                <div className="server-card-left">
                  <div className="server-icon" style={{ color: SERVER_COLORS[id] || "#888" }}>
                    {Icons[id] || Icons.notion}
                  </div>
                  <div className="server-info">
                    <span className="server-name">{srv.name}</span>
                    {isConnected ? (
                      <span className="server-status connected-status">{srv.toolCount} tools</span>
                    ) : isConnecting ? (
                      <span className="server-status connecting-status">Connecting…</span>
                    ) : (
                      <span className="server-status">Not connected</span>
                    )}
                  </div>
                </div>
                <div className="server-card-right">
                  {isConnected ? (
                    <>
                      <span className="status-indicator online">{Icons.check}</span>
                      <button
                        className="btn-sm btn-disconnect"
                        onClick={(e) => { e.stopPropagation(); handleDisconnect(id); }}
                      >✕</button>
                    </>
                  ) : (
                    <button
                      className="btn-sm btn-connect"
                      disabled={isConnecting}
                      onClick={(e) => { e.stopPropagation(); handleConnect(id); }}
                    >
                      {isConnecting ? (
                        <span className="btn-spinner" />
                      ) : (
                        <>
                          {Icons.link}
                          <span>{srv.connect_label || "Connect"}</span>
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="chat-history">
          <div className="section-label">
            History
            <button className="btn-icon" onClick={handleNewChat} title="New Chat">{Icons.plus}</button>
          </div>
          <div className="chat-list">
            {chats.map((c) => (
              <div
                key={c.id}
                className={`chat-item ${activeChatId === c.id ? "active" : ""}`}
                onClick={() => handleLoadChat(c.id)}
              >
                <span className="chat-item-title">{c.title}</span>
                <button className="btn-icon btn-delete" onClick={(e) => handleDeleteChat(c.id, e)}>
                  {Icons.trash}
                </button>
              </div>
            ))}
            {chats.length === 0 && <div className="empty-chats">No conversations yet</div>}
          </div>
        </div>
      </aside>

      {/* ── Main ────────────────────────────────────────────────────────── */}
      <main className="main">
        <header className="topbar">
          <button className="btn-icon sidebar-toggle" onClick={() => setSidebarOpen((p) => !p)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20">
              <path d="M3 12h18M3 6h18M3 18h18" />
            </svg>
          </button>
          <div className="topbar-title">
            <span>Multi-Server Orchestration</span>
            <span style={{ fontSize: "0.85em", color: "#888", marginLeft: "8px" }}>
              ({Object.values(servers).filter(s => s.connected).length} connected)
            </span>
          </div>
        </header>

        <div className="chat-viewport">
          {messages.length === 0 && (
            <div className="empty-state">
              <div className="empty-icon">⚡</div>
              <h2>Unified MCP Platform</h2>
              <p>Connect your services and start chatting.</p>
              <div className="suggestion-grid">
                {[
                  { server: "github", text: "List my repositories" },
                  { server: "zomato", text: "Find restaurants nearby" },
                  { server: "notion", text: "Search my Notion pages" },
                  { server: "figma", text: "Get my Figma files" },
                  { server: "hubspot", text: "Show my open HubSpot deals" },
                ].map((s, i) => (
                  <button
                    key={i}
                    className="suggestion-tile"
                    style={{ borderColor: SERVER_COLORS[s.server] + "33" }}
                    onClick={() => {
                      if (servers[s.server]?.connected) {
                        setActiveServer(s.server);
                        setInput(s.text);
                        inputRef.current?.focus();
                      } else {
                        handleConnect(s.server);
                      }
                    }}
                  >
                    <span className="suggestion-icon" style={{ color: SERVER_COLORS[s.server] }}>
                      {Icons[s.server]}
                    </span>
                    <span>{s.text}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              {msg.role === "assistant" && (
                <div
                  className="message-avatar"
                  style={{
                    background: "#a259ff",
                    color: "#fff",
                  }}
                >
                  🤖
                </div>
              )}
              <div className="message-body">
                {msg.role === "user" ? (
                  <div className="message-content user-content">{msg.content}</div>
                ) : (
                  <>
                    <div className="message-content" dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />

                    {msg.toolCalls && msg.toolCalls.length > 0 && (
                      <details className="execution-results-details" style={{ marginTop: "8px" }}>
                        <summary style={{ cursor: "pointer", color: "#888", fontSize: "0.9em" }}>
                          ⚙️ Tools used ({msg.toolCalls.length})
                        </summary>
                        <div style={{ marginTop: "8px", paddingLeft: "12px", borderLeft: "2px solid #444" }}>
                          {msg.toolCalls.map((tc, i) => (
                            <div key={i} style={{ fontSize: "0.85em", marginBottom: "6px" }}>
                              <strong>{tc.server || "unknown"}</strong> → <code>{tc.tool}</code>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="message assistant">
              <div className="message-avatar thinking"><div className="dot-pulse" /></div>
              <div className="message-body"><div className="thinking-text">Thinking…</div></div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="composer-container">
          {showSlashMenu && filteredServers.length > 0 && (
            <div className="slash-menu">
              <div className="slash-menu-header">Switch Service</div>
              {filteredServers.map(([id, srv], idx) => (
                <div
                  key={id}
                  className={`slash-item ${idx === slashIndex ? "selected" : ""}`}
                  onClick={() => selectSlashServer(id)}
                  onMouseEnter={() => setSlashIndex(idx)}
                >
                  <span className="slash-icon" style={{ color: SERVER_COLORS[id] || "#888" }}>
                    {Icons[id]}
                  </span>
                  <div className="slash-info">
                    <span className="slash-name">/{id}</span>
                    <span className="slash-desc">{srv.name}</span>
                  </div>
                  {srv.connected && <span className="slash-status connected">Connected</span>}
                </div>
              ))}
            </div>
          )}

          <div className="composer">
            <textarea
              ref={inputRef}
              className="composer-input"
              placeholder="Ask anything across all services (e.g., 'Create a GitHub repo and find Joe in HubSpot')…"
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              rows={1}
              onInput={(e) => {
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
              }}
            />
            <button className="btn-send" onClick={sendMessage} disabled={loading || !input.trim()}>
              {Icons.send}
            </button>
          </div>
        </div>
      </main>
      {/* ── Tools Modal ────────────────────────────────────────────── */}
      {toolsModal.open && (
        <div className="modal-overlay" onClick={closeToolsModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-icon" style={{ color: SERVER_COLORS[toolsModal.serverId] || "#888" }}>
                {Icons[toolsModal.serverId]}
              </span>
              <h3>{toolsModal.serverName}</h3>
              <button className="btn-icon modal-close" onClick={closeToolsModal}>✕</button>
            </div>

            {toolsModal.phase === "confirm" && (
              <div className="modal-body">
                <p className="modal-question">View the list of available tools?</p>
                <div className="modal-actions">
                  <button className="modal-btn modal-btn-secondary" onClick={closeToolsModal}>No</button>
                  <button className="modal-btn modal-btn-primary" onClick={handleToolsConfirm}>Yes</button>
                </div>
              </div>
            )}

            {toolsModal.phase === "loading" && (
              <div className="modal-body">
                <div className="modal-loading"><span className="btn-spinner" /> Loading tools…</div>
              </div>
            )}

            {toolsModal.phase === "list" && (
              <div className="modal-body">
                <div className="modal-tool-count">{toolsModal.tools.length} tools available</div>
                <div className="modal-tool-list">
                  {toolsModal.tools.map((t, i) => (
                    <div key={i} className="modal-tool-item">
                      <span className="tool-name">⚙ {t.name}</span>
                      {t.description && <span className="tool-desc">{t.description}</span>}
                    </div>
                  ))}
                  {toolsModal.tools.length === 0 && <div className="empty-chats">No tools found</div>}
                </div>
                <div className="modal-actions">
                  <button className="modal-btn modal-btn-primary" onClick={closeToolsModal}>Close</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
