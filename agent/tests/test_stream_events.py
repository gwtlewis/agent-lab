"""
Tests for IntegratedAgent.stream_events() – the reasoning-stream pipeline.

All tests mock the underlying LLM so no Ollama server is required.
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.agent import IntegratedAgent
from core.event_model import AgentEvent


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_chunk(content="", reasoning="", finish_reason=None):
    """Fake LangChain AIMessageChunk-like object.

    Args:
        content: Text content of the chunk.
        reasoning: Optional reasoning trace content (Ollama-style).
        finish_reason: If set, populates ``response_metadata`` so truncation
            detection works.  Pass ``"length"`` to simulate a truncated response
            or ``"stop"`` for a normal completion.
    """
    c = MagicMock()
    c.content = content
    c.additional_kwargs = {"reasoning_content": reasoning} if reasoning else {}
    # Explicitly None so the tool-call branch is not triggered for normal chunks
    c.tool_call_chunks = None
    if finish_reason is not None:
        # Both Ollama (done_reason) and OpenAI (finish_reason) formats
        c.response_metadata = {"finish_reason": finish_reason, "done_reason": finish_reason}
    else:
        c.response_metadata = {}
    return c


def _make_agent():
    """Return a mocked IntegratedAgent that never hits Ollama."""
    mock_provider = MagicMock()
    mock_provider.is_available.return_value = True
    mock_provider.get_chat_model.return_value = MagicMock()
    mock_provider.get_max_tokens.return_value = 2000

    with patch("core.agent.get_provider", return_value=mock_provider):
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
    @patch("core.agent.IntegratedAgent._init_llm_with_reasoning")
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

    @patch("core.agent.IntegratedAgent._init_llm_with_reasoning")
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

    @patch("core.agent.IntegratedAgent._init_llm_with_reasoning")
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


class TestStreamEventsContinuation:
    """Tests for automatic output-truncation continuation."""

    def test_no_continuation_on_normal_stop(self):
        """A normal finish_reason='stop' should NOT trigger continuation."""
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.return_value = [_make_chunk("done", finish_reason="stop")]
        list(agent.stream_events("q", enable_reasoning=False))
        assert agent.llm.stream.call_count == 1

    def test_continuation_triggered_on_length(self):
        """finish_reason='length' must trigger a second LLM call."""
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.side_effect = [
            # First call: truncated
            [_make_chunk("part one ", finish_reason="length")],
            # Second call: normal completion
            [_make_chunk("part two", finish_reason="stop")],
        ]
        list(agent.stream_events("q", enable_reasoning=False))
        assert agent.llm.stream.call_count == 2

    def test_continuation_tokens_concatenated_in_final(self):
        """The final event must contain the full joined text from all continuations."""
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.side_effect = [
            [_make_chunk("Hello ", finish_reason="length")],
            [_make_chunk("World", finish_reason="stop")],
        ]
        events = list(agent.stream_events("q", enable_reasoning=False))
        final = next(e for e in events if e.type == "final")
        assert final.content == "Hello World"

    def test_continuation_tokens_emitted_as_token_events(self):
        """All tokens — including continuation tokens — must be yielded as token events."""
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.side_effect = [
            [_make_chunk("foo ", finish_reason="length")],
            [_make_chunk("bar", finish_reason="stop")],
        ]
        events = list(agent.stream_events("q", enable_reasoning=False))
        tokens = [e for e in events if e.type == "token"]
        assert len(tokens) == 2
        assert tokens[0].content == "foo "
        assert tokens[1].content == "bar"

    def test_history_records_full_concatenated_answer(self):
        """History must store the complete answer, not just the first part."""
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.side_effect = [
            [_make_chunk("part1 ", finish_reason="length")],
            [_make_chunk("part2", finish_reason="stop")],
        ]
        list(agent.stream_events("question", enable_reasoning=False))
        from langchain_core.messages import AIMessage
        ai_msgs = [m for m in agent.history if isinstance(m, AIMessage)]
        assert ai_msgs[-1].content == "part1 part2"

    def test_max_continuations_respected(self):
        """Should stop after _MAX_CONTINUATIONS even if still truncated."""
        agent = _make_agent()
        agent.llm = MagicMock()
        # Always return truncated — should stop at 1 + _MAX_CONTINUATIONS calls
        agent.llm.stream.return_value = [_make_chunk("x", finish_reason="length")]
        list(agent.stream_events("q", enable_reasoning=False))
        assert agent.llm.stream.call_count == 1 + agent._MAX_CONTINUATIONS

    def test_continuation_uses_partial_answer_as_context(self):
        """The continuation call must include the partial answer as an AIMessage."""
        from langchain_core.messages import AIMessage, HumanMessage
        agent = _make_agent()
        agent.llm = MagicMock()
        agent.llm.stream.side_effect = [
            [_make_chunk("prefix ", finish_reason="length")],
            [_make_chunk("suffix", finish_reason="stop")],
        ]
        list(agent.stream_events("q", enable_reasoning=False))
        # The second stream call's messages must contain the partial AI answer
        second_call_messages = agent.llm.stream.call_args_list[1][0][0]
        ai_contents = [m.content for m in second_call_messages if isinstance(m, AIMessage)]
        assert any("prefix " in c for c in ai_contents)
        # And a "Continue" human message
        human_contents = [m.content for m in second_call_messages if isinstance(m, HumanMessage)]
        assert any("Continue" in c for c in human_contents)

    def test_is_truncated_ollama_format(self):
        """_is_truncated should recognise Ollama's done_reason='length'."""
        chunk = _make_chunk("text")
        chunk.response_metadata = {"done_reason": "length", "done": True}
        assert IntegratedAgent._is_truncated(chunk) is True

    def test_is_truncated_openai_format(self):
        """_is_truncated should recognise OpenAI's finish_reason='length'."""
        chunk = _make_chunk("text")
        chunk.response_metadata = {"finish_reason": "length"}
        assert IntegratedAgent._is_truncated(chunk) is True

    def test_is_truncated_returns_false_on_stop(self):
        chunk = _make_chunk("text", finish_reason="stop")
        assert IntegratedAgent._is_truncated(chunk) is False

    def test_is_truncated_returns_false_on_none(self):
        assert IntegratedAgent._is_truncated(None) is False

    def test_is_truncated_returns_false_when_no_metadata(self):
        chunk = _make_chunk("text")
        chunk.response_metadata = {}
        assert IntegratedAgent._is_truncated(chunk) is False


