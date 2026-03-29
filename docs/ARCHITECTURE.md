# Agent Lab – Architecture

**Last Updated**: 2026-03-29
**Project Status**: ✅ Production Ready

## 1. Project Overview

Agent Lab is a complete AI development environment combining:
- **Vector Database**: PostgreSQL 17.9 with pgvector for semantic search / RAG
- **LangChain Agent**: Multi-provider LLM orchestration (Ollama local + OpenAI remote)
- **Web UI**: Browser chat with real-time streaming, reasoning display, and Markdown rendering
- **CLI**: Interactive REPL for quick terminal use
- **Dynamic Configuration**: Single `.env` file switches between providers and ports

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Agent Lab System                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────┐       ┌──────────────────────────────────┐ │
│  │  Browser            │  WS   │  FastAPI  web_server.py          │ │
│  │  static/index.html  │◄─────►│  /ws  WebSocket endpoint         │ │
│  │  app.js  (marked,   │       │  /     static UI                 │ │
│  │  DOMPurify)         │       │  /health  HTTP health check      │ │
│  └─────────────────────┘       └──────────────┬───────────────────┘ │
│                                               │ asyncio.Queue        │
│  ┌─────────────────────┐       ┌──────────────▼───────────────────┐ │
│  │  CLI REPL           │       │  IntegratedAgent  (agent.py)     │ │
│  │  agent.py __main__  │──────►│  stream_events() generator       │ │
│  └─────────────────────┘       │  _init_llm_with_reasoning()      │ │
│                                │  conversation history (list)      │ │
│                                └──────────────┬───────────────────┘ │
│                          ┌─────────────────────┴──────────────────┐ │
│                          │                                         │ │
│                ┌─────────▼──────────┐             ┌───────────────▼┐ │
│                │  ChatOllama        │             │  ChatOpenAI    │ │
│                │  langchain_ollama  │             │  langchain_    │ │
│                │  reasoning=True    │             │  openai        │ │
│                └─────────┬──────────┘             └───────────────┘ │
│                          │                                           │
│                ┌─────────▼──────────┐   ┌───────────────────────┐  │
│                │  Ollama Server     │   │  OpenAI API           │  │
│                │  127.0.0.1:11434   │   │  api.openai.com       │  │
│                │  qwen3:8b          │   │  gpt-4 / gpt-4o       │  │
│                └─────────┬──────────┘   └───────────────────────┘  │
│                          │                                           │
│                ┌─────────▼────────────────────────────────────────┐ │
│                │  PostgreSQL 17.9 + pgvector 0.8.2  (Docker)     │ │
│                │  port 5432 – embeddings & vector similarity      │ │
│                └──────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## 3. Component Details

### 3.1 Docker Container - PostgreSQL 17.9 with pgvector

**Files**:
- `Dockerfile` - PostgreSQL 17.9 with pgvector extension
- `docker-compose.yml` - Service orchestration
- `.env` - Database credentials (root level)

**Configuration**:
```yaml
Server: postgres://localhost:5432
User: postgres
Password: postgres
Database: postgres
Extension: pgvector 0.8.2
```

**Status**: ✅ Running and verified  
**Data Persistence**: Yes (named volume: `agent-lab_pgvector_data`)

**Key Commands**:
```bash
# Start
docker-compose up -d

# Connect
docker-compose exec db psql -U postgres

# Verify pgvector
SELECT extname, extversion FROM pg_extension WHERE extname='vector';

# Check status
docker-compose ps
```

### 3.2 Ollama Local LLM Server

**Status**: ✅ Running on localhost:11434

**Available Models**:
1. `qwen3:8b` - Primary language model for chat
2. `qwen3-embedding:4b` - Embeddings generation
3. `nomic-embed-text:latest` - Alternative embeddings

**Configuration**:
- Host: `http://127.0.0.1:11434`
- Default Model: `qwen3:8b`
- API Endpoint: `/api/chat` (for chat) and `/api/tags` (for listing models)

