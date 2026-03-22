# AI Agent – LangChain + Ollama / OpenAI

LangChain-based conversational AI agent with support for multiple LLM providers,
real-time token streaming, chain-of-thought reasoning display, and a browser UI.

## Features

- **Multi-Provider Support**: Switch between Ollama (local) and OpenAI (remote) via `.env`
- **LangChain Integration**: Uses `langchain_ollama.ChatOllama` and `langchain_openai.ChatOpenAI`
- **Conversation Memory**: Multi-turn context with automatic history trimming
- **Token Streaming**: `stream_events()` generator yields `AgentEvent` objects in real time
- **Reasoning Stream**: Optional chain-of-thought trace via Ollama's `reasoning=True` flag
- **Web UI**: Browser chat served by `web_server.py` over WebSocket
- **CLI REPL**: Interactive terminal interface for quick testing

## Setup

### Prerequisites

- Ollama running locally on `localhost:11434` (default) OR valid OpenAI API key
- Python 3.10+
- Virtual environment (auto-configured)

### Installation

1. Install dependencies:
```bash
cd agent
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

2. Verify Ollama models (if using Ollama provider):
```bash
curl http://127.0.0.1:11434/api/tags
```

Expected models:
- `qwen3:8b` (primary - language model)
- `qwen3-embedding:4b` (embeddings)
- `nomic-embed-text:latest` (embeddings)

## Configuration

Edit `.env` to select provider and configure LLM:

### Ollama Provider (Default - Local)

```bash
LLM_PROVIDER=ollama
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
```

### OpenAI Provider (Remote)

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4
```

## Running the Agent

### Web UI (recommended)

```bash
# From repo root
./start.sh
# → http://127.0.0.1:8000
```

### CLI

```bash
cd agent
.venv/bin/python agent.py
```

## Interactive Commands

While the agent is running:

| Command | Description |
|---------|-------------|
| `<message>` | Send a message to the agent |
| `exit` / `quit` | Exit the agent |
| `clear` | Clear conversation history |
| `history` | View conversation history |

## Example Session

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

## Project Structure

```
agent-lab/agent/
├── agent.py              # Main agent with OllamaLLM & IntegratedAgent
├── run_agent.sh          # Execution script
├── requirements.txt      # Python dependencies (LangChain, OpenAI, requests)
├── .env                  # Configuration (LLM_PROVIDER, keys, models)
├── test_agent.py         # Connection test script
├── test_requests.py      # Direct Ollama API test script
├── test_langchain_agent.py # LangChain integration test
└── README.md             # This file
```

## Architecture

### OllamaLLM Class

Custom wrapper implementing LangChain's message protocol for Ollama:

```python
class OllamaLLM:
    """Custom LLM wrapper for Ollama using LangChain messages"""
    
    def __init__(self, model: str, host: str):
        self.model = model
        self.host = host
    
    def invoke(self, messages: List[BaseMessage]) -> str:
        # Convert LangChain BaseMessage objects to Ollama format
        msgs = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                msgs.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                msgs.append({"role": "assistant", "content": msg.content})
        
        # POST to /api/chat endpoint and return response
        r = requests.post(f"{self.host}/api/chat", 
            json={"model": self.model, "messages": msgs, "stream": False}, 
            timeout=60)
        return r.json().get("message", {}).get("content", "No response")
```

### IntegratedAgent Class

Provider-based factory pattern with conversation memory:

```python
class IntegratedAgent:
    """LangChain-based agent with multi-provider LLM support"""
    
    def __init__(self, provider: str = "ollama"):
        self.provider = provider.lower()
        self.history: List[BaseMessage] = []  # Conversation history
        self.llm = self._init_llm()
    
    def _init_llm(self):
        # Route to OllamaLLM or ChatOpenAI based on provider
        if self.provider == "ollama":
            return OllamaLLM(OLLAMA_MODEL, OLLAMA_HOST)
        elif self.provider == "openai":
            return ChatOpenAI(api_key=OPENAI_API_KEY, model=OPENAI_MODEL)
    
    def chat(self, msg: str, system_prompt: str = None) -> str:
        # Send message with accumulated history
        messages: List[BaseMessage] = []
        if system_prompt:
            messages.append(HumanMessage(content=system_prompt))
        messages.extend(self.history)
        messages.append(HumanMessage(content=msg))
        
        # Call LLM (works with both OllamaLLM and ChatOpenAI)
        resp = self.llm.invoke(messages)
        
        # Store in history for context
        self.history.append(HumanMessage(content=msg))
        self.history.append(AIMessage(content=resp))
        return resp
    
    def get_memory(self) -> str:
        # Display conversation history
        if not self.history:
            return "No conversation history"
        result = []
        for msg in self.history:
            role = "User" if isinstance(msg, HumanMessage) else "Agent"
            content = msg.content[:100]
            if len(msg.content) > 100:
                content += "..."
            result.append(f"{role}: {content}")
        return "\n".join(result)
    
    def clear_memory(self):
        # Reset conversation
        self.history = []
```

## Python Integration

```python
from agent import IntegratedAgent

# Initialize with Ollama (default)
agent = IntegratedAgent("ollama")

# Verify connection
if agent.verify_connection():
    # Send messages with automatic context
    response = agent.chat("Explain quantum computing")
    print(response)
    
    # Follow-up uses conversation history automatically
    response2 = agent.chat("Can you simplify that?")
    
    # View conversation
    print(agent.get_memory())
    
    # Clear history for new conversation
    agent.clear_memory()
```

