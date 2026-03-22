# AI Agent - LangChain + OpenAI SDK

LangChain-based conversational AI agent with support for multiple LLM providers (Ollama local, OpenAI remote).

## Features

- **Multi-Provider Support**: Switch between Ollama (local) and OpenAI (remote) via `.env` configuration
- **LangChain Integration**: Uses `langchain_core.messages` for standardized message handling
- **Conversation Memory**: Maintains multi-turn conversation context with automatic message history
- **Custom Ollama Wrapper**: `OllamaLLM` class bridges Ollama REST API to LangChain interface
- **Provider Factory Pattern**: Dynamic initialization based on `LLM_PROVIDER` environment variable
- **Interactive CLI**: REPL-style interface with commands for conversation management
- **No Complex Dependencies**: Removed ConversationBufferMemory - uses simple Python list for memory

## Setup

### Prerequisites

- Ollama running locally on `localhost:11434` (default) OR valid OpenAI API key
- Python 3.10+
- Virtual environment (auto-configured)

### Installation

1. Install dependencies:
```bash
cd /Users/lewisgong/code/agent-lab/agent
/Users/lewisgong/code/.venv/bin/pip install -r requirements.txt
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

### Method 1: Using the run script (recommended)

```bash
/Users/lewisgong/code/agent-lab/agent/run_agent.sh
```

### Method 2: Direct Python

```bash
cd /Users/lewisgong/code/agent-lab/agent
/Users/lewisgong/code/.venv/bin/python agent.py
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

## Environment Integration

- **Parent Project**: agent-lab (Docker PostgreSQL with pgvector)
- **Python Environment**: `/Users/lewisgong/code/.venv` (Python 3.13.1)
- **Host Platform**: macOS with Ollama running
- **Database**: PostgreSQL 17.9 with pgvector 0.8.2

## Migration from Requests-based Agent

Updated from previous `requests`-only implementation:

| Change | Before | After |
|--------|--------|-------|
| Framework | Manual HTTP requests | LangChain with messages |
| Memory | Custom dict storage | LangChain BaseMessage list |
| LLM Abstraction | Single-provider | Multi-provider factory |
| OpenAI Support | Not available | Supported via LangChain |
| Message Format | Dict-based | LangChain message objects |

## Next Steps

- **Database Integration**: Store embeddings in pgvector for semantic search
- **System Prompts**: Add configurable system prompts for different agent roles
- **Streaming Responses**: Implement streaming for real-time chat responses
- **Function Calling**: Add tool calling support for extended agent capabilities
- **Retrieval Augmented Generation (RAG)**: Connect to pgvector for knowledge-base queries
- **Multi-model Orchestration**: Chain multiple models for complex tasks

## Notes

- Conversation history is stored in memory (cleared on exit)
- Each message includes full conversation context for better responses
- API calls have a 60-second timeout
- Use `clear_memory()` or `clear` command to start fresh conversation
- Provider can be changed at runtime by modifying `.env` and restarting agent
