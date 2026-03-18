# Agent Lab - Quick Start Guide

**Status**: ✅ Production Ready | **Date**: 2026-03-16

## 🚀 30-Second Start

```bash
# Terminal 1: Start database
cd /Users/lewisgong/code/agent-lab
docker-compose up -d

# Terminal 2: Run agent
cd /Users/lewisgong/code/agent-lab/agent
python agent.py
```

## 📋 5-Minute Overview

### What Is Agent Lab?

A complete AI system with:
- **Vector Database**: PostgreSQL 17.9 + pgvector (for semantic search)
- **AI Agent**: LangChain with Ollama (local) or OpenAI (remote)
- **Chat Interface**: Interactive CLI with multi-turn conversations

### What Can It Do?

```
┌─────────────┐
│ You: "What is quantum computing?"
├─────────────┤
│ Agent: "Quantum computing uses..."
│ [Maintains conversation history]
│ [Remembers context]
└─────────────┘
```

### Who Runs What?

| Component | Status | Command |
|-----------|--------|---------|
| PostgreSQL | Docker | `docker-compose up -d` |
| Ollama | External | `ollama serve` (or already running) |
| Agent | Python | `python agent.py` |

## 🎯 Common Tasks

### Start Everything

```bash
# Terminal 1: Start database
cd /Users/lewisgong/code/agent-lab
docker-compose up -d

# Terminal 2: Verify Ollama (if not already running)
curl http://localhost:11434/api/tags

# Terminal 3: Run agent
cd /Users/lewisgong/code/agent-lab/agent
python agent.py
```

### Use Ollama (Local) - Default

**Already configured!** No changes needed.

```env
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
```

### Switch to OpenAI (Remote)

Edit `/Users/lewisgong/code/agent-lab/agent/.env`:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-actual-api-key-here
OPENAI_MODEL=gpt-4
```

Then restart agent:
```bash
cd /Users/lewisgong/code/agent-lab/agent
python agent.py
```

### Test Without Running Full Agent

```bash
# Direct Ollama test
python test_requests.py

# Agent connection test
python test_agent.py

# Multi-turn conversation test
python test_langchain_agent.py
```

### Connect to PostgreSQL

```bash
docker-compose exec db psql -U postgres

# In PostgreSQL:
\dt          # List tables
\dx          # List extensions
SELECT extname, extversion FROM pg_extension;
```

## 📚 Documentation Map

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | Project overview |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design & components |
| [AGENT.md](AGENT.md) | Agent setup & usage |
| **This file** | Quick reference |

## 🔧 Configuration Files

### Database Config
- **File**: `/Users/lewisgong/code/agent-lab/.env`
- **Variables**: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`

### Agent Config
- **File**: `/Users/lewisgong/code/agent-lab/agent/.env`
- **Variables**: `LLM_PROVIDER`, `OLLAMA_HOST`, `OLLAMA_MODEL`, `OPENAI_API_KEY`

## ✅ Verification Checklist

```bash
# 1. Database running?
docker-compose ps
# Look for: pgvector-db ... Up

# 2. Ollama running?
curl http://localhost:11434/api/tags
# Should return: {"models": [...]}

# 3. Agent works?
cd /Users/lewisgong/code/agent-lab/agent
python agent.py
# Try: "What is 2+2?"
# Expected: Math answer with context
```

## 🆘 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| "Connection refused" to Ollama | Check: `curl http://localhost:11434/api/tags` |
| "Connection refused" to PostgreSQL | Check: `docker-compose ps` and `docker-compose logs db` |
| Agent won't start | Check: `python -c "from agent import IntegratedAgent; print('OK')"` |
| Slow responses | Check CPU/RAM usage, consider smaller model |
| No modules found | Verify venv: `source /Users/lewisgong/code/.venv/bin/activate` |

## 💡 Agent Commands

Within the running agent:

```
You: What is Python?
Agent: Python is a programming language...

You: When was it created?
Agent: Python was created in 1989... [Remembers context!]

You: history
[Shows full conversation]

You: clear
[Clears conversation history]

You: exit
[Exits agent]
```

## 🎓 Learning Paths

### Path 1: Database Focused
1. Start with: `docker-compose up -d`
2. Connect: `docker-compose exec db psql`
3. Learn: pgvector operations
4. Do: Create tables, insert vectors, query

### Path 2: Agent Focused
1. Start with: `python agent.py`
2. Have conversations with qwen3:8b
3. Test history/memory
4. Switch to OpenAI

### Path 3: Full Integration
1. Run database: `docker-compose up -d`
2. Run agent: `python agent.py`
3. Plan: How to connect agent to database
4. Build: Vector embedding storage

## 🔌 Developer Environment

```
Language:      Python 3.13.1
Venv:          /Users/lewisgong/code/.venv
Project Root:  /Users/lewisgong/code/agent-lab
Agent Dir:     /Users/lewisgong/code/agent-lab/agent
OS:            macOS
```

## 📦 Package Summary

```
Backend:
  - langchain >= 0.1.0 (LLM orchestration)
  - langchain-openai >= 0.1.0 (OpenAI integration)
  - openai >= 1.0.0 (OpenAI SDK)
  - requests >= 2.31.0 (HTTP client)

Config:
  - python-dotenv >= 1.0.0 (Env vars)

Database:
  - psycopg2 (future: for agent-db integration)
  - sqlalchemy (future: ORM layer)
```

## 🚦 Project Status

✅ **Phase 1 Complete**
- PostgreSQL + pgvector running
- LangChain agent working
- Multi-provider support ready
- Ollama + OpenAI both supported
- Conversation memory functional

✅ **Phase 2 Complete**
- Database integration active
- Vector storage operational
- RAG functionality enabled
- PDF ingestion working
- Knowledge base populated

📋 **Full roadmap**: See [ARCHITECTURE.md#13-next-steps--future-enhancements](ARCHITECTURE.md#13-next-steps--future-enhancements)

## 🎯 Next Actions

1. **Immediate**: Run agent and test conversations
2. **Short-term**: Switch to OpenAI or try different Ollama models
3. **Medium-term**: Connect agent to PostgreSQL for embeddings
4. **Long-term**: Build RAG system with knowledge base

---

**Need more details?**
- Architecture → [ARCHITECTURE.md](ARCHITECTURE.md)
- Agent setup → [AGENT.md](AGENT.md)
- Database queries → [README.md](README.md)

**Created**: 2026-03-16 | **Status**: Production Ready