**Verification**:
```bash
curl http://127.0.0.1:11434/api/tags
```

## 4. Web UI & WebSocket Server

**Files**: `agent/web_server.py`, `agent/event_model.py`, `agent/static/`

### 4.1 FastAPI Server (`web_server.py`)

- Serves the browser UI from `agent/static/` at `/`
- Exposes a WebSocket endpoint at `/ws`
- Exposes a health check at `/health`
- Each WebSocket connection creates an isolated `IntegratedAgent` instance

### 4.2 Streaming pipeline

```
ChatOllama/ChatOpenAI  →  stream_events() generator  →  asyncio.Queue  →  ws.send_text()
          (thread pool)                                   (main loop)
```

`stream_events()` runs in a thread-pool executor so it never blocks the asyncio
event loop. Events are placed on a `Queue` and forwarded to the client in order.

### 4.3 Event model (`event_model.py`)

`AgentEvent` is the shared dataclass used by both the generator and the server.
All events serialize to:

```json
{"type": "token", "content": "hello", "metadata": {}}
```

| `type` | When emitted |
|---|---|
| `status` | Connection established, thinking, memory compacting |
| `reasoning` | Each chain-of-thought token (Ollama reasoning mode) |
| `tool_call` | Once per RAG / general tool invocation |
| `board` | When `render_dashboard` is called — carries HTML fragment for the board panel |
| `token` | Each answer text chunk |
| `final` | End of turn; carries full answer and `reasoning_shown` flag |
| `error` | On exception; replaces `final` |
| `pong` / `cleared` | Heartbeat reply / history clear confirmation |

### 4.4 Browser client (`static/app.js`)

- Connects via `WebSocket` and listens with `addEventListener`
- Streams tokens into the agent bubble using `textContent`
- On `final` event: renders the full response as Markdown via `marked.parse()` + `DOMPurify.sanitize()`
- On `board` event: writes the HTML fragment into a sandboxed `<iframe>` (Chart.js 4.4 pre-loaded) shown as a split panel to the right of the transcript
- Libraries vendored locally in `static/vendor/` (no CDN dependency)
- Saves/restores conversation to `sessionStorage`; markdown source stored in `dataset.md`

### 4.5 Pluggable tools (`tools/`)

Tools are `@lc_tool`-decorated functions passed into `IntegratedAgent(tools=[...])`.
The agent binds them via `llm.bind_tools()` and dispatches by name in `stream_events()`.

| Tool | File | What it does |
|---|---|---|
| `render_dashboard` | `tools/dashboard.py` | Returns an HTML fragment; agent dispatch emits `AgentEvent.board` instead of the normal `tool_call` pill |

### 4.5 Launch

```bash
./start.sh          # auto-detects venv and WEB_PORT
```

## 5. Python Agent Component

**Location**: `agent/`

### 4.1 Core Implementation

**Files**: `llm_providers.py`, `agent.py`

---

#### LLMProvider (llm_providers.py) — Pluggable Provider Layer

The `llm_providers` module is the **single source of truth** for all LLM provider
configuration. No other module reads Ollama- or OpenAI-related environment variables
directly — everything goes through this abstraction.

```python
class LLMProvider(ABC):
    """Abstract interface every provider must implement."""
    @property
    def name(self) -> str: ...              # 'ollama' | 'openai'
    @property
    def model_name(self) -> str: ...        # active chat model name
    @property
    def embedding_model_name(self) -> str:  # active embeddings model name
    def is_available(self) -> bool: ...     # health check
    def get_chat_model(self, reasoning: bool = False): ...  # ChatOllama | ChatOpenAI
    def get_embeddings(self): ...           # OllamaEmbeddings | OpenAIEmbeddings
    def get_max_tokens(self) -> int: ...    # context-window size

def get_provider(name: str | None = None) -> LLMProvider:
    """Factory — reads LLM_PROVIDER env var when name is None."""
```

**Concrete implementations**:

| Class | Provider | Chat model | Embeddings model |
|---|---|---|---|
| `OllamaProvider` | Local Ollama | `OLLAMA_MODEL` | `OLLAMA_EMBEDDING_MODEL` |
| `OpenAIProvider` | OpenAI API | `OPENAI_MODEL` | `OPENAI_EMBEDDING_MODEL` |

**Environment variables** (all optional — sensible defaults shown):

```env
# Ollama
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text:latest
OLLAMA_MAX_TOKENS=8192          # optional override

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_MAX_TOKENS=8192          # optional override
```

---

#### IntegratedAgent (agent.py)

- Delegates all LLM init to `get_provider(provider)`
- Manages conversation history (simple Python list)
- Supports streaming, reasoning traces (Ollama), history trimming, and LLM-powered memory summarization

```python
class IntegratedAgent:
    def __init__(self, provider: str = "ollama"):
        self._llm_provider: LLMProvider = get_provider(self.provider)
        self.llm = self._llm_provider.get_chat_model()
        self.MAX_HISTORY_TOKENS = self._llm_provider.get_max_tokens()
    
    def chat(self, msg: str) -> str: ...           # streaming or blocking
    def stream_events(self, msg: str) -> Generator[AgentEvent, None, None]: ...
    
    def get_memory(self) -> str:
        # Display conversation history
    
    def clear_memory(self):
        # Reset conversation

    def _needs_summarization(self) -> bool:
        # True when history >= 90% of MAX_HISTORY_TOKENS

    def _summarize_history(self) -> None:
        # Compress older turns into a SystemMessage summary; preserve last 4 messages verbatim
```

#### Memory Compression Strategy

When conversation history reaches **90% of the model's context window**, the agent
automatically compresses older turns:

1. The most recent **4 messages (2 turn pairs)** are kept verbatim.
2. All earlier turns are sent to the LLM with a summarization prompt.
3. The resulting summary replaces the old turns as a single `SystemMessage` at the
   start of history.
4. If the LLM call fails, the agent falls back to plain trimming (dropping oldest messages).

During `stream_events()`, a `status("compacting")` event is emitted before the normal
`status("thinking")` event so the UI can show a subtle **"Compacting conversation…"**
indicator. The indicator is removed automatically when the thinking phase begins.

### 4.2 Configuration

**File**: `agent/.env`

**Ollama Configuration** (default):
```env
LLM_PROVIDER=ollama
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
OPENAI_API_KEY=sk-your-api-key-here  # unused when provider=ollama
OPENAI_MODEL=gpt-4
```

**To Switch to OpenAI**:
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-real-api-key
OPENAI_MODEL=gpt-4
```

### 4.3 Dependencies

**File**: `requirements.txt`

```
langchain>=0.1.0          # LLM orchestration framework
langchain-openai>=0.1.0   # OpenAI integration
openai>=1.0.0            # OpenAI SDK
python-dotenv>=1.0.0     # Environment variable management
requests>=2.31.0         # HTTP client for Ollama API
```

**Python Version**: 3.13.1  
**Environment**: Virtual environment at `/Users/lewisgong/code/.venv`

## 5. Runtime - Interactive Agent

**File**: `python agent.py`

### 5.1 Startup Flow

1. Load `.env` configuration
2. Initialize provider-specific LLM
3. Verify connection to LLM server
4. Display agent status and available commands
5. Enter interactive REPL loop

### 5.2 Interactive Commands

| Command | Action |
|---------|--------|
| `<message>` | Send message to agent (maintains conversation history) |
| `exit` / `quit` | Exit agent gracefully |
| `clear` | Clear conversation history |
| `history` | Display full conversation history |
| `Ctrl+C` | Interrupt (same as exit) |

### 5.3 Example Session

```
======================================================================
Agent Lab - LangChain + OpenAI SDK Integration
======================================================================
Provider: ollama

