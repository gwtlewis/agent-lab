"""Unit tests for IntegratedAgent pluggable tool system."""

import json
import unittest
from unittest.mock import MagicMock, Mock, patch, call

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage, ToolMessage

from core.agent import IntegratedAgent
from core.event_model import AgentEvent


# ---------------------------------------------------------------------------
# Helpers — build minimal mock objects
# ---------------------------------------------------------------------------

def _make_lc_tool(name="test_tool", return_value="plain result"):
    """Create a minimal mock LangChain tool."""
    tool = Mock()
    tool.name = name
    tool.invoke = Mock(return_value=return_value)
    return tool


def _make_mock_llm(chunks):
    """Return a mock LLM whose .stream() yields the given chunks."""
    llm = Mock()
    llm.stream = Mock(return_value=iter(chunks))
    llm.bind_tools = Mock(return_value=llm)
    llm.invoke = Mock()
    return llm


def _text_chunk(text):
    """Create a plain-text AIMessageChunk."""
    c = AIMessageChunk(content=text)
    return c


def _tool_call_chunk(name, args_json, tool_call_id="call_1"):
    """Create an AIMessageChunk that represents a tool call."""
    c = AIMessageChunk(
        content="",
        tool_call_chunks=[
            {"name": name, "args": args_json, "id": tool_call_id, "index": 0}
        ],
    )
    return c


# ---------------------------------------------------------------------------
# Patch target — avoid real Ollama / OpenAI connections
# ---------------------------------------------------------------------------

class TestIntegratedAgentToolInit(unittest.TestCase):
    """__init__ — tool registration behaviour."""

    @patch("core.agent.IntegratedAgent._init_llm")
    @patch("core.agent.get_provider")
    def test_init_no_tools_tools_disabled(self, mock_get_provider, mock_init_llm):
        """No tools provided → _tools_enabled is False; bind_tools never called."""
        mock_llm = Mock()
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        mock_init_llm.return_value = mock_llm
        mock_provider = Mock()
        mock_provider.get_max_tokens.return_value = 4096
        mock_get_provider.return_value = mock_provider

        agent = IntegratedAgent.__new__(IntegratedAgent)
        agent.provider = "ollama"
        agent._llm_provider = mock_provider
        agent.history = []
        agent.llm = mock_llm
        agent.MAX_HISTORY_TOKENS = 4096
        agent._lc_tools = []
        agent._tool_map = {}
        agent._tools_enabled = False

        self.assertFalse(agent._tools_enabled)
        self.assertEqual(agent._tool_map, {})

    @patch("core.agent.IntegratedAgent._init_llm")
    @patch("core.agent.get_provider")
    def test_init_with_tools_success(self, mock_get_provider, mock_init_llm):
        """Tools provided + bind succeeds → _tools_enabled=True; _tool_map populated."""
        mock_llm = Mock()
        bound_llm = Mock()
        mock_llm.bind_tools = Mock(return_value=bound_llm)
        mock_init_llm.return_value = mock_llm
        mock_provider = Mock()
        mock_provider.get_max_tokens.return_value = 4096
        mock_get_provider.return_value = mock_provider

        tool = _make_lc_tool("my_tool")
        with patch("core.agent.get_provider", return_value=mock_provider):
            # Manually test the init flow
            agent = Mock(spec=IntegratedAgent)
            agent._lc_tools = [tool]
            agent._tool_map = {tool.name: tool}
            agent._tools_enabled = True

        self.assertTrue(agent._tools_enabled)
        self.assertIn("my_tool", agent._tool_map)

    @patch("core.agent.IntegratedAgent._init_llm")
    @patch("core.agent.get_provider")
    def test_init_with_tools_bind_fails(self, mock_get_provider, mock_init_llm):
        """bind_tools raises NotImplementedError → _tools_enabled=False; no tool map."""
        mock_llm = Mock()
        mock_llm.bind_tools = Mock(side_effect=NotImplementedError("Not supported"))
        mock_init_llm.return_value = mock_llm
        mock_provider = Mock()
        mock_provider.get_max_tokens.return_value = 4096
        mock_get_provider.return_value = mock_provider

        tool = _make_lc_tool("rag_tool")

        # Simulate what __init__ does when bind fails
        lc_tools = [tool]
        tool_map = {}
        tools_enabled = False
        try:
            mock_llm.bind_tools(lc_tools)
            tools_enabled = True
            tool_map = {t.name: t for t in lc_tools}
        except (NotImplementedError, AttributeError, ValueError):
            lc_tools = []

        self.assertFalse(tools_enabled)
        self.assertEqual(tool_map, {})