## Dependencies

```
langchain>=0.1.0
langchain-openai>=0.1.0
openai>=1.0.0
python-dotenv>=1.0.0
requests>=2.31.0
```

### Key Libraries

| Library | Purpose |
|---------|---------|
| `langchain_core.messages` | Standard message types (HumanMessage, AIMessage) |
| `langchain_openai` | ChatOpenAI integration for remote LLMs |
| `openai` | OpenAI SDK (underlying openai library) |
| `requests` | HTTP client for direct Ollama API calls |
| `python-dotenv` | Environment variable management |

## Testing

### Test 1: Agent Initialization and Connection
```bash
/Users/lewisgong/code/.venv/bin/python -c \
  "from agent import IntegratedAgent; \
   a = IntegratedAgent('ollama'); \
   a.verify_connection()"
```

### Test 2: Multi-turn Conversation Memory
```bash
/Users/lewisgong/code/.venv/bin/python test_langchain_agent.py
```

### Test 3: Direct API Test
```bash
/Users/lewisgong/code/.venv/bin/python test_requests.py
```

### Test 4: Provider Routing
```python
# Test Ollama provider
agent_ollama = IntegratedAgent("ollama")
assert type(agent_ollama.llm).__name__ == "OllamaLLM"

# Test OpenAI provider (needs valid API key)
agent_openai = IntegratedAgent("openai")
assert type(agent_openai.llm).__name__ == "ChatOpenAI"
```

## Troubleshooting

### Connection Issues

**Ollama provider fails to connect:**
```bash
# Check if Ollama is running and accessible
curl http://127.0.0.1:11434/api/tags

# If not running, start Ollama
ollama serve
```

**OpenAI provider fails:**
```bash
# Verify API key is valid
echo $OPENAI_API_KEY
# Should start with sk-
```

### Import Errors

**Error: `ModuleNotFoundError: No module named 'langchain.schema'`**
- LangChain v0.1+ reorganized imports
- Solution: Use `langchain_core.messages` instead (already done in agent.py)

**Error: `ModuleNotFoundError: No module named 'langchain.memory'`**
- Reason: Agent uses simple Python list for message history instead of ConversationBufferMemory
- Solution: No action needed - this is intentional for simplicity

### Model/Mode Issues

**Model not found error:**
```bash
# List available models
curl http://127.0.0.1:11434/api/tags | jq '.models[].name'

# Update .env with available model
OLLAMA_MODEL=neural-chat:7b
```

**Slow responses:**
- Check system resources (CPU/RAM)
- Try smaller model: `neural-chat:7b` instead of `qwen3:8b`
- Increase timeout in agent.py (currently 60s)

## Streaming API – `stream_events()`

`IntegratedAgent.stream_events()` is a synchronous generator that yields
`AgentEvent` objects as the model produces tokens.

```python
from agent import IntegratedAgent

agent = IntegratedAgent(provider="ollama")
for event in agent.stream_events("Explain RAG in one paragraph",
                                  enable_reasoning=True):
    if event.type == "reasoning":
        print("[think]", event.content, end="", flush=True)
    elif event.type == "token":
        print(event.content, end="", flush=True)
    elif event.type == "final":
        print()  # newline
        break
    elif event.type == "error":
        print("Error:", event.content)
        break
```

### Event types

| `type` | When | `content` |
|---|---|---|
| `status` | First event (`"thinking"`) | status string |
| `reasoning` | Ollama chain-of-thought token | reasoning chunk |
| `token` | Each answer token | text chunk |
| `final` | Stream complete | full answer text |
| `error` | Exception occurred | error message |

### Reasoning stream

When `enable_reasoning=True`, the agent calls `_init_llm_with_reasoning()`
which creates a `ChatOllama` instance with `reasoning=True`.  
Reasoning chunks arrive in `chunk.additional_kwargs["reasoning_content"]`
and are emitted as `reasoning` events.

Reasoning events are **suppressed** when `enable_reasoning=False`, regardless
of whether the underlying model emits reasoning content.

## Event Model – `event_model.py`

`AgentEvent` is the shared wire format used by both `stream_events()` and
`web_server.py`.

```python
from event_model import AgentEvent

e = AgentEvent.token("hello")
print(e.to_json())
# {"type": "token", "content": "hello", "metadata": {}}
```

Factory methods: `.status()`, `.reasoning()`, `.token()`, `.final()`,
`.error()`, `.pong()`, `.cleared()`.

## Ollama Host Normalisation

`ollama_utils.normalize_ollama_host()` rewrites `localhost` → `127.0.0.1`
before passing the URL to `ChatOllama`.

**Root cause**: `httpx` (used internally by `ChatOllama`) resolves `localhost`
to `::1` (IPv6) on macOS.  If Ollama only listens on the IPv4 loopback,
the connection drops.  `requests` falls back to IPv4 silently; `httpx` does not.

## Environment Integration

- **Web server**: `web_server.py` — FastAPI + WebSocket
- **Browser UI**: `static/` — Apple-style single-page chat
- **Database**: PostgreSQL 17.9 + pgvector (for RAG)
- **Host Platform**: macOS with Ollama running locally

## Notes

- Conversation history is stored in memory (cleared on exit or `clear_memory()`)
- `WEB_PORT` in `agent/.env` controls the browser port (default: `8000`)
- Use `./start.sh` from the repo root to launch the web UI with one command

