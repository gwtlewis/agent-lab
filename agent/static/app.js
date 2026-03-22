/**
 * Agent Lab – WebSocket chat client
 *
 * Responsibilities:
 *   - Connect to the WebSocket server at /ws
 *   - Render streamed events (status / reasoning / token / final / error)
 *   - Handle user input (send, stop, clear, Enter/Shift+Enter)
 *   - Auto-resize textarea; auto-scroll transcript (unless user scrolled up)
 *   - Reconnect automatically on disconnect (exponential back-off)
 *   - Persist conversation history in sessionStorage across soft refreshes
 */

(function () {
  "use strict";

  /* ── DOM refs ─────────────────────────────────────────────────────────── */
  const transcript    = document.getElementById("transcript");
  const emptyState    = document.getElementById("empty-state");
  const userInput     = document.getElementById("user-input");
  const sendBtn       = document.getElementById("send-btn");
  const stopBtn       = document.getElementById("stop-btn");
  const clearBtn      = document.getElementById("clear-btn");
  const statusDot     = document.getElementById("status-dot");
  const providerBadge = document.getElementById("provider-badge");
  const reasoningPanel = document.getElementById("reasoning-panel");
  const reasoningToggle = document.getElementById("reasoning-toggle");
  const reasoningBody  = document.getElementById("reasoning-body");
  const reasoningCheckbox = document.getElementById("reasoning-checkbox");

  /* ── State ────────────────────────────────────────────────────────────── */
  let ws             = null;
  let reconnectDelay = 1000;   // ms, doubles on each failure (max 30 s)
  let isStreaming    = false;
  let stopped        = false;  // user hit Stop
  let activeBubble   = null;   // the agent bubble currently receiving tokens
  let reasoningBuffer = "";    // accumulates reasoning chunks

  /* ── Markdown rendering ───────────────────────────────────────────────── */
  marked.use({ breaks: true, gfm: true });

  function renderMarkdown(text) {
    if (!text) return "";
    const html = marked.parse(text);
    return typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(html) : html;
  }

  /* ── WebSocket connection ─────────────────────────────────────────────── */
  function connect() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws`);

    ws.addEventListener("open", () => {
      reconnectDelay = 1000;
      setStatus("connected");
    });

    ws.addEventListener("message", (ev) => {
      let event;
      try { event = JSON.parse(ev.data); }
      catch { console.error("Bad JSON from server:", ev.data); return; }
      handleEvent(event);
    });

    ws.addEventListener("close", () => {
      setStatus("disconnected");
      if (isStreaming) { endStream(null); }
      scheduleReconnect();
    });

    ws.addEventListener("error", () => {
      setStatus("error");
    });
  }

  function scheduleReconnect() {
    setTimeout(() => { connect(); }, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 30_000);
  }

  /* ── Event dispatch ───────────────────────────────────────────────────── */
  function handleEvent(ev) {
    switch (ev.type) {
      case "status":
        if (ev.content === "connected") {
          const meta = ev.metadata || {};
          setProviderBadge(meta.provider, meta.model);
          setStatus("connected");
          restoreHistory();
        } else if (ev.content === "thinking") {
          setStatus("thinking");
          reasoningBuffer = "";
          activeBubble = appendAgentBubble("");
          activeBubble.querySelector(".bubble").classList.add("bubble--streaming");
          reasoningBody.textContent = "";
        }
        break;

      case "reasoning":
        reasoningBuffer += ev.content;
        reasoningBody.textContent = reasoningBuffer;
        reasoningBody.scrollTop = reasoningBody.scrollHeight;
        showReasoningPanel();
        break;

      case "token":
        if (stopped) break;
        if (activeBubble) {
          const bubble = activeBubble.querySelector(".bubble");
          bubble.textContent += ev.content;
          maybeScrollDown();
        }
        break;

      case "final":
        endStream(ev.content);
        break;

      case "error":
        endStream(null, ev.content);
        break;

      case "pong":
        // heartbeat ack – no UI action needed
        break;

      case "cleared":
        clearTranscript();
        break;

      default:
        console.warn("Unknown event type:", ev.type);
    }
  }

  /* ── Sending messages ─────────────────────────────────────────────────── */
  function sendMessage() {
    const text = userInput.value.trim();
    if (!text || isStreaming || !ws || ws.readyState !== WebSocket.OPEN) return;

    hideEmptyState();
    appendUserBubble(text);
    isStreaming = true;
    stopped = false;
    setInputEnabled(false);

    ws.send(JSON.stringify({
      type:             "message",
      content:          text,
      enable_reasoning: reasoningCheckbox.checked,
    }));

    userInput.value = "";
    resizeTextarea();
    saveHistory();
  }

  function sendStop() {
    stopped = true;
    isStreaming = false;
    if (activeBubble) {
      const bubble = activeBubble.querySelector(".bubble");
      bubble.classList.remove("bubble--streaming");
      const partialText = bubble.textContent;
      if (partialText) {
        bubble.innerHTML = renderMarkdown(partialText);
        activeBubble.dataset.md = partialText;
      }
    }
    setInputEnabled(true);
    setStatus("connected");
  }

  function sendClear() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: "clear" }));
  }

  /* ── Stream lifecycle ─────────────────────────────────────────────────── */
  function endStream(finalText, errorMsg) {
    isStreaming = false;
    setStatus("connected");

    if (activeBubble) {
      const bubble = activeBubble.querySelector(".bubble");
      bubble.classList.remove("bubble--streaming");
      if (errorMsg) {
        bubble.textContent = errorMsg;
        bubble.classList.add("bubble--error");
      } else if (finalText !== null && finalText !== undefined) {
        bubble.innerHTML = renderMarkdown(finalText);
        activeBubble.dataset.md = finalText;
      }
      activeBubble = null;
    }

    if (!reasoningBuffer) {
      hideReasoningPanel();
    }

    setInputEnabled(true);
    saveHistory();
    maybeScrollDown();
  }

  /* ── UI helpers ───────────────────────────────────────────────────────── */
  function setStatus(s) {
    statusDot.className = `status-dot status-dot--${s}`;
    statusDot.title = { connected: "Connected", disconnected: "Disconnected",
      thinking: "Thinking…", error: "Error" }[s] || s;
  }

  function setProviderBadge(provider, model) {
    const label = model ? `${provider} · ${model}` : (provider || "—");
    providerBadge.textContent = label;
    providerBadge.className   = `badge ${provider === "openai" ? "badge--blue" : "badge--neutral"}`;
  }

  function setInputEnabled(enabled) {
    userInput.disabled = !enabled;
    sendBtn.disabled   = !enabled;
    stopBtn.hidden     = enabled;
    if (enabled) userInput.focus();
  }

  function hideEmptyState() {
    if (emptyState && emptyState.parentNode) {
      emptyState.parentNode.removeChild(emptyState);
    }
  }

  function appendUserBubble(text) {
    const msg = makeBubble("user", "You", text);
    transcript.appendChild(msg);
    maybeScrollDown();
    return msg;
  }

  function appendAgentBubble(text) {
    const msg = makeBubble("agent", "Agent", text);
    transcript.appendChild(msg);
    maybeScrollDown();
    return msg;
  }

  function makeBubble(role, label, text) {
    const wrapper = document.createElement("div");
    wrapper.className = `message message--${role}`;
    wrapper.dataset.role = role;
    wrapper.dataset.text = text;

    const lbl = document.createElement("div");
    lbl.className = "message-label";
    lbl.textContent = label;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;

    wrapper.appendChild(lbl);
    wrapper.appendChild(bubble);
    return wrapper;
  }

  /* Reasoning panel */
  function showReasoningPanel() {
    reasoningPanel.classList.remove("reasoning-panel--hidden");
  }

  function hideReasoningPanel() {
    reasoningPanel.classList.add("reasoning-panel--hidden");
  }

  reasoningToggle.addEventListener("click", () => {
    const open = reasoningToggle.getAttribute("aria-expanded") === "true";
    reasoningToggle.setAttribute("aria-expanded", String(!open));
    reasoningBody.classList.toggle("reasoning-body--open", !open);
  });

  /* Auto-scroll: only if the user hasn't scrolled up manually */
  let userScrolled = false;
  transcript.addEventListener("scroll", () => {
    const atBottom = transcript.scrollTop + transcript.clientHeight >= transcript.scrollHeight - 20;
    userScrolled = !atBottom;
  });

  function maybeScrollDown() {
    if (!userScrolled) {
      transcript.scrollTop = transcript.scrollHeight;
    }
  }

  /* Textarea auto-resize */
  function resizeTextarea() {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 160) + "px";
  }
  userInput.addEventListener("input", resizeTextarea);

  /* ── Keyboard & button handlers ───────────────────────────────────────── */
  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  sendBtn.addEventListener("click", sendMessage);
  stopBtn.addEventListener("click", sendStop);
  clearBtn.addEventListener("click", sendClear);

  /* ── Session history (sessionStorage) ────────────────────────────────── */
  const HISTORY_KEY = "agentlab_history";

  function saveHistory() {
    const messages = [...transcript.querySelectorAll(".message")].map(m => ({
      role: m.dataset.role,
      // Prefer the original markdown source; fall back to visible text for user bubbles.
      text: m.dataset.md || m.querySelector(".bubble").textContent,
    }));
    try { sessionStorage.setItem(HISTORY_KEY, JSON.stringify(messages)); }
    catch { /* quota exceeded — skip */ }
  }

  function restoreHistory() {
    let messages;
    try { messages = JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "[]"); }
    catch { messages = []; }

    if (!messages.length) return;

    hideEmptyState();
    messages.forEach(m => {
      if (m.role === "user") {
        appendUserBubble(m.text);
      } else {
        const msg = appendAgentBubble("");
        const bubble = msg.querySelector(".bubble");
        bubble.innerHTML = renderMarkdown(m.text);
        msg.dataset.md = m.text;
      }
    });
  }

  function clearTranscript() {
    // Remove all messages from DOM
    [...transcript.querySelectorAll(".message")].forEach(m => m.remove());
    // Put empty state back
    if (!document.getElementById("empty-state")) {
      const es = document.createElement("div");
      es.className = "transcript-empty";
      es.id = "empty-state";
      es.innerHTML = '<div class="empty-icon">◎</div><p class="empty-title">How can I help?</p><p class="empty-sub">Start a conversation below.</p>';
      transcript.appendChild(es);
    }
    sessionStorage.removeItem(HISTORY_KEY);
    hideReasoningPanel();
    userScrolled = false;
  }

  /* ── Heartbeat (keep-alive ping every 25 s) ───────────────────────────── */
  setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "ping" }));
    }
  }, 25_000);

  /* ── Boot ─────────────────────────────────────────────────────────────── */
  connect();
})();