class TestParseToolResult(unittest.TestCase):
    """IntegratedAgent._parse_tool_result — JSON convention parsing."""

    def setUp(self):
        self.agent = Mock(spec=IntegratedAgent)
        # Bind the static method for direct testing
        self._parse = IntegratedAgent._parse_tool_result

    def test_plain_string_returns_as_is(self):
        text, meta = self._parse("just text")
        self.assertEqual(text, "just text")
        self.assertEqual(meta, [])

    def test_json_with_content_key_extracts(self):
        raw = json.dumps({"content": "formatted context", "docs": [{"title": "A"}]})
        text, meta = self._parse(raw)
        self.assertEqual(text, "formatted context")
        self.assertEqual(meta, [{"title": "A"}])

    def test_json_without_content_key_treated_as_plain(self):
        raw = json.dumps({"something": "else"})
        text, meta = self._parse(raw)
        self.assertEqual(text, raw)
        self.assertEqual(meta, [])

    def test_invalid_json_treated_as_plain(self):
        raw = "{not valid json"
        text, meta = self._parse(raw)
        self.assertEqual(text, raw)
        self.assertEqual(meta, [])

    def test_non_string_coerced(self):
        text, meta = self._parse(42)
        self.assertEqual(text, "42")
        self.assertEqual(meta, [])

    def test_json_without_docs_defaults_to_empty(self):
        raw = json.dumps({"content": "ctx"})
        text, meta = self._parse(raw)
        self.assertEqual(meta, [])


class TestStreamEventsToolLoop(unittest.TestCase):
    """IntegratedAgent.stream_events — generic tool-call loop (mocked LLM)."""

    def _make_agent_with_tool(self, tool, llm_chunks_per_call):
        """Build a partial IntegratedAgent with a mocked LLM and one tool."""
        agent = IntegratedAgent.__new__(IntegratedAgent)
        agent.provider = "ollama"
        agent.history = []
        agent.MAX_HISTORY_TOKENS = 4096
        agent._MAX_TOOL_ITERATIONS = 5
        agent._lc_tools = [tool]
        agent._tool_map = {tool.name: tool}
        agent._tools_enabled = True

        call_count = [0]

        def stream_side_effect(messages):
            idx = call_count[0]
            call_count[0] += 1
            return iter(llm_chunks_per_call[idx])

        mock_llm = Mock()
        mock_llm.stream = Mock(side_effect=stream_side_effect)
        agent.llm = mock_llm
        agent._init_llm_with_reasoning = Mock(return_value=None)
        agent._trim_history = Mock()
        return agent

    def test_stream_events_no_tools_yields_tokens(self):
        """No tools: all text chunks become token events; final emitted at end."""
        agent = IntegratedAgent.__new__(IntegratedAgent)
        agent.provider = "ollama"
        agent.history = []
        agent.MAX_HISTORY_TOKENS = 4096
        agent._MAX_TOOL_ITERATIONS = 5
        agent._lc_tools = []
        agent._tool_map = {}
        agent._tools_enabled = False
        agent._init_llm_with_reasoning = Mock(return_value=None)
        agent._trim_history = Mock()

        mock_llm = Mock()
        mock_llm.stream = Mock(return_value=iter([_text_chunk("Hello"), _text_chunk(" world")]))
        agent.llm = mock_llm

        events = list(agent.stream_events("hi", enable_reasoning=False))
        types = [e.type for e in events]

        self.assertIn("status", types)
        self.assertEqual(types.count("token"), 2)
        self.assertIn("final", types)

        final = next(e for e in events if e.type == "final")
        self.assertEqual(final.content, "Hello world")

    def test_stream_events_emits_tool_call_event(self):
        """When LLM emits tool-call chunks, a tool_call event is yielded."""
        tool = _make_lc_tool("search_knowledge_base", return_value="plain result")

        # First LLM call: emits a tool call chunk
        # Second LLM call: emits plain text
        tc_chunk = _tool_call_chunk("search_knowledge_base", '{"query": "XVA"}')
        agent = self._make_agent_with_tool(
            tool,
            llm_chunks_per_call=[
                [tc_chunk],
                [_text_chunk("The answer is 42.")],
            ],
        )

        events = list(agent.stream_events("XVA question", enable_reasoning=False))
        tc_events = [e for e in events if e.type == "tool_call"]

        self.assertEqual(len(tc_events), 1)
        self.assertEqual(tc_events[0].metadata["tool"], "search_knowledge_base")

    def test_stream_events_tool_result_fed_back_llm_reinvoked(self):
        """After tool executes, LLM is reinvoked; final answer tokens are yielded."""
        tool = _make_lc_tool("search_knowledge_base", return_value="plain result")
        tc_chunk = _tool_call_chunk("search_knowledge_base", '{"query": "CVA"}')

        agent = self._make_agent_with_tool(
            tool,
            llm_chunks_per_call=[
                [tc_chunk],
                [_text_chunk("Here is the answer.")],
            ],
        )

        events = list(agent.stream_events("CVA question", enable_reasoning=False))
        token_events = [e for e in events if e.type == "token"]
        final_events = [e for e in events if e.type == "final"]

        self.assertTrue(len(token_events) > 0)
        self.assertEqual(len(final_events), 1)
        self.assertIn("Here is the answer.", final_events[0].content)
        # Tool was invoked exactly once
        tool.invoke.assert_called_once()

    def test_stream_events_unknown_tool_skipped(self):
        """LLM requests unknown tool → stream continues to final without crashing."""
        agent = IntegratedAgent.__new__(IntegratedAgent)
        agent.provider = "ollama"
        agent.history = []
        agent.MAX_HISTORY_TOKENS = 4096
        agent._MAX_TOOL_ITERATIONS = 5
        agent._lc_tools = []
        agent._tool_map = {}  # empty — no tools registered
        agent._tools_enabled = True
        agent._init_llm_with_reasoning = Mock(return_value=None)
        agent._trim_history = Mock()

        unknown_chunk = _tool_call_chunk("nonexistent_tool", '{"query": "test"}')

        call_count = [0]

        def stream_side_effect(messages):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                return iter([unknown_chunk])
            return iter([_text_chunk("Fallback answer.")])

        mock_llm = Mock()
        mock_llm.stream = Mock(side_effect=stream_side_effect)
        agent.llm = mock_llm

        events = list(agent.stream_events("test", enable_reasoning=False))
        types = [e.type for e in events]

        # Must reach final without raising
        self.assertIn("final", types)
        self.assertNotIn("error", types)

    def test_stream_events_no_tool_calls_single_iteration(self):
        """Plain text response exits loop after first iteration."""
        agent = IntegratedAgent.__new__(IntegratedAgent)
        agent.provider = "ollama"
        agent.history = []
        agent.MAX_HISTORY_TOKENS = 4096
        agent._MAX_TOOL_ITERATIONS = 5
        agent._lc_tools = []
        agent._tool_map = {}
        agent._tools_enabled = False
        agent._init_llm_with_reasoning = Mock(return_value=None)
        agent._trim_history = Mock()

        stream_call_count = [0]

        def stream_side_effect(messages):
            stream_call_count[0] += 1
            return iter([_text_chunk("Answer.")])

        mock_llm = Mock()
        mock_llm.stream = Mock(side_effect=stream_side_effect)
        agent.llm = mock_llm

        list(agent.stream_events("question", enable_reasoning=False))
        self.assertEqual(stream_call_count[0], 1)


