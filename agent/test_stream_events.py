"""
Tests for IntegratedAgent.stream_events() – the reasoning-stream pipeline.

All tests mock the underlying LLM so no Ollama server is required.
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import IntegratedAgent
from event_model import AgentEvent


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_chunk(content="", reasoning=""):
    """Fake LangChain AIMessageChunk-like object."""
    c = MagicMock()
    c.content = content
    c.additional_kwargs = {"reasoning_content": reasoning} if reasoning else {}
    return c


def _make_agent():
    """Return a mocked IntegratedAgent that never hits Ollama."""
    with patch("agent.requests.get") as mock_get, patch("agent.ChatOllama") as mock_llm:
        resp = MagicMock()
        resp.json.return_value = {"models": [{"name": "qwen3:8b"}]}
        mock_get.return_value = resp
        mock_llm.return_value = MagicMock()
        agent = IntegratedAgent()
    return agent


# ── Tests ────────────────────────────────────────────────────────────────────

class TestStreamEventsBasic:
    def test_emits_status_first(self):
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.return_value = [_make_chunk("hi")]

        events = list(agent.stream_events("hello", enable_reasoning=False))
        assert events[0].type == "status"
        assert events[0].content == "thinking"

    def test_emits_token_events(self):
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.return_value = [
            _make_chunk("hel"), _make_chunk("lo"),
        ]
        events = list(agent.stream_events("hi", enable_reasoning=False))
        tokens = [e for e in events if e.type == "token"]
        assert len(tokens) == 2
        assert tokens[0].content == "hel"
        assert tokens[1].content == "lo"

    def test_emits_final_event(self):
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.return_value = [_make_chunk("42")]
        events = list(agent.stream_events("what is 6*7", enable_reasoning=False))
        finals = [e for e in events if e.type == "final"]
        assert len(finals) == 1
        assert finals[0].content == "42"

    def test_final_contains_full_text(self):
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.return_value = [
            _make_chunk("Hello"), _make_chunk(" World"),
        ]
        events = list(agent.stream_events("greet", enable_reasoning=False))
        final = next(e for e in events if e.type == "final")
        assert final.content == "Hello World"

    def test_history_updated_after_stream(self):
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.return_value = [_make_chunk("pong")]
        list(agent.stream_events("ping", enable_reasoning=False))
        assert len(agent.history) == 2
        assert agent.history[0].content == "ping"
        assert agent.history[1].content == "pong"


class TestStreamEventsReasoning:
    @patch("agent.IntegratedAgent._init_llm_with_reasoning")
    def test_reasoning_chunks_emitted(self, mock_reasoning_llm_init):
        agent = _make_agent()
        reasoning_llm = MagicMock()
        reasoning_llm.stream.return_value = [
            _make_chunk(content="", reasoning="step 1"),
            _make_chunk(content="answer", reasoning=""),
        ]
        mock_reasoning_llm_init.return_value = reasoning_llm

        events = list(agent.stream_events("think", enable_reasoning=True))
        reason_events = [e for e in events if e.type == "reasoning"]
        assert len(reason_events) == 1
        assert reason_events[0].content == "step 1"

    @patch("agent.IntegratedAgent._init_llm_with_reasoning")
    def test_final_marks_reasoning_shown(self, mock_reasoning_llm_init):
        agent = _make_agent()
        llm = MagicMock()
        llm.stream.return_value = [
            _make_chunk(content="", reasoning="I thought about it"),
            _make_chunk(content="result"),
        ]
        mock_reasoning_llm_init.return_value = llm

        events = list(agent.stream_events("q", enable_reasoning=True))
        final = next(e for e in events if e.type == "final")
        assert final.metadata["reasoning_shown"] is True

    @patch("agent.IntegratedAgent._init_llm_with_reasoning")
    def test_fallback_when_no_reasoning_llm(self, mock_reasoning_llm_init):
        """If reasoning LLM returns None (e.g., OpenAI), falls back to base llm."""
        agent = _make_agent()
        mock_reasoning_llm_init.return_value = None
        agent.llm = MagicMock()
        agent.llm.stream.return_value = [_make_chunk("fallback")]

        events = list(agent.stream_events("q", enable_reasoning=True))
        tokens = [e for e in events if e.type == "token"]
        assert any(t.content == "fallback" for t in tokens)

    def test_no_reasoning_when_disabled(self):
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.return_value = [
            _make_chunk(content="ans", reasoning="should not appear"),
        ]
        events = list(agent.stream_events("q", enable_reasoning=False))
        assert not any(e.type == "reasoning" for e in events)


class TestStreamEventsEdgeCases:
    def test_empty_chunks_not_emitted_as_tokens(self):
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.return_value = [
            _make_chunk(""), _make_chunk("x"), _make_chunk(""),
        ]
        events = list(agent.stream_events("hi", enable_reasoning=False))
        tokens = [e for e in events if e.type == "token"]
        assert len(tokens) == 1
        assert tokens[0].content == "x"

    def test_error_event_on_llm_exception(self):
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.side_effect = RuntimeError("Ollama died")
        events = list(agent.stream_events("x", enable_reasoning=False))
        errors = [e for e in events if e.type == "error"]
        assert len(errors) == 1
        assert "Ollama died" in errors[0].content

    def test_no_final_on_error(self):
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.side_effect = RuntimeError("boom")
        events = list(agent.stream_events("x", enable_reasoning=False))
        assert not any(e.type == "final" for e in events)

    def test_system_prompt_included(self):
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.return_value = [_make_chunk("ok")]
        list(agent.stream_events("q", system_prompt="Be concise.", enable_reasoning=False))
        call_args = agent.llm.stream.call_args[0][0]
        from langchain_core.messages import SystemMessage
        assert any(isinstance(m, SystemMessage) for m in call_args)

    def test_history_trimmed_when_too_long(self):
        agent = _make_agent()
        agent.MAX_HISTORY_TOKENS = 5
        agent.llm = MagicMock()
        agent.llm.stream.return_value = [_make_chunk("ok")]
        # Flood history beyond limit
        from langchain_core.messages import HumanMessage, AIMessage
        for _ in range(20):
            agent.history.append(HumanMessage(content="word word word"))
            agent.history.append(AIMessage(content="word word word"))
        list(agent.stream_events("new q", enable_reasoning=False))
        # History should have been trimmed plus the new turn
        assert len(agent.history) <= 4   # trimmed + new user + new assistant

    def test_multiple_turns_accumulate_history(self):
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.return_value = [_make_chunk("a")]
        list(agent.stream_events("q1", enable_reasoning=False))
        agent.llm.stream.return_value = [_make_chunk("b")]
        list(agent.stream_events("q2", enable_reasoning=False))
        assert len(agent.history) == 4

    def test_unicode_content_preserved(self):
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.return_value = [_make_chunk("こんにちは")]
        events = list(agent.stream_events("greet in japanese", enable_reasoning=False))
        final = next(e for e in events if e.type == "final")
        assert final.content == "こんにちは"