class TestStreamEventsSummarization:
    """Summarization: compacting status emitted and streaming continues normally."""

    def _make_agent_with_heavy_history(self):
        """Return an agent whose history already fills 90%+ of its token budget."""
        agent = _make_agent()
        agent.MAX_HISTORY_TOKENS = 10  # tiny budget — easy to exceed
        from langchain_core.messages import HumanMessage, AIMessage
        for _ in range(5):
            agent.history.append(HumanMessage(content="word word word"))
            agent.history.append(AIMessage(content="word word word"))
        return agent

    def test_compacting_status_emitted_when_summarization_needed(self):
        """When history >= 90% of token budget, a status('compacting') event is yielded."""
        agent = self._make_agent_with_heavy_history()
        from langchain_core.messages import AIMessage as AI
        agent.llm.invoke = MagicMock(return_value=AI(content="Summary."))
        agent.llm.stream = MagicMock(return_value=[_make_chunk("answer")])

        events = list(agent.stream_events("new question", enable_reasoning=False))
        status_contents = [e.content for e in events if e.type == "status"]
        assert "compacting" in status_contents

    def test_compacting_status_emitted_before_thinking(self):
        """The compacting status appears before the thinking status in the event stream."""
        agent = self._make_agent_with_heavy_history()
        from langchain_core.messages import AIMessage as AI
        agent.llm.invoke = MagicMock(return_value=AI(content="Summary."))
        agent.llm.stream = MagicMock(return_value=[_make_chunk("answer")])

        events = list(agent.stream_events("q", enable_reasoning=False))
        status_events = [e for e in events if e.type == "status"]
        contents = [e.content for e in status_events]
        assert "compacting" in contents
        assert contents.index("compacting") < contents.index("thinking")

    def test_token_and_final_emitted_after_compacting(self):
        """Normal token and final events are still delivered after a compacting cycle."""
        agent = self._make_agent_with_heavy_history()
        from langchain_core.messages import AIMessage as AI
        agent.llm.invoke = MagicMock(return_value=AI(content="Summary."))
        agent.llm.stream = MagicMock(return_value=[_make_chunk("response text")])

        events = list(agent.stream_events("q", enable_reasoning=False))
        assert any(e.type == "token" for e in events)
        final_events = [e for e in events if e.type == "final"]
        assert len(final_events) == 1
        assert final_events[0].content == "response text"

    def test_no_compacting_status_when_history_is_small(self):
        """With a small history (below threshold), no compacting status is emitted."""
        agent = _make_agent()
        agent.MAX_HISTORY_TOKENS = 10000  # huge budget — never compacts
        agent.llm.stream = MagicMock(return_value=[_make_chunk("ok")])

        events = list(agent.stream_events("hi", enable_reasoning=False))
        status_contents = [e.content for e in events if e.type == "status"]
        assert "compacting" not in status_contents

    def test_history_compressed_after_compacting(self):
        """After a compacting cycle, agent.history is shorter than before the call."""
        agent = self._make_agent_with_heavy_history()
        original_count = len(agent.history)
        from langchain_core.messages import AIMessage as AI
        agent.llm.invoke = MagicMock(return_value=AI(content="Summary."))
        agent.llm.stream = MagicMock(return_value=[_make_chunk("ok")])

        list(agent.stream_events("q", enable_reasoning=False))
        # history grows by 2 (new turn) but should be shorter than before overall
        assert len(agent.history) < original_count + 2


# ── Board tool dispatch ──────────────────────────────────────────────────────