✓ Connected to Ollama
✓ Available models: qwen3-embedding:4b, nomic-embed-text:latest, qwen3:8b
✓ Using model: qwen3:8b

======================================================================
Ready! Commands: exit, clear, history
======================================================================

You: What is 2+2?
Agent: The sum of 2 + 2 is **4** in standard arithmetic.

You: My name is Alice
Agent: Hello, Alice! It's a pleasure to meet you.

You: What is my name?
Agent: Your name is Alice. 😊 How can I assist you today?

You: history
User: What is 2+2?
Agent: The sum of 2 + 2 is **4** in standard arithmetic.
User: My name is Alice
Agent: Hello, Alice! It's a pleasure to meet you.
User: What is my name?
Agent: Your name is Alice. 😊 How can I assist you today?

You: exit
Goodbye!
```

## 6. Testing & Verification

### 6.1 Test Files

**test_requests.py**
- Direct Ollama API testing using requests
- Verifies `/api/chat` endpoint
- Tests model availability

**test_agent.py**
- Basic agent connection verification
- Tests Ollama availability check
- Validates agent initialization

**test_langchain_agent.py**
- LangChain integration testing
- Verifies embeddings API consistency
- Tests RAG pipeline components
- Multi-turn conversation testing
- Tests memory/history functionality
- Validates context awareness

### 6.2 Verification Checklist

```bash
# 1. Docker database
docker-compose ps

# 2. Ollama availability
curl http://127.0.0.1:11434/api/tags

# 3. Agent imports
python -c "from agent import IntegratedAgent; print('OK')"

# 4. Agent connection
python -c "from agent import IntegratedAgent; a = IntegratedAgent('ollama'); a.verify_connection()"

# 5. Multi-turn memory
python test_langchain_agent.py

# 6. Run interactive agent
python agent.py
```

## 7. Project File Structure

```
agent-lab/
├── Dockerfile                    # PostgreSQL 17.9 + pgvector
├── docker-compose.yml            # Container orchestration
├── .env                          # Database credentials
├── README.md                     # Main documentation
├── ARCHITECTURE.md               # This file
│
├── agent/                        # Python LangChain Agent
│   ├── agent.py                 # Main implementation (160 lines)
│   ├── requirements.txt          # Python dependencies
│   ├── .env                     # Agent configuration
│   ├── README.md                # Agent documentation
│   │
│   ├── test_agent.py            # Connection tests
│   ├── test_requests.py         # Direct API tests
│   └── test_langchain_agent.py  # Integration tests
│
├── init-scripts/                 # SQL initialization (future)
│
└── .github/
    └── copilot-instructions.md  # VS Code agent config
```

## 8. Integration Points

### 8.1 Agent ↔ Database

**Planned Features**:
- Store conversation embeddings in pgvector
- Perform semantic similarity searches
- Retrieval Augmented Generation (RAG)
- Knowledge base queries

**Connection Details**:
```python
# Future implementation
import psycopg2
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="postgres",
    user="postgres",
    password="postgres"
)
```

### 8.2 Agent ↔ Ollama

**Current Interface**:
- HTTP REST API to `/api/chat` endpoint
- Request format: `{"model": "qwen3:8b", "messages": [...]}`
- Response format: `{"message": {"content": "..."}}`

### 8.3 Agent ↔ OpenAI

**Current Interface**:
- LangChain's ChatOpenAI class
- Automatic API key authentication
- Compatible with existing agent code

## 9. LangChain Integration Details

### 9.1 Message Types

```python
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

# User message
HumanMessage(content="What is quantum computing?")

# Agent response
AIMessage(content="Quantum computing is...")

# Generic message (base type)
BaseMessage  # parent class for all message types
```

### 9.2 Provider Selection Logic

```python
# Ollama provider
if provider == "ollama":
    return OllamaLLM(OLLAMA_MODEL, OLLAMA_HOST)

# OpenAI provider
elif provider == "openai":
    return ChatOpenAI(api_key=OPENAI_API_KEY, model=OPENAI_MODEL)
