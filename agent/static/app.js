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
  const themeSelect   = document.getElementById("theme-select");
  const reasoningCheckbox = document.getElementById("reasoning-checkbox");
  const EMPTY_STATE_HTML = '<div class="empty-icon"><img src="/static/icon.svg" width="48" height="48" alt="Agent Lab Icon" /></div><p class="empty-title">How can I help?</p><p class="empty-sub">Start a conversation below.</p><div class="starter-prompts"><button class="btn btn--starter" type="button">Summarize a document</button><button class="btn btn--starter" type="button">Write a Python script</button><button class="btn btn--starter" type="button">Explain neural networks</button></div>';
  const THEME_KEY = "agentlab_theme";

  /* ── State ────────────────────────────────────────────────────────────── */
  let ws             = null;
  let reconnectDelay = 1000;   // ms, doubles on each failure (max 30 s)
  let isStreaming    = false;
  let stopped        = false;  // user hit Stop
  let activeBubble   = null;   // the agent bubble currently receiving tokens
  let reasoningBuffer = "";    // accumulates reasoning chunks for the active turn
  let activeReasoningBox    = null;  // per-turn reasoning container element
  let activeReasoningBody   = null;  // per-turn reasoning text element
  let activeReasoningToggle = null;  // per-turn toggle button
  let firstMainToken = false;        // used to auto-collapse reasoning on first token
  let followStreaming = true;        // true when transcript should stay pinned to latest output
  let scrollRafPending = false;
  let streamingResizeObserver = null;

  const SCROLL_FOLLOW_THRESHOLD = 48;

  /* ── Markdown rendering ───────────────────────────────────────────────── */
  marked.use({ breaks: true, gfm: true });

  function renderMarkdown(text) {
    if (!text) return "";

    // Replace $$...$$ (display) and $...$ (inline) with Markdown-safe temporary placeholders.
    const mathBlocks = [];

    // 1. Extract Display Math ($$ ... $$)
    let processedText = text.replace(/\$\$([\s\S]+?)\$\$/g, (match, formula) => {
      const id = `MATHDISP${mathBlocks.length}`;
      mathBlocks.push({ id, formula, displayMode: true });
      return id;
    });

    // 2. Extract Inline Math ($ ... $) - non-greedy, doesn't cross lines
    processedText = processedText.replace(/\$([^\$\n]+?)\$/g, (match, formula) => {
      const id = `MATHINL${mathBlocks.length}`;
      mathBlocks.push({ id, formula, displayMode: false });
      return id;
    });

    let html = marked.parse(processedText);

    // Restore math blocks and render with KaTeX
    if (typeof katex !== "undefined") {
      mathBlocks.forEach(block => {
        try {
          const rendered = katex.renderToString(block.formula, { 
            displayMode: block.displayMode, 
            throwOnError: false,
            trust: true 
          });
          // Use a split/join to replace all occurrences if needed, though id is unique
          html = html.split(block.id).join(rendered);
        } catch (e) {
          console.error("KaTeX error:", e);
        }
      });
    }

    return typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(html) : html;
  }

  function postProcessMarkdown(bubble) {
    const pres = bubble.querySelectorAll("pre");
    pres.forEach(pre => {
      // Avoid processing twice just in case
      if (pre.parentNode.classList.contains("code-container")) return;

      const codeElem = pre.querySelector("code");
      if (codeElem && typeof hljs !== "undefined") {
        hljs.highlightElement(codeElem);
      }

      const container = document.createElement("div");
      container.className = "code-container";

      const btn = document.createElement("button");
      btn.className = "btn--copy-code";
      btn.textContent = "Copy";
      btn.setAttribute("aria-label", "Copy code");
      btn.addEventListener("click", () => {
        const text = codeElem ? codeElem.textContent : pre.textContent;
        navigator.clipboard.writeText(text).then(() => {
          btn.textContent = "Copied!";
          setTimeout(() => btn.textContent = "Copy", 2000);
        }).catch(() => {
          btn.textContent = "Failed";
          setTimeout(() => btn.textContent = "Copy", 2000);
        });
      });

      pre.parentNode.insertBefore(container, pre);
      container.appendChild(pre);
      container.appendChild(btn);
    });
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
        } else if (ev.content === "compacting") {
          showCompactingBanner();
        } else if (ev.content === "thinking") {
          hideCompactingBanner();
          setStatus("thinking");
          reasoningBuffer = "";
          firstMainToken = true;
          followStreaming = isNearBottom();
          activeBubble = appendAgentBubble("");
          activeBubble.querySelector(".bubble").classList.add("bubble--streaming");
          activeReasoningBox    = activeBubble._reasoningBox;
          activeReasoningBody   = activeBubble._reasoningBody;
          activeReasoningToggle = activeBubble._reasoningToggle;
          connectStreamingResizeObserver();
          maybeScrollDown(true);
        }
        break;

      case "reasoning":
        reasoningBuffer += ev.content;
        if (activeReasoningBody) {
          activeReasoningBody.textContent = reasoningBuffer;
          activeReasoningBody.scrollTop = activeReasoningBody.scrollHeight;
        }
        if (activeReasoningBox) {
          activeReasoningBox.classList.add("reasoning-inline--visible");
        }
        if (activeReasoningToggle) {
          activeReasoningToggle.setAttribute("aria-expanded", "true");
        }
        maybeScrollDown();
        break;

      case "token":
        if (stopped) break;
        // Auto-collapse reasoning box when the main answer starts arriving
        if (firstMainToken) {
          if (activeReasoningToggle) {
            activeReasoningToggle.setAttribute("aria-expanded", "false");
          }
          firstMainToken = false;
        }
        if (activeBubble) {
          const bubble = activeBubble.querySelector(".bubble");
          bubble.textContent += ev.content;
          maybeScrollDown();
        }
        break;

      case "tool_call": {
        if (!activeBubble) break;
        // Auto-collapse reasoning box when tool is invoked (same as first token)
        if (firstMainToken) {
          if (activeReasoningToggle) {
            activeReasoningToggle.setAttribute("aria-expanded", "false");
          }
          firstMainToken = false;
        }
        const pill = buildToolCallPill(ev);
        // Insert between the reasoning box and the bubble div
        const bubbleDiv = activeBubble.querySelector(".bubble");
        activeBubble.insertBefore(pill, bubbleDiv);
        maybeScrollDown();
        break;
      }

      case "board":
        renderBoard(ev.content);
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
    followStreaming = true;
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
    disconnectStreamingResizeObserver();
    if (activeBubble) {
      const bubble = activeBubble.querySelector(".bubble");
      bubble.classList.remove("bubble--streaming");
      const partialText = bubble.textContent;
      if (partialText) {
        bubble.innerHTML = renderMarkdown(partialText);
        postProcessMarkdown(bubble);
        activeBubble.dataset.md = partialText;
        maybeScrollDown();
      }
    }
    if (activeReasoningToggle) {
      activeReasoningToggle.setAttribute("aria-expanded", "false");
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
    disconnectStreamingResizeObserver();
    hideCompactingBanner();
    setStatus("connected");

    if (activeBubble) {
      const bubble = activeBubble.querySelector(".bubble");
      bubble.classList.remove("bubble--streaming");
      if (errorMsg) {
        bubble.textContent = errorMsg;
        bubble.classList.add("bubble--error");
      } else if (finalText !== null && finalText !== undefined) {
        bubble.innerHTML = renderMarkdown(finalText);
        postProcessMarkdown(bubble);
        activeBubble.dataset.md = finalText;
      }
      activeBubble = null;
    }

    // Collapse reasoning box if it's still open (no main tokens arrived)
    if (activeReasoningToggle && activeReasoningToggle.getAttribute("aria-expanded") === "true") {
      activeReasoningToggle.setAttribute("aria-expanded", "false");
    }
    activeReasoningBox    = null;
    activeReasoningBody   = null;
    activeReasoningToggle = null;
    firstMainToken        = false;

    setInputEnabled(true);
    saveHistory();

    // Use a direct RAF instead of maybeScrollDown() to bypass the scrollRafPending
    // guard. When the server responds without reasoning (fast path), the thinking-phase
    // RAF is still queued (scrollRafPending=true), which silently blocks the
    // maybeScrollDown() call here, leaving the transcript un-scrolled.
    if (followStreaming) {
      requestAnimationFrame(() => {
        const container = getScrollContainer();
        container.scrollTop = container.scrollHeight;
      });
    }
  }

  /* ── UI helpers ───────────────────────────────────────────────────────── */
  function setStatus(s) {
    statusDot.className = `status-dot status-dot--${s}`;
    statusDot.title = { connected: "Connected", disconnected: "Disconnected",
      thinking: "Thinking…", compacting: "Compacting conversation…", error: "Error" }[s] || s;
  }

  let _compactingBanner = null;

  function showCompactingBanner() {
    if (_compactingBanner) return;
    _compactingBanner = document.createElement("div");
    _compactingBanner.className = "compacting-banner";
    _compactingBanner.textContent = "Compacting conversation…";
    transcript.appendChild(_compactingBanner);
    maybeScrollDown(true);
  }

  function hideCompactingBanner() {
    if (_compactingBanner) {
      _compactingBanner.remove();
      _compactingBanner = null;
    }
  }

  function setProviderBadge(provider, model) {
    const label = model ? `${provider} · ${model}` : (provider || "—");
    providerBadge.textContent = label;
    providerBadge.className   = `badge ${provider === "openai" ? "badge--blue" : "badge--neutral"}`;
  }

  function applyTheme(theme) {
    const resolved = ["auto", "light", "dark"].includes(theme) ? theme : "auto";
    document.documentElement.setAttribute("data-theme", resolved);
  }

  function initThemePreference() {
    let saved = "auto";
    try {
      saved = localStorage.getItem(THEME_KEY) || "auto";
    } catch {
      saved = "auto";
    }
    applyTheme(saved);
    if (themeSelect) {
      themeSelect.value = ["auto", "light", "dark"].includes(saved) ? saved : "auto";
    }
  }

  function bindThemeSelector() {
    if (!themeSelect) return;
    themeSelect.addEventListener("change", () => {
      const value = themeSelect.value;
      applyTheme(value);
      try {
        localStorage.setItem(THEME_KEY, value);
      } catch {
        // Ignore storage failures in restrictive environments.
      }
    });
  }

  function setInputEnabled(enabled) {
    userInput.disabled = !enabled;
    sendBtn.disabled   = !enabled;
    stopBtn.hidden     = enabled;
    if (enabled) userInput.focus();
  }

  function distanceFromBottom() {
    const container = getScrollContainer();
    return container.scrollHeight - (container.scrollTop + container.clientHeight);
  }

  function getScrollContainer() {
    // In some layouts the page is the scroll container, not the transcript.
    if (transcript.scrollHeight > transcript.clientHeight + 1) {
      return transcript;
    }
    return document.scrollingElement || document.documentElement;
  }

  function isNearBottom() {
    return distanceFromBottom() <= SCROLL_FOLLOW_THRESHOLD;
  }

  function scrollToLatest(force = false) {
    if (!(force || followStreaming)) return;

    // Keep the active streaming bubble anchored in-view.
    if (isStreaming && activeBubble) {
      const tRect = transcript.getBoundingClientRect();
      const bRect = activeBubble.getBoundingClientRect();
      if (force || bRect.bottom > (tRect.bottom - 8)) {
        activeBubble.scrollIntoView({ block: "end", inline: "nearest" });
      }
    }

    const container = getScrollContainer();
    container.scrollTop = container.scrollHeight;
  }

  function maybeScrollDown(force = false) {
    if (!(force || followStreaming)) return;
    if (scrollRafPending) return;
    scrollRafPending = true;
    requestAnimationFrame(() => {
      scrollRafPending = false;
      scrollToLatest(force);
    });
  }

  function disconnectStreamingResizeObserver() {
    if (streamingResizeObserver) {
      streamingResizeObserver.disconnect();
      streamingResizeObserver = null;
    }
  }

  function connectStreamingResizeObserver() {
    disconnectStreamingResizeObserver();
    if (typeof ResizeObserver === "undefined") return;

    streamingResizeObserver = new ResizeObserver(() => {
      maybeScrollDown();
    });

    streamingResizeObserver.observe(transcript);
    if (activeBubble) {
      streamingResizeObserver.observe(activeBubble);
    }
  }

  function hideEmptyState() {
    if (emptyState && emptyState.parentNode) {
      emptyState.parentNode.removeChild(emptyState);
    }
  }

  function appendUserBubble(text) {
    const wrapper = document.createElement("div");
    wrapper.className = "message message--user";
    wrapper.dataset.role = "user";
    wrapper.dataset.text = text;

    const lbl = document.createElement("div");
    lbl.className = "message-label";
    lbl.textContent = "You";

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;

    wrapper.appendChild(lbl);
    wrapper.appendChild(bubble);
    transcript.appendChild(wrapper);
    maybeScrollDown();
    return wrapper;
  }

  function appendAgentBubble(text) {
    const wrapper = document.createElement("div");
    wrapper.className = "message message--agent";
    wrapper.dataset.role = "agent";
    wrapper.dataset.text = text;

    const lbl = document.createElement("div");
    lbl.className = "message-label";
    lbl.textContent = "Agent";

    // Inline reasoning box (hidden until reasoning arrives)
    const reasoningBox = document.createElement("div");
    reasoningBox.className = "reasoning-inline";

    const toggleBtn = document.createElement("button");
    toggleBtn.className = "reasoning-inline-toggle";
    toggleBtn.setAttribute("aria-expanded", "false");

    const toggleLabel = document.createElement("span");
    toggleLabel.className = "reasoning-inline-label";
    toggleLabel.textContent = "Reasoning";

    const chevron = document.createElement("span");
    chevron.className = "reasoning-inline-chevron";
    chevron.textContent = "›";

    toggleBtn.appendChild(toggleLabel);
    toggleBtn.appendChild(chevron);

    const body = document.createElement("div");
    body.className = "reasoning-inline-body";

    reasoningBox.appendChild(toggleBtn);
    reasoningBox.appendChild(body);

    toggleBtn.addEventListener("click", () => {
      const open = toggleBtn.getAttribute("aria-expanded") === "true";
      toggleBtn.setAttribute("aria-expanded", String(!open));
    });

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;

    wrapper.appendChild(lbl);
    wrapper.appendChild(reasoningBox);
    wrapper.appendChild(bubble);

    // Attach refs for easy access from streaming handlers
    wrapper._reasoningBox    = reasoningBox;
    wrapper._reasoningBody   = body;
    wrapper._reasoningToggle = toggleBtn;

    transcript.appendChild(wrapper);
    maybeScrollDown();
    return wrapper;
  }

  function handleUserScroll() {
    if (isStreaming) {
      followStreaming = isNearBottom();
    } else if (isNearBottom()) {
      followStreaming = true;
    }
  }

  transcript.addEventListener("scroll", handleUserScroll);
  window.addEventListener("scroll", handleUserScroll, { passive: true });

  /* Textarea auto-resize */
  function resizeTextarea() {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 160) + "px";
  }
  userInput.addEventListener("input", resizeTextarea);

  /* ── Tool call pill builder ────────────────────────────────────────────── */
  const TOOL_DISPLAY_NAMES = {
    search_knowledge_base: "Knowledge Base",
  };

  function buildToolCallPill(ev) {
    const toolName = (ev.metadata && ev.metadata.tool) || "tool";
    const query    = ev.content || "";
    const docs     = (ev.metadata && ev.metadata.docs) || [];
    const label    = TOOL_DISPLAY_NAMES[toolName] || toolName;

    const pill = document.createElement("div");
    pill.className = "tool-call-pill";

    const header = document.createElement("span");
    header.className = "tool-call-pill__header";
    header.textContent = `🔍 Searched ${label}: "${query}"`;
    pill.appendChild(header);

    if (docs.length > 0) {
      const badgeRow = document.createElement("div");
      badgeRow.className = "tool-call-pill__docs";
      docs.forEach((doc) => {
        const badge = document.createElement("span");
        badge.className = "tool-call-pill__doc";
        badge.textContent = doc.title || "Document";
        badgeRow.appendChild(badge);
      });
      pill.appendChild(badgeRow);
    }

    return pill;
  }
  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  sendBtn.addEventListener("click", sendMessage);
  stopBtn.addEventListener("click", sendStop);
  clearBtn.addEventListener("click", sendClear);

  /* ── Board panel ──────────────────────────────────────────────────────── */
  const boardPanel    = document.getElementById("board-panel");
  const boardFrame    = document.getElementById("board-frame");
  const boardCloseBtn = document.getElementById("board-close-btn");

  function renderBoard(html) {
    // Build a self-contained srcdoc page that pre-loads Chart.js via <base>
    // so relative /static/ URLs resolve against the parent page's origin.
    const base = window.location.origin;
    boardFrame.srcdoc = [
      "<!DOCTYPE html><html><head>",
      `<base href="${base}">`,
      '<script src="/static/vendor/chart.min.js"><\/script>',
      "<style>",
      "  body{margin:16px;font-family:system-ui,sans-serif;color:#111;font-size:14px;line-height:1.5}",
      "  table{border-collapse:collapse;width:100%;margin:.5em 0}",
      "  th,td{border:1px solid #ddd;padding:7px 11px;text-align:left}",
      "  th{background:#f5f5f5;font-weight:600}",
      "  tr:nth-child(even){background:#fafafa}",
      "  .chart-wrap{position:relative;height:260px;margin:.5em 0}",
      "  h1,h2,h3{margin:.6em 0 .3em;font-weight:600}",
      "  h2{font-size:1em} h3{font-size:.95em;color:#444}",
      "  .kpi{display:inline-block;margin:4px 8px 4px 0;padding:10px 16px;",
      "       background:#f0f4ff;border-radius:8px;min-width:120px}",
      "  .kpi-label{font-size:.78em;color:#666;margin-bottom:2px}",
      "  .kpi-value{font-size:1.5em;font-weight:700;color:#1a56db}",
      "</style></head><body>",
      html,
      "</body></html>",
    ].join("");
    boardPanel.hidden = false;
    maybeScrollDown();
  }

  boardCloseBtn.addEventListener("click", () => {
    boardPanel.hidden = true;
  });

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
        postProcessMarkdown(bubble);
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
      es.innerHTML = EMPTY_STATE_HTML;
      transcript.appendChild(es);
    }
    sessionStorage.removeItem(HISTORY_KEY);
    followStreaming = true;
    disconnectStreamingResizeObserver();
  }

  /* ── Heartbeat (keep-alive ping every 25 s) ───────────────────────────── */
  setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "ping" }));
    }
  }, 25_000);

  /* ── Starter Prompts ──────────────────────────────────────────────────── */
  document.addEventListener("click", (e) => {
    if (e.target.matches(".btn--starter")) {
      userInput.value = e.target.textContent;
      resizeTextarea();
      sendMessage();
    }
  });

  /* ── Boot ─────────────────────────────────────────────────────────────── */
  initThemePreference();
  bindThemeSelector();
  connect();
})();