def _make_tool_call_chunk(tool_name: str, tool_args: dict = None, tool_id: str = "tc_1"):
    """Fake a single tool-call chunk.

    A single chunk suffices because the accumulation loop (tool_chunks[0] +
    tool_chunks[1:]) with only one item never calls __add__, so
    ``ai_msg = tool_chunks[0]`` is the chunk itself.
    """
    chunk = MagicMock()
    chunk.content = ""
    chunk.additional_kwargs = {}
    chunk.tool_call_chunks = [{"name": tool_name, "id": tool_id}]  # truthy → routes to tool path
    chunk.response_metadata = {}
    chunk.tool_calls = [{"name": tool_name, "args": tool_args or {}, "id": tool_id}]
    return chunk


class TestStreamEventsBoardTool:
    """render_dashboard tool emits AgentEvent.board instead of tool_call."""

    def test_board_event_emitted(self):
        """A render_dashboard tool call must yield exactly one board event."""
        agent = _make_agent()
        html = "<table><tr><td>CVA</td><td>1.5M</td></tr></table>"
        mock_tool = MagicMock()
        mock_tool.name = "render_dashboard"
        mock_tool.invoke.return_value = html
        agent._tool_map = {"render_dashboard": mock_tool}
        agent._tools_enabled = True
        agent.llm.stream.side_effect = [
            [_make_tool_call_chunk("render_dashboard", {"html": html})],
            [_make_chunk("Here is your board.")],
        ]

        events = list(agent.stream_events("draw a table", enable_reasoning=False))
        board_events = [e for e in events if e.type == "board"]
        assert len(board_events) == 1
        assert board_events[0].content == html

    def test_board_event_content_is_raw_html(self):
        """board event content must be the exact HTML the tool returned."""
        agent = _make_agent()
        html = '<canvas id="myChart"></canvas><script>new Chart();</script>'
        mock_tool = MagicMock()
        mock_tool.name = "render_dashboard"
        mock_tool.invoke.return_value = html
        agent._tool_map = {"render_dashboard": mock_tool}
        agent._tools_enabled = True
        agent.llm.stream.side_effect = [
            [_make_tool_call_chunk("render_dashboard", {"html": html})],
            [_make_chunk("Done.")],
        ]

        events = list(agent.stream_events("show chart", enable_reasoning=False))
        board = next(e for e in events if e.type == "board")
        assert board.content == html

    def test_no_tool_call_event_for_render_dashboard(self):
        """render_dashboard must NOT emit a tool_call pill event — only a board event."""
        agent = _make_agent()
        mock_tool = MagicMock()
        mock_tool.name = "render_dashboard"
        mock_tool.invoke.return_value = "<p>chart</p>"
        agent._tool_map = {"render_dashboard": mock_tool}
        agent._tools_enabled = True
        agent.llm.stream.side_effect = [
            [_make_tool_call_chunk("render_dashboard", {})],
            [_make_chunk("Done.")],
        ]

        events = list(agent.stream_events("q", enable_reasoning=False))
        tool_call_events = [e for e in events if e.type == "tool_call"]
        assert len(tool_call_events) == 0

    def test_tool_message_fed_back_as_rendered(self):
        """The ToolMessage returned to the LLM must say 'Dashboard rendered.' not raw HTML."""
        from langchain_core.messages import ToolMessage
        agent = _make_agent()
        mock_tool = MagicMock()
        mock_tool.name = "render_dashboard"
        mock_tool.invoke.return_value = "<table>big table</table>"
        agent._tool_map = {"render_dashboard": mock_tool}
        agent._tools_enabled = True

        captured_messages = []
        call_count = [0]

        def stream_side_effect(messages):
            call_count[0] += 1
            if call_count[0] == 1:
                return iter([_make_tool_call_chunk("render_dashboard", {})])
            captured_messages.extend(messages)
            return iter([_make_chunk("ok")])

        agent.llm.stream.side_effect = stream_side_effect

        list(agent.stream_events("q", enable_reasoning=False))
        tool_messages = [m for m in captured_messages if isinstance(m, ToolMessage)]
        assert any("Dashboard rendered." in m.content for m in tool_messages)

    def test_non_board_tool_still_emits_tool_call_event(self):
        """Regression: non-dashboard tools must still emit the normal tool_call pill event."""
        agent = _make_agent()
        mock_tool = MagicMock()
        mock_tool.name = "search_knowledge_base"
        mock_tool.invoke.return_value = "some result"
        agent._tool_map = {"search_knowledge_base": mock_tool}
        agent._tools_enabled = True
        agent.llm.stream.side_effect = [
            [_make_tool_call_chunk("search_knowledge_base", {"query": "XVA"})],
            [_make_chunk("The answer is 42.")],
        ]

        events = list(agent.stream_events("what is XVA", enable_reasoning=False))
        tool_call_events = [e for e in events if e.type == "tool_call"]
        board_events = [e for e in events if e.type == "board"]
        assert len(tool_call_events) == 1
        assert len(board_events) == 0