```

### 9.3 Why No ConversationBufferMemory

- Kept implementation simple and dependency-light
- Python list provides same functionality
- Avoids extra import issues with langchain.memory
- Easier to debug and customize

## 10. Performance Characteristics

### Response Times
- **Ollama (local)**: 2-10 seconds per response (qwen3:8b)
- **OpenAI (remote)**: 1-3 seconds per response (API call + network)

### Memory Usage
- **Agent + LangChain**: ~200MB base
- **Ollama process**: 4-8GB (model size dependent)
- **PostgreSQL**: 500MB-1GB

### Scalability
- **Concurrent agents**: Limited by Ollama memory (GPU/CPU)
- **Conversation history**: Unlimited in memory (could optimize with database)
- **Vector storage**: Scalable with pgvector

## 11. Environment Details

### Development Environment
- **OS**: macOS
- **Python**: 3.13.1
- **Virtual Environment**: `/Users/lewisgong/code/.venv`
- **Docker**: Desktop version with Docker Compose v2.18.1+

### Production Deployment (Future)
- Containerize agent as Docker service
- Use managed PostgreSQL with pgvector
- Deploy Ollama to GPU-enabled environment
- Or use OpenAI API directly

## 12. Troubleshooting Reference

### Issue: "Connection refused" to Ollama
```bash
# Check if Ollama is running
curl http://127.0.0.1:11434/api/tags

# If not running
ollama serve
```

### Issue: LangChain import errors
```bash
# Ensure correct imports
from langchain_core.messages import HumanMessage, AIMessage
# NOT: from langchain.schema import ...
```

### Issue: Model not found
```bash
# List available models
curl http://127.0.0.1:11434/api/tags | jq '.models[].name'

# Update .env with available model
OLLAMA_MODEL=neural-chat:7b
```

### Issue: Database not accessible
```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs db

# Restart container
docker-compose restart db
```

## 13. Next Steps & Future Enhancements

### Phase 1 (Current): ✅ Complete
- PostgreSQL + pgvector setup
- LangChain agent implementation
- Multi-provider LLM support
- Conversation memory system
- Interactive CLI

### Phase 2 (Current): ✅ Complete
- [x] Database integration layer
- [x] Vector embedding storage
- [x] Semantic search queries
- [x] RAG (Retrieval Augmented Generation)
- [x] PDF ingestion pipeline
- [x] Knowledge base with xVA documents

### Phase 3 (Current): ✅ Complete
- [x] Streaming responses (token streaming, reasoning stream)
- [x] Web UI interface (WebSocket, Markdown, dark mode, session history)
- [x] Function calling / tool use (`render_dashboard`, RAG search)
- [x] Financial dashboard board panel (Chart.js, tables, KPI cards in sandboxed iframe)

## 14. Quick Reference Commands

```bash
# Database
docker-compose up -d          # Start database
docker-compose down           # Stop database
docker-compose exec db psql   # Connect to PostgreSQL

# Agent
cd /Users/lewisgong/code/agent-lab/agent
python agent.py               # Run agent

# Testing
python test_agent.py         # Connection test
python test_requests.py      # Direct API test
python test_langchain_agent.py # Integration test

# LLM
curl http://127.0.0.1:11434/api/tags  # List Ollama models
```

## 15. Configuration Summary

| Component | Provider | Status | Location |
|-----------|----------|--------|----------|
| Database | PostgreSQL 17.9 | Running | localhost:5432 |
| Vector Extension | pgvector 0.8.2 | Loaded | postgres |
| LLM (Local) | Ollama qwen3:8b | Running | localhost:11434 |
| LLM (Remote) | OpenAI API | Configured | api.openai.com |
| Agent Framework | LangChain 0.1+ | Installed | Python venv |
| Language | Python 3.13.1 | Active | `/Users/lewisgong/code/.venv` |

---

**Created**: 2026-03-16  
**Status**: Production Ready  
**Version**: 1.0
