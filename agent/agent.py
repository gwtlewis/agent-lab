"""AI Agent with LangChain + OpenAI SDK Support"""

import json
import os
import sys
from typing import List, Union

import requests
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

# Database configuration for RAG
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
ENABLE_RAG = os.getenv("ENABLE_RAG", "false").lower() == "true"

# Build database URL
DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


class OllamaLLM:
    """Custom LLM wrapper for Ollama using LangChain messages"""

    def __init__(self, model: str, host: str):
        self.model = model
        self.host = host

    def invoke(self, messages: List[BaseMessage]) -> str:
        msgs = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                msgs.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                msgs.append({"role": "assistant", "content": msg.content})
            else:
                msgs.append({"role": "user", "content": str(msg.content)})

        r = requests.post(
            f"{self.host}/api/chat",
            json={"model": self.model, "messages": msgs, "stream": False},
            timeout=60,
        )
        if r.status_code != 200:
            raise Exception(f"Error: {r.status_code}")
        return r.json().get("message", {}).get("content", "No response")


class IntegratedAgent:
    """LangChain-based agent with multi-provider LLM support"""

    # default fallbacks; overwritten based on model detection
    MAX_HISTORY_TOKENS = 2000
    DEFAULT_OLLAMA_MAX_TOKENS = 8192

    def __init__(self, provider: str = "ollama"):
        self.provider = provider.lower()
        self.history: List[BaseMessage] = []  # Simple conversation history
        self.llm: Union[OllamaLLM, ChatOpenAI, None] = self._init_llm()
        if not self.llm:
            raise ValueError(f"Failed to init: {provider}")
        # determine context window after llm created
        self.MAX_HISTORY_TOKENS = self._get_model_max_tokens()

    def _init_llm(self) -> Union[OllamaLLM, ChatOpenAI, None]:
        if self.provider == "ollama":
            try:
                r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
                if OLLAMA_MODEL not in [m["name"] for m in r.json().get("models", [])]:
                    return None
                return OllamaLLM(OLLAMA_MODEL, OLLAMA_HOST)
            except:
                return None
        elif self.provider == "openai":
            if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("sk-your"):
                return None
            return ChatOpenAI(api_key=SecretStr(OPENAI_API_KEY), model=OPENAI_MODEL)
        return None

    def verify_connection(self) -> bool:
        if self.provider == "ollama":
            try:
                r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
                models = [m["name"] for m in r.json().get("models", [])]
                print(f"✓ Connected to Ollama")
                print(f"✓ Available models: {', '.join(models[:3])}")
                print(f"✓ Using model: {OLLAMA_MODEL}")
                return True
            except:
                return False
        return bool(OPENAI_API_KEY) and not (
            OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-your")
        )

    def chat(
        self, msg: str, system_prompt: str | None = None, stream: bool = True
    ) -> str:
        """Send a message and stream the response to stdout by default.

        When ``stream`` is True (default) the function prints tokens as they arrive and
        returns the final reply text once complete. This mimics ChatGPT's
        incremental output. Set ``stream=False`` to get the full response at once.
        """
        try:
            # trim history if it exceeds the model's context window
            self._trim_history()

            messages: List[BaseMessage] = []
            if system_prompt:
                messages.append(HumanMessage(content=system_prompt))
            messages.extend(self.history)
            messages.append(HumanMessage(content=msg))

            if stream:
                if isinstance(self.llm, OllamaLLM):
                    resp = self._stream_ollama(messages)
                else:
                    resp = self._stream_openai(messages)
            else:
                if isinstance(self.llm, OllamaLLM):
                    resp = self.llm.invoke(messages)
                elif self.llm:
                    result = self.llm.invoke(messages)
                    resp = result.content if hasattr(result, "content") else str(result)
                else:
                    resp = ""

            # Store in history
            self.history.append(HumanMessage(content=msg))
            self.history.append(
                AIMessage(content=resp if isinstance(resp, str) else str(resp))
            )
            return resp if isinstance(resp, str) else str(resp)
        except Exception as e:
            return f"Error: {e}"

    def _estimate_tokens(self, text: Union[str, List]) -> int:
        # very simple estimate: split on whitespace
        # for more accuracy, install and use tiktoken or similar tokenizer
        if isinstance(text, str):
            return len(text.split())
        return len(str(text).split())

    def _get_model_max_tokens(self) -> int:
        """Query the underlying API for the model's context length.
        Falls back to defaults plus environment overrides."""
        # allow manual override via env
        if self.provider == "ollama":
            env = os.getenv("OLLAMA_MAX_TOKENS")
            if env and env.isdigit():
                return int(env)
            # try to infer from available tags if possible (not always exposed)
            try:
                r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
                for m in r.json().get("models", []):
                    if m.get("name") == OLLAMA_MODEL:
                        # some Ollama builds may expose `max_tokens` or similar
                        if "max_tokens" in m:
                            return int(m["max_tokens"])
                        if "context_length" in m:
                            return int(m["context_length"])
            except Exception:
                pass
            # fallback
            return self.DEFAULT_OLLAMA_MAX_TOKENS
        elif self.provider == "openai":
            env = os.getenv("OPENAI_MAX_TOKENS")
            if env and env.isdigit():
                return int(env)
            try:
                from openai import OpenAI

                client = OpenAI(api_key=OPENAI_API_KEY)
                mdl = client.models.retrieve(OPENAI_MODEL)
                # openai returns context_length or max_tokens
                return getattr(
                    mdl,
                    "context_length",
                    getattr(mdl, "max_tokens", self.MAX_HISTORY_TOKENS),
                )
            except Exception:
                return self.MAX_HISTORY_TOKENS
        # default catch-all
        return self.MAX_HISTORY_TOKENS

    def _trim_history(self):
        """Remove oldest messages until estimate of tokens falls under limit."""
        total = sum(self._estimate_tokens(m.content) for m in self.history)
        if total <= self.MAX_HISTORY_TOKENS:
            return
        while self.history and total > self.MAX_HISTORY_TOKENS:
            removed = self.history.pop(0)
            total -= self._estimate_tokens(removed.content)

    def get_memory(self) -> str:
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
        self.history = []

    # streaming helpers
    def _stream_ollama(self, messages: List[BaseMessage]) -> str:
        """Stream Ollama response to stdout and return the full text."""
        # Ollama supports chunked output when you set stream=True
        msgs = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                msgs.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                msgs.append({"role": "assistant", "content": msg.content})
            else:
                msgs.append({"role": "user", "content": str(msg.content)})

        r = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": msgs, "stream": True},
            stream=True,
            timeout=60,
        )
        full = []
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                chunk = json.loads(line)
                text = chunk.get("message", {}).get("content", "")
            except Exception:
                # not json? just print raw
                text = line
            print(text, end="", flush=True)
            full.append(text)
        print()
        return "".join(full)

    def _stream_openai(self, messages: List[BaseMessage]) -> str:
        """Stream OpenAI response via ChatOpenAI streaming interface."""
        # using callback streamed to stdout
        from langchain_core.callbacks.streaming_stdout import (
            StreamingStdOutCallbackHandler,
        )

        if not OPENAI_API_KEY:
            return ""
        handler = StreamingStdOutCallbackHandler()
        llm = ChatOpenAI(
            api_key=SecretStr(OPENAI_API_KEY),
            model=OPENAI_MODEL,
            streaming=True,
            callbacks=[handler],
        )
        result = llm.invoke(messages)
        # result may already have full text in .content
        content = result.content if hasattr(result, "content") else str(result)
        return content if isinstance(content, str) else str(content)