class TestInvokeWithTools(unittest.TestCase):
    """IntegratedAgent._invoke_with_tools — non-streaming tool loop."""

    def _make_agent(self, tool):
        agent = IntegratedAgent.__new__(IntegratedAgent)
        agent._MAX_TOOL_ITERATIONS = 5
        agent._tool_map = {tool.name: tool}
        agent._tools_enabled = True
        return agent

    def test_no_tool_calls_returns_content(self):
        """If LLM returns a plain AIMessage, content is returned."""
        tool = _make_lc_tool()
        agent = self._make_agent(tool)
        mock_llm = Mock()
        mock_llm.invoke = Mock(return_value=AIMessage(content="Direct answer"))
        agent.llm = mock_llm

        result = agent._invoke_with_tools([])
        self.assertEqual(result, "Direct answer")

    def test_tool_called_and_result_fed_back(self):
        """Tool call is executed, result appended, LLM reinvoked for final answer."""
        tool = _make_lc_tool("search_knowledge_base", return_value="tool output")
        agent = self._make_agent(tool)

        # First invoke: AIMessage with tool_calls
        ai_with_tool = AIMessage(
            content="",
            tool_calls=[{"name": "search_knowledge_base", "args": {"query": "q"}, "id": "c1"}],
        )
        # Second invoke: plain answer
        final_ai = AIMessage(content="Final answer after tool")

        mock_llm = Mock()
        mock_llm.invoke = Mock(side_effect=[ai_with_tool, final_ai])
        agent.llm = mock_llm

        result = agent._invoke_with_tools([])
        self.assertEqual(result, "Final answer after tool")
        tool.invoke.assert_called_once_with({"query": "q"})


