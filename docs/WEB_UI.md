# Agent Lab – Web UI

**Last Updated**: 2026-03-22

A browser-based chat interface that connects to the LangChain agent over WebSocket.  
Features real-time token streaming, model reasoning display, and full Markdown rendering.

---

## Quick Start

```bash
# From the repo root — one command does everything
./start.sh
```

Open **http://127.0.0.1:8000** in your browser.

> `start.sh` auto-detects the local `.venv`, reads `WEB_PORT` from `agent/.env`,
> starts uvicorn, and prints the full set of URLs.

---

## Configuration

| Variable | File | Default | Description |
|---|---|---|---|
| `WEB_PORT` | `agent/.env` | `8000` | HTTP/WebSocket port |
| `LLM_PROVIDER` | `agent/.env` | `ollama` | `ollama` or `openai` |
| `OLLAMA_HOST` | `agent/.env` | `http://127.0.0.1:11434` | Ollama base URL |
| `OLLAMA_MODEL` | `agent/.env` | `qwen3:8b` | Model to use |

---

## Features

### Streaming chat
Tokens stream into the agent bubble character-by-character as the model generates them.  
A blinking cursor (`▍`) shows while the stream is in progress.  
The **Stop** button immediately halts token delivery.

### Markdown rendering
Agent responses are rendered as HTML using [marked.js](https://marked.js.org/) with [DOMPurify](https://github.com/cure53/DOMPurify) sanitization.

| Markdown syntax | Rendered as |
|---|---|
| `**bold**` / `*italic*` | `<strong>` / `<em>` |
| `` `inline code` `` | `<code>` with monospace style |
| ` ```lang\n…\n``` ` | `<pre><code>` with scroll |
| `## Heading` | `<h2>` (h1–h4 supported) |
| `- item` / `1. item` | `<ul>/<ol><li>` |
| `[text](url)` | `<a href="url">` |
| `> quote` | `<blockquote>` |
| `\| col \| col \|` | `<table>` |

`<script>` tags and event-handler attributes (`onclick`, etc.) are stripped by DOMPurify before insertion into the DOM.

Markdown source is stored in `dataset.md` on each message node so it can be re-rendered correctly when conversation history is restored from `sessionStorage`.

### Model reasoning stream
When the model supports chain-of-thought reasoning (e.g. qwen3:8b with Ollama), an **aside panel** shows the raw reasoning trace in real time.

- Toggle the **"Show reasoning"** checkbox (bottom of input area) to send `enable_reasoning: true/false` to the server.
- The reasoning panel appears automatically the moment a `reasoning` event arrives.
- Click the **Reasoning** button to expand/collapse the reasoning body.

### Session history
The last conversation is stored in `sessionStorage` and restored automatically on page reload.  
History is cleared when the user clicks **Clear conversation**.

### Reconnect
The client reconnects automatically on disconnect using exponential back-off (1 s → 2 s → … → 30 s).

### Heartbeat
A `ping` / `pong` keepalive runs every 25 seconds to prevent idle connection drops.

---

## Architecture

```
Browser (Playwright / user)
  │  WebSocket  ws://host/ws
  ▼
FastAPI  web_server.py
  │  asyncio.Queue  (thread-safe bridge)
  ▼
IntegratedAgent.stream_events()      ← runs in thread pool
  │  yields AgentEvent objects
  ▼
ChatOllama / ChatOpenAI  (LangChain)
```

### Key files

| Path | Purpose |
|---|---|
| `agent/web_server.py` | FastAPI app; `/ws` WebSocket endpoint; `/health` HTTP endpoint |
| `agent/event_model.py` | `AgentEvent` dataclass — single wire format for all events |
| `agent/agent.py` | `stream_events()` generator; `_init_llm_with_reasoning()` |
| `agent/static/index.html` | Single-page UI shell |
| `agent/static/app.js` | WebSocket client; streaming render; reconnect; history |
| `agent/static/style.css` | Apple-style design tokens and markdown element styles |
| `agent/static/vendor/marked.min.js` | Markdown parser (vendored, no CDN dependency) |
| `agent/static/vendor/purify.min.js` | HTML sanitizer (vendored) |
| `start.sh` | Repo-root launcher script |

---

## WebSocket Protocol

### Client → Server

```jsonc
// Chat message
{ "type": "message", "content": "…", "enable_reasoning": true }

// Keepalive
{ "type": "ping" }

// Clear conversation history
{ "type": "clear" }
```

### Server → Client

| `type` | `content` | `metadata` | Meaning |
|---|---|---|---|
| `status` | `"connected"` | `{provider, model}` | Initial handshake |
| `status` | `"thinking"` | `{}` | LLM started |
| `reasoning` | chunk | `{}` | Chain-of-thought token |
| `token` | chunk | `{}` | Answer token |
| `final` | full text | `{reasoning_shown}` | Stream complete |
| `error` | message | `{}` | Error (replaces `final`) |
| `pong` | `""` | `{}` | Heartbeat reply |
| `cleared` | `""` | `{}` | History cleared |

### Per-connection isolation
Each WebSocket connection creates its own `IntegratedAgent` instance with a private conversation history.  
Closing the tab destroys the agent and its history.

---

## Running the Server Manually

```bash
cd agent
.venv/bin/python -m uvicorn web_server:app --host 127.0.0.1 --port 8000
```

Reload on code change (development):

```bash
.venv/bin/python -m uvicorn web_server:app --host 127.0.0.1 --port 8000 --reload
```

---

## Testing

### Backend unit tests

```bash
cd agent
.venv/bin/python -m pytest test_event_model.py test_stream_events.py test_web_server.py -v
```

| File | What it covers |
|---|---|
| `test_event_model.py` | `AgentEvent` factory methods and JSON serialisation |
| `test_stream_events.py` | `stream_events()` pipeline; reasoning on/off; error paths |
| `test_web_server.py` | WebSocket protocol; ping/pong; clear; error handling |

### Headless browser tests

```bash
cd agent
.venv/bin/python -m pytest test_ui_headless.py -v
```

Tests use Playwright (Chromium) with a client-side WebSocket mock that replaces
`window.WebSocket` via `add_init_script`.  No live Ollama or real network calls.

| Class | What it covers |
|---|---|
| `TestPageLoad` | Title, header, empty state, send button, focus |
| `TestConnectionStatus` | Status dot class, provider badge text |
| `TestSendMessage` | User/agent bubbles, empty-state hiding |
| `TestInputConstraints` | Disabled during stream, empty input guard, Shift+Enter |
| `TestReasoningPanel` | Hidden by default, shows on reasoning event, toggle |
| `TestClearConversation` | Clear removes all `.message` elements |
| `TestErrorHandling` | `.bubble--error` rendered, input re-enabled after error |
| `TestKeyboardAccessibility` | Tab focus lands on interactive element |
| `TestMarkdownRendering` | bold, italic, inline/block code, headings, lists, links, blockquotes, plain text, XSS sanitisation, history restore |

Run the full test suite (153 tests):

```bash
cd agent
.venv/bin/python -m pytest
```