def main():
    print("=" * 70)
    print("Agent Lab - LangChain + OpenAI SDK Integration")
    print("=" * 70)
    print(f"Provider: {LLM_PROVIDER}")
    print(f"RAG Enabled: {ENABLE_RAG}")
    print()

    try:
        if ENABLE_RAG:
            # Import here to avoid circular imports
            from agent_with_rag import RAGAgent

            agent = RAGAgent(LLM_PROVIDER, DB_URL)
        else:
            agent = IntegratedAgent(LLM_PROVIDER)
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)

    if not agent.verify_connection():
        print("Connection failed")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("Ready! Commands: exit, clear, history")
    print("=" * 70 + "\n")

    while True:
        try:
            user = input("You: ").strip()
            if not user:
                continue
            low = user.lower()
            if low in ("exit", "quit"):
                print("Goodbye!")
                break
            if low == "clear":
                agent.clear_memory()
                print("Cleared")
                continue
            if low == "history":
                print("\n" + agent.get_memory() + "\n")
                continue
            # non-streaming usage: start message with "nostream " to disable streaming
            if low.startswith("nostream "):
                prompt = user[len("nostream ") :]
                print("Agent: ", end="", flush=True)
                print(agent.chat(prompt, stream=False))
                continue
            print("Agent: ", end="", flush=True)
            agent.chat(user)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
