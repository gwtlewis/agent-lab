# Documentation Index

**Last Updated**: 2026-03-29

---

## 📚 Documentation Overview

### 🚀 Getting Started
- **[QUICKSTART.md](QUICKSTART.md)** – Setup guide; launch web UI with `./start.sh`
- **[WEB_UI.md](WEB_UI.md)** – Browser chat UI, WebSocket protocol, Markdown rendering, dashboard board panel ⭐ new

### 🏗️ System Design
- **[ARCHITECTURE.md](ARCHITECTURE.md)** – System architecture & diagrams
- **[AGENT.md](AGENT.md)** – Agent design, streaming API, reasoning stream

### 🛠️ Implementation Guides
- **[CLI_USAGE.md](CLI_USAGE.md)** – Command-line tool documentation
- **[XVA_RAG_TESTING.md](XVA_RAG_TESTING.md)** – RAG testing guide & test suite

### 📊 Project State
- **[PROJECT_STATUS.md](PROJECT_STATUS.md)** – Current status, metrics, and project overview

---

## 📋 Quick Reference

| File | Purpose | Audience |
|------|---------|----------|
| QUICKSTART.md | Setup & launch | Everyone |
| WEB_UI.md | Browser UI, WebSocket, Markdown | Developers/Users |
| ARCHITECTURE.md | System design | Developers/Architects |
| AGENT.md | Agent API, streaming, reasoning | Developers |
| CLI_USAGE.md | CLI tools | Users/Developers |
| PROJECT_STATUS.md | Current project state | Managers/Developers |
| XVA_RAG_TESTING.md | RAG & testing | QA/Developers |

---

## 🎯 Common Tasks

### Launch the web UI
```bash
./start.sh          # → http://127.0.0.1:8000
```

### Run all tests
```bash
cd agent && .venv/bin/python -m pytest   # 153 passed, 7 skipped
```

### Ingest a PDF
```bash
cd agent && .venv/bin/python -m ingest_pdf ingest <pdf_path>
```

### Switch to OpenAI
Edit `agent/.env`: set `LLM_PROVIDER=openai` and `OPENAI_API_KEY=sk-…`

---

## 📊 Project Statistics

| Metric | Value |
|---|---|
| Documentation files | 8 markdown files |
| Core modules | `agent.py`, `web_server.py`, `event_model.py`, `agent_with_rag.py`, `ingest_pdf.py`, `tools/dashboard.py` |
| Test files | 13 |
| Unit tests passing | 94 (mocked, no Ollama/DB required) |
| UI test coverage | 33 headless Playwright tests |
| Static assets | marked.js + DOMPurify + Chart.js 4.4 vendored (no CDN dependency) |