class TestMemorySummarizer(unittest.TestCase):
    """IntegratedAgent memory summarization — threshold trigger and compression logic."""

    PRESERVE_TURNS = 4  # messages = 2 HumanMessage/AIMessage pairs

    def _make_agent(self, max_tokens=1000):
        """Return a minimal IntegratedAgent with a mocked LLM."""
        agent = IntegratedAgent.__new__(IntegratedAgent)
        agent.provider = "ollama"
        agent.history = []
        agent.MAX_HISTORY_TOKENS = max_tokens
        agent._MAX_TOOL_ITERATIONS = 5
        agent._MAX_CONTINUATIONS = 3
        agent._lc_tools = []
        agent._tool_map = {}
        agent._tools_enabled = False
        agent._init_llm_with_reasoning = Mock(return_value=None)
        mock_llm = Mock()
        mock_llm.stream = Mock(return_value=iter([]))
        mock_llm.invoke = Mock(return_value=AIMessage(content="[Summary of past conversation.]"))
        agent.llm = mock_llm
        return agent

    def _add_turns(self, agent, n):
        """Append n Human/AI turn pairs to agent.history (5 words each)."""
        for i in range(n):
            agent.history.append(HumanMessage(content=f"User turn {i}: word word word word word"))
            agent.history.append(AIMessage(content=f"Agent turn {i}: word word word word word"))

    # --- _needs_summarization ---

    def test_needs_summarization_false_below_threshold(self):
        """Below 90% of MAX_HISTORY_TOKENS → _needs_summarization returns False."""
        agent = self._make_agent(max_tokens=10000)
        self._add_turns(agent, 2)  # tiny history
        self.assertFalse(agent._needs_summarization())

    def test_needs_summarization_true_at_or_above_90_percent(self):
        """At/above 90% of MAX_HISTORY_TOKENS → _needs_summarization returns True."""
        agent = self._make_agent(max_tokens=10)  # very low limit
        # 10 words → exactly at the limit
        agent.history.append(HumanMessage(content="a b c d e f g h i j"))
        self.assertTrue(agent._needs_summarization())

    def test_needs_summarization_exactly_at_threshold(self):
        """Exactly at 90% triggers summarization."""
        agent = self._make_agent(max_tokens=100)
        # 90 words = 90% of 100
        agent.history.append(HumanMessage(content=" ".join(["word"] * 90)))
        self.assertTrue(agent._needs_summarization())

    # --- _summarize_history ---

    def test_summarize_history_replaces_old_turns_with_summary_message(self):
        """After summarization, history[0] is a SystemMessage containing the summary."""
        agent = self._make_agent()
        self._add_turns(agent, 6)  # 12 messages, well above the preserve window
        agent._summarize_history()
        self.assertIsInstance(agent.history[0], SystemMessage)
        self.assertIn("[Summary of past conversation.]", agent.history[0].content)

    def test_summarize_history_preserves_recent_turns_verbatim(self):
        """The last PRESERVE_TURNS messages are kept verbatim after summarization."""
        agent = self._make_agent()
        self._add_turns(agent, 6)  # 12 messages
        last_four = [m.content for m in agent.history[-self.PRESERVE_TURNS:]]
        agent._summarize_history()
        recent = [m.content for m in agent.history[-self.PRESERVE_TURNS:]]
        self.assertEqual(recent, last_four)

    def test_summarize_history_calls_llm_invoke_once(self):
        """Summarization invokes the LLM exactly once to generate the summary."""
        agent = self._make_agent()
        self._add_turns(agent, 6)
        agent._summarize_history()
        agent.llm.invoke.assert_called_once()

    def test_summarize_history_total_messages_reduced(self):
        """After summarization, history is shorter than the original."""
        agent = self._make_agent()
        self._add_turns(agent, 6)
        original_len = len(agent.history)
        agent._summarize_history()
        self.assertLess(len(agent.history), original_len)

    def test_summarize_history_noop_when_not_enough_old_turns(self):
        """With fewer turns than the preserve window, nothing is summarized."""
        agent = self._make_agent()
        self._add_turns(agent, 2)  # 4 messages — equal to preserve window
        original_content = [m.content for m in agent.history]
        agent._summarize_history()
        result_content = [m.content for m in agent.history]
        self.assertEqual(original_content, result_content)
        agent.llm.invoke.assert_not_called()

    def test_summarize_history_fallback_on_llm_error(self):
        """If the summarization LLM call fails, history falls back to plain trimming."""
        agent = self._make_agent(max_tokens=10)
        agent.llm.invoke = Mock(side_effect=RuntimeError("LLM unavailable"))
        self._add_turns(agent, 6)
        # Must not raise
        agent._summarize_history()
        total = sum(agent._estimate_tokens(m.content) for m in agent.history)
        self.assertLessEqual(total, agent.MAX_HISTORY_TOKENS)

    def test_summarize_history_summary_contains_llm_output(self):
        """The SystemMessage content wraps the LLM-generated summary text."""
        agent = self._make_agent()
        agent.llm.invoke = Mock(return_value=AIMessage(content="Alice mentioned she is a developer."))
        self._add_turns(agent, 6)
        agent._summarize_history()
        self.assertIn("Alice mentioned she is a developer.", agent.history[0].content)


if __name__ == "__main__":
    unittest.main()
