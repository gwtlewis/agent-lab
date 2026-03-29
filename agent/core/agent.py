"""AI Agent with LangChain + multi-provider LLM support."""

import json
import logging
import os
import sys
from typing import Generator, List, Optional, Union
from urllib.parse import quote_plus

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from core.event_model import AgentEvent
from providers.llm_providers import LLMProvider, get_provider

load_dotenv()

logger = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

# Database configuration for RAG
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
ENABLE_RAG = os.getenv("ENABLE_RAG", "false").lower() == "true"

# Build database URL with URL-encoded credentials to handle special characters
DB_URL = (
    f"postgresql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


class IntegratedAgent:
    """LangChain-based agent with multi-provider LLM support."""

    # default fallbacks; overwritten based on model detection
    MAX_HISTORY_TOKENS = 2000
    DEFAULT_OLLAMA_MAX_TOKENS = 8192
    _MAX_TOOL_ITERATIONS = 5  # guard against runaway tool loops
    _MAX_CONTINUATIONS = 3    # max automatic continuations when output is truncated

    # Memory summarization settings
    _SUMMARIZE_THRESHOLD = 0.9   # trigger summarization at 90% of token budget
    _SUMMARIZE_KEEP_TURNS = 4    # number of recent messages to preserve verbatim (2 pairs)
    _SUMMARIZE_PROMPT = (
        "Summarize the following conversation exchange into a concise memory note. "
        "Capture key facts, names, goals, decisions, and important context. "
        "Keep it under 150 words.\n\nConversation:\n{conversation}\n\nSummary:"
    )

    def __init__(self, provider: str = "ollama", tools: Optional[List] = None):
        self.provider = provider.lower()
        self._llm_provider: LLMProvider = get_provider(self.provider)
        self.history: List[BaseMessage] = []
        self.llm = self._init_llm()
        if not self.llm:
            raise ValueError(f"Failed to init: {provider}")
        # determine context window after llm created
        self.MAX_HISTORY_TOKENS = self._llm_provider.get_max_tokens()

        # --- pluggable tool registration ---
        self._lc_tools: List = tools or []
        self._tool_map: dict = {}
        self._tools_enabled: bool = False

        if self._lc_tools:
            try:
                self.llm = self.llm.bind_tools(self._lc_tools)
                self._tool_map = {t.name: t for t in self._lc_tools}
                self._tools_enabled = True
                logger.info("Tools bound successfully: %s", list(self._tool_map.keys()))
            except (NotImplementedError, AttributeError, ValueError) as e:
                logger.warning(
                    "Tool binding failed — tools disabled for this session: %s", e
                )
                self._lc_tools = []

    def _init_llm(self):
        try:
            return self._llm_provider.get_chat_model(reasoning=False)
        except Exception as e:
            logger.warning("Failed to init LLM: %s", e)
            return None

    def _init_llm_with_reasoning(self):
        """Return a reasoning-enabled LLM instance, or None if unsupported."""
        if self.provider != "ollama":
            return None
        try:
            llm = self._llm_provider.get_chat_model(reasoning=True)
            if self._tools_enabled and self._lc_tools:
                try:
                    llm = llm.bind_tools(self._lc_tools)
                except Exception:
                    pass  # reasoning LLM tool bind is best-effort
            return llm
        except Exception as e:
            logger.warning("Failed to init reasoning LLM: %s", e)
            return None

    def verify_connection(self) -> bool:
        if not self._llm_provider.is_available():
            logger.warning("LLM provider '%s' is not available", self.provider)
            return False
        print(f"✓ Connected to {self._llm_provider.name}")
        print(f"✓ Using model: {self._llm_provider.model_name}")
        return True

    def chat(
        self,
        msg: str,
        system_prompt: str | None = None,
        stream: bool = True,
        use_rag: bool = True,
        k_documents: int = 5,
    ) -> str:
        """Send a message and stream the response to stdout by default.

        When ``stream`` is True (default) the function prints tokens as they arrive and
        returns the final reply text once complete. Set ``stream=False`` to get the full
        response at once.
        """
        try:
            if use_rag and getattr(self, "enable_rag", False):
                search_knowledge_base = getattr(self, "search_knowledge_base", None)
                format_rag_context = getattr(self, "_format_rag_context", None)
                if callable(search_knowledge_base) and callable(format_rag_context):
                    docs = search_knowledge_base(msg, k=k_documents)
                    context = format_rag_context(docs)
                    rag_prompt = (
                        f"Financial Knowledge Base Context:\n{context}"
                        if context
                        else "Financial Knowledge Base Context:"
                    )
                    system_prompt = (
                        f"{system_prompt}\n\n{rag_prompt}" if system_prompt else rag_prompt
                    )

            # Summarize history if near the token budget limit, otherwise trim.
            if self._needs_summarization():
                self._summarize_history()
            else:
                self._trim_history()

            messages: List[BaseMessage] = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.extend(self.history)
            messages.append(HumanMessage(content=msg))

            if stream:
                resp = self._stream_response(messages)
            elif self._tools_enabled:
                resp = self._invoke_with_tools(messages)
            else:
                result = self.llm.invoke(messages)
                resp = result.content if hasattr(result, "content") else str(result)

            # Store in history
            self.history.append(HumanMessage(content=msg))
            self.history.append(
                AIMessage(content=resp if isinstance(resp, str) else str(resp))
            )
            return resp if isinstance(resp, str) else str(resp)
        except Exception as e:
            return f"Error: {e}"

    def _invoke_with_tools(self, messages: List[BaseMessage]) -> str:
        """Invoke the LLM with a tool-calling loop (non-streaming).

        Handles up to ``_MAX_TOOL_ITERATIONS`` tool calls before forcing a final
        answer from the model.
        """
        for _iteration in range(self._MAX_TOOL_ITERATIONS):
            result = self.llm.invoke(messages)
            tool_calls = getattr(result, "tool_calls", None)
            if not tool_calls:
                return result.content if hasattr(result, "content") else str(result)

            messages.append(result)
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                tool_id = tc.get("id", "")
                tool_args = tc.get("args", {})
                if tool_name in self._tool_map:
                    try:
                        raw = self._tool_map[tool_name].invoke(tool_args)
                        text, _ = self._parse_tool_result(raw)
                        messages.append(ToolMessage(content=text, tool_call_id=tool_id))
                    except Exception as e:
                        logger.warning("Tool %s failed: %s", tool_name, e)
                        messages.append(
                            ToolMessage(content=f"Tool error: {e}", tool_call_id=tool_id)
                        )
                else:
                    logger.warning("Unknown tool requested: %s", tool_name)
                    messages.append(
                        ToolMessage(content="Tool not found.", tool_call_id=tool_id)
                    )

        # Max iterations reached — ask for a plain answer
        result = self.llm.invoke(messages)
        return result.content if hasattr(result, "content") else str(result)

    @staticmethod
    def _parse_tool_result(raw_result) -> tuple:
        """Parse a tool's return value into ``(text_for_llm, metadata_for_event)``.

        Tools may return:
        - A plain string → used as-is, metadata is empty list.
        - A JSON string ``{"content": str, "docs": list}`` → structured metadata.
        """
        if not isinstance(raw_result, str):
            return str(raw_result), []
        try:
            parsed = json.loads(raw_result)
            if isinstance(parsed, dict) and "content" in parsed:
                return parsed["content"], parsed.get("docs", [])
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return raw_result, []

    @staticmethod
    def _is_truncated(last_chunk) -> bool:
        """Return True if the LLM hit its output token limit (response was cut off).

        Checks both Ollama (``done_reason``) and OpenAI (``finish_reason``) metadata
        on the final streaming chunk.  A value of ``"length"`` means the model ran
        out of output tokens before finishing naturally.
        """
        if last_chunk is None:
            return False
        meta = getattr(last_chunk, "response_metadata", None) or {}
        reason = meta.get("done_reason") or meta.get("finish_reason") or ""
        return reason == "length"

    def _stream_response(self, messages: List[BaseMessage]) -> str:
        """Stream LLM response to stdout via LangChain's streaming interface and return the full text.

        Automatically requests continuation when the model hits its output token
        limit (``finish_reason == "length"``), up to ``_MAX_CONTINUATIONS`` times.
        """
        full = []
        for _cont in range(1 + self._MAX_CONTINUATIONS):
            last_chunk = None
            for chunk in self.llm.stream(messages):
                last_chunk = chunk
                text = chunk.content if hasattr(chunk, "content") else str(chunk)
                if text:
                    print(text, end="", flush=True)
                    full.append(text)
            if not self._is_truncated(last_chunk):
                break
            logger.info(
                "LLM output truncated; requesting continuation %d/%d",
                _cont + 1, self._MAX_CONTINUATIONS,
            )
            messages = list(messages) + [
                AIMessage(content="".join(full)),
                HumanMessage(content="Continue"),
            ]
        print()
        return "".join(full)

    def stream_events(
        self,
        msg: str,
        system_prompt: Optional[str] = None,
        enable_reasoning: bool = True,
    ) -> Generator[AgentEvent, None, None]:
        """Yield normalized AgentEvent objects while streaming a response.

        Emits:
          - AgentEvent.status("compacting") when memory compression runs (optional)
          - AgentEvent.status("thinking") immediately
          - AgentEvent.reasoning(chunk) for each reasoning token (Ollama only)
          - AgentEvent.tool_call(name, query, docs) each time a tool is invoked
          - AgentEvent.token(chunk) for each answer token
          - AgentEvent.final(full_text) when done
          - AgentEvent.error(msg) on failure (replaces final)

        The caller is responsible for appending the completed turn to history
        by calling ``record_turn(msg, full_text)`` after consuming all events.
        """
        # Run memory compression before anything else so the UI can show a hint.
        if self._needs_summarization():
            yield AgentEvent.status("compacting")
            self._summarize_history()

        yield AgentEvent.status("thinking")

        try:
            self._trim_history()
            messages: List[BaseMessage] = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.extend(self.history)
            messages.append(HumanMessage(content=msg))

            # Try reasoning-enabled LLM first (Ollama only); it also gets tools bound.
            reasoning_llm = self._init_llm_with_reasoning() if enable_reasoning else None
            llm = reasoning_llm if reasoning_llm is not None else self.llm

            full_answer: List[str] = []
            reasoning_shown = False
            continuation_count = 0

            # Tool-calling loop — each iteration is one LLM call.
            # The loop also handles output-truncation continuations: when the model
            # hits its token limit (finish_reason == "length") and produces no tool
            # calls, the partial answer is fed back and the model is asked to
            # "Continue".  Continuations are capped at _MAX_CONTINUATIONS; tool-call
            # turns are capped at _MAX_TOOL_ITERATIONS.
            for _iteration in range(self._MAX_TOOL_ITERATIONS + self._MAX_CONTINUATIONS):
                tool_chunks: List = []   # accumulate AIMessageChunks with tool_call_chunks
                has_tool_calls = False
                last_chunk = None

                for chunk in llm.stream(messages):
                    last_chunk = chunk
                    # Reasoning trace (Ollama additional_kwargs)
                    if enable_reasoning:
                        reasoning_chunk = (
                            chunk.additional_kwargs.get("reasoning_content", "")
                            if hasattr(chunk, "additional_kwargs")
                            else ""
                        )
                        if reasoning_chunk:
                            reasoning_shown = True
                            yield AgentEvent.reasoning(reasoning_chunk)

                    # Tool-call chunk (model wants to invoke a tool)
                    if getattr(chunk, "tool_call_chunks", None):
                        has_tool_calls = True
                        tool_chunks.append(chunk)
                        continue

                    # Regular answer token
                    answer_chunk = chunk.content if hasattr(chunk, "content") else str(chunk)
                    if answer_chunk and not has_tool_calls:
                        full_answer.append(answer_chunk)
                        yield AgentEvent.token(answer_chunk)

                if not has_tool_calls:
                    # Check whether the model ran out of output tokens mid-response.
                    if self._is_truncated(last_chunk) and continuation_count < self._MAX_CONTINUATIONS:
                        continuation_count += 1
                        logger.info(
                            "LLM output truncated; requesting continuation %d/%d",
                            continuation_count, self._MAX_CONTINUATIONS,
                        )
                        # Feed the partial answer back so the model can pick up where
                        # it left off.  Use a plain "Continue" prompt — models trained
                        # with RLHF understand this idiom reliably.
                        messages = list(messages) + [
                            AIMessage(content="".join(full_answer)),
                            HumanMessage(content="Continue"),
                        ]
                        continue  # next iteration will stream the continuation
                    break  # normal completion or max continuations reached

                # Assemble the full AIMessage from accumulated chunks
                ai_msg = tool_chunks[0]
                for c in tool_chunks[1:]:
                    ai_msg = ai_msg + c
                messages.append(ai_msg)

                # Execute each requested tool call
                for tc in (ai_msg.tool_calls or []):
                    tool_name = tc.get("name", "")
                    tool_args = tc.get("args", {})
                    tool_id = tc.get("id", "")

                    if tool_name not in self._tool_map:
                        logger.warning("Unknown tool requested by model: %s", tool_name)
                        messages.append(
                            ToolMessage(content="Tool not found.", tool_call_id=tool_id)
                        )
                        continue

                    try:
                        raw = self._tool_map[tool_name].invoke(tool_args)
                        result_text, result_meta = self._parse_tool_result(raw)
                        query_str = tool_args.get("query", str(tool_args))
                        if tool_name == "render_dashboard":
                            yield AgentEvent.board(result_text)
                            messages.append(
                                ToolMessage(content="Dashboard rendered.", tool_call_id=tool_id)
                            )
                        else:
                            yield AgentEvent.tool_call(tool_name, query_str, result_meta)
                            messages.append(
                                ToolMessage(content=result_text, tool_call_id=tool_id)
                            )
                    except Exception as e:
                        logger.warning("Tool %s execution failed: %s", tool_name, e)
                        messages.append(
                            ToolMessage(
                                content=f"Tool error: {e}", tool_call_id=tool_id
                            )
                        )

            full_text = "".join(full_answer)
            # Persist turn in history
            self.history.append(HumanMessage(content=msg))
            self.history.append(AIMessage(content=full_text))
            yield AgentEvent.final(full_text, reasoning_shown=reasoning_shown)

        except Exception as e:
            logger.exception("stream_events error: %s", e)
            yield AgentEvent.error(str(e))

    def _estimate_tokens(self, text: Union[str, List]) -> int:
        # very simple estimate: split on whitespace
        if isinstance(text, str):
            return len(text.split())
        return len(str(text).split())

    def _trim_history(self):
        """Remove oldest messages until estimate of tokens falls under limit."""
        total = sum(self._estimate_tokens(m.content) for m in self.history)
        if total <= self.MAX_HISTORY_TOKENS:
            return
        while self.history and total > self.MAX_HISTORY_TOKENS:
            removed = self.history.pop(0)
            total -= self._estimate_tokens(removed.content)

    def _needs_summarization(self) -> bool:
        """Return True when history token estimate is at or above the 90% threshold."""
        total = sum(self._estimate_tokens(m.content) for m in self.history)
        return total >= self._SUMMARIZE_THRESHOLD * self.MAX_HISTORY_TOKENS

    def _summarize_history(self) -> None:
        """Compress older turns into a single SystemMessage summary.

        Keeps the most recent ``_SUMMARIZE_KEEP_TURNS`` messages verbatim and
        replaces all earlier messages with one LLM-generated summary injected as
        a SystemMessage at the start of history.  Falls back to plain trimming if
        the LLM call fails or there is nothing old enough to summarize.
        """
        keep = self._SUMMARIZE_KEEP_TURNS
        old_turns = self.history[:-keep] if len(self.history) > keep else []
        if not old_turns:
            return  # nothing old enough to summarize

        conversation_text = "\n".join(
            f"{'User' if isinstance(m, HumanMessage) else 'Agent'}: {m.content}"
            for m in old_turns
        )
        prompt = self._SUMMARIZE_PROMPT.format(conversation=conversation_text)

        try:
            result = self.llm.invoke([HumanMessage(content=prompt)])
            summary_text = result.content if hasattr(result, "content") else str(result)
            summary_msg = SystemMessage(
                content=f"[Conversation summary — earlier context]\n{summary_text}"
            )
            self.history = [summary_msg] + self.history[-keep:]
        except Exception as e:
            logger.warning("Memory summarization failed, falling back to trim: %s", e)
            self._trim_history()

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

    def close(self):
        """Close any open resources."""
        pass


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
                prompt = user[len("nostream "):]
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
