"""Tests for RAGAgent after refactor to tool-calling architecture."""

import json
import unittest
from unittest.mock import Mock, patch

from core.agent_with_rag import RAGAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_llm(bind_raises=False):
    """Build a mock LLM for IntegratedAgent._init_llm."""
    llm = Mock()
    if bind_raises:
        llm.bind_tools = Mock(side_effect=NotImplementedError("No tool support"))
    else:
        llm.bind_tools = Mock(return_value=llm)
    llm.stream = Mock(return_value=iter([]))
    llm.invoke = Mock(return_value=Mock(content=""))
    return llm


def _make_mock_provider(llm):
    """Build a mock LLMProvider for agent.get_provider."""
    p = Mock()
    p.get_max_tokens = Mock(return_value=4096)
    p.get_chat_model = Mock(return_value=llm)
    p.get_embeddings = Mock(return_value=Mock())
    return p


# Common patch targets
_INIT_LLM = "core.agent.IntegratedAgent._init_llm"
_GET_PROVIDER = "core.agent.get_provider"
_RAG_RETRIEVER = "core.agent_with_rag.RAGRetriever"
_LLP_GET_PROVIDER = "core.agent_with_rag.get_provider"


class TestRAGAgentInitialization(unittest.TestCase):
    """RAGAgent.__init__ — tool injection and enable_rag flag."""

    def _run_with_mocks(self, *, bind_raises=False, retriever_raises=False,
                        db_url="postgresql://localhost/test", enable_rag=True,
                        embeddings=None):
        """Helper to create a RAGAgent with mocked infrastructure."""
        mock_llm = _make_mock_llm(bind_raises=bind_raises)
        mock_provider = _make_mock_provider(mock_llm)
        mock_retriever = Mock()

        with patch(_INIT_LLM, return_value=mock_llm), \
             patch(_GET_PROVIDER, return_value=mock_provider), \
             patch(_LLP_GET_PROVIDER, return_value=mock_provider), \
             patch(_RAG_RETRIEVER,
                   side_effect=Exception("DB error") if retriever_raises
                   else Mock(return_value=mock_retriever)):
            agent = RAGAgent(
                provider="ollama",
                db_url=db_url,
                embeddings=embeddings or Mock(),
                enable_rag=enable_rag,
            )
        return agent

    def test_init_without_rag(self):
        """enable_rag=False → no retriever; enable_rag is False."""
        mock_llm = _make_mock_llm()
        mock_provider = _make_mock_provider(mock_llm)
        with patch(_INIT_LLM, return_value=mock_llm), \
             patch(_GET_PROVIDER, return_value=mock_provider):
            agent = RAGAgent(provider="ollama", enable_rag=False)

        self.assertFalse(agent.enable_rag)
        self.assertIsNone(agent.rag_retriever)

    def test_init_with_rag_enabled_no_db_url(self):
        """enable_rag=True but no db_url → no tool built; enable_rag is False."""
        mock_llm = _make_mock_llm()
        mock_provider = _make_mock_provider(mock_llm)
        with patch(_INIT_LLM, return_value=mock_llm), \
             patch(_GET_PROVIDER, return_value=mock_provider):
            agent = RAGAgent(provider="ollama", db_url=None, enable_rag=True)

        self.assertFalse(agent.enable_rag)
        self.assertIsNone(agent.rag_retriever)

    def test_init_with_rag_success_ollama(self):
        """Successful init → enable_rag=True; parent receives one tool."""
        agent = self._run_with_mocks()

        self.assertTrue(agent.enable_rag)
        self.assertIsNotNone(agent.rag_retriever)
        self.assertIn("search_knowledge_base", agent._tool_map)
        self.assertTrue(agent._tools_enabled)

    def test_init_with_rag_failure(self):
        """RAGRetriever init raises → enable_rag=False; rag_retriever is None."""
        agent = self._run_with_mocks(retriever_raises=True)

        self.assertFalse(agent.enable_rag)
        self.assertIsNone(agent.rag_retriever)

    def test_rag_tool_bind_fails_disables_rag(self):
        """Model doesn't support bind_tools → enable_rag=False."""
        agent = self._run_with_mocks(bind_raises=True)

        self.assertFalse(agent.enable_rag)
        self.assertFalse(agent._tools_enabled)

    def test_rag_tool_injected_into_parent(self):
        """After init, _tool_map has exactly one tool: search_knowledge_base."""
        agent = self._run_with_mocks()

        self.assertEqual(list(agent._tool_map.keys()), ["search_knowledge_base"])

    def test_stream_events_not_overridden(self):
        """RAGAgent must NOT define stream_events — parent's generic loop is used."""
        self.assertNotIn("stream_events", RAGAgent.__dict__)

    def test_chat_not_overridden(self):
        """RAGAgent must NOT define chat — parent's method is inherited."""
        self.assertNotIn("chat", RAGAgent.__dict__)


class TestRAGToolFactory(unittest.TestCase):
    """RAGAgent._make_rag_tool — standalone; no need to construct a full agent."""

    def _make_retriever(self, docs=None, raises=False):
        r = Mock()
        if raises:
            r.retrieve_context.side_effect = Exception("DB down")
        else:
            r.retrieve_context.return_value = docs or []
        return r

    def test_tool_name(self):
        tool = RAGAgent._make_rag_tool(self._make_retriever())
        self.assertEqual(tool.name, "search_knowledge_base")

    def test_tool_returns_json_with_content_and_docs(self):
        docs = [{"document_title": "Q1 Report", "content": "Revenue $1M", "similarity_score": 0.9}]
        tool = RAGAgent._make_rag_tool(self._make_retriever(docs))

        result = tool.invoke({"query": "revenue"})
        parsed = json.loads(result)

        self.assertIn("content", parsed)
        self.assertIn("docs", parsed)
        self.assertEqual(parsed["docs"][0]["title"], "Q1 Report")
        self.assertIn("Revenue $1M", parsed["content"])

    def test_tool_returns_empty_on_retrieval_failure(self):
        tool = RAGAgent._make_rag_tool(self._make_retriever(raises=True))

        result = tool.invoke({"query": "something"})
        parsed = json.loads(result)

        self.assertEqual(parsed["content"], "")
        self.assertEqual(parsed["docs"], [])

    def test_tool_passes_query_to_retriever(self):
        retriever = self._make_retriever()
        tool = RAGAgent._make_rag_tool(retriever)

        tool.invoke({"query": "XVA methodology"})

        retriever.retrieve_context.assert_called_once_with("XVA methodology")


class TestRAGAgentFormatContext(unittest.TestCase):
    """RAGAgent._format_rag_context — static; tested directly."""

    def test_format_rag_context_empty(self):
        self.assertEqual(RAGAgent._format_rag_context([]), "")

    def test_format_rag_context_single_document(self):
        docs = [{"similarity_score": 0.95, "document_title": "Q1", "content": "Revenue $1M"}]
        result = RAGAgent._format_rag_context(docs)

        self.assertIn("Document 1", result)
        self.assertIn("Q1", result)
        self.assertIn("95", result)
        self.assertIn("Revenue $1M", result)

    def test_format_rag_context_multiple_documents(self):
        docs = [
            {"similarity_score": 0.95, "document_title": "Q1", "content": "A"},
            {"similarity_score": 0.87, "document_title": "Q2", "content": "B"},
        ]
        result = RAGAgent._format_rag_context(docs)

        self.assertIn("Document 1 (Q1", result)
        self.assertIn("Document 2 (Q2", result)

    def test_format_rag_context_content_truncation(self):
        long_content = "A" * 1000
        docs = [{"similarity_score": 0.9, "document_title": "T", "content": long_content}]
        result = RAGAgent._format_rag_context(docs)

        self.assertLess(len(result), len(long_content))


class TestRAGAgentStats(unittest.TestCase):
    """RAGAgent.get_rag_stats."""

    def _make_rag_agent_with_retriever(self, retriever):
        mock_llm = _make_mock_llm()
        mock_provider = _make_mock_provider(mock_llm)
        with patch(_INIT_LLM, return_value=mock_llm), \
             patch(_GET_PROVIDER, return_value=mock_provider), \
             patch(_LLP_GET_PROVIDER, return_value=mock_provider), \
             patch(_RAG_RETRIEVER, return_value=retriever):
            return RAGAgent(provider="ollama", db_url="postgresql://localhost/test",
                            embeddings=Mock(), enable_rag=True)

    def test_get_rag_stats_disabled(self):
        mock_llm = _make_mock_llm()
        mock_provider = _make_mock_provider(mock_llm)
        with patch(_INIT_LLM, return_value=mock_llm), \
             patch(_GET_PROVIDER, return_value=mock_provider):
            agent = RAGAgent(provider="ollama", enable_rag=False)
        self.assertEqual(agent.get_rag_stats(), {})

    def test_get_rag_stats_success(self):
        expected = {"total_documents": 5, "total_chunks": 150}
        retriever = Mock()
        retriever.retrieve_context.return_value = []
        retriever.get_stats.return_value = expected

        agent = self._make_rag_agent_with_retriever(retriever)
        self.assertEqual(agent.get_rag_stats(), expected)

    def test_get_rag_stats_error(self):
        retriever = Mock()
        retriever.retrieve_context.return_value = []
        retriever.get_stats.side_effect = Exception("Stats failed")

        agent = self._make_rag_agent_with_retriever(retriever)
        self.assertEqual(agent.get_rag_stats(), {})


class TestRAGAgentSearchKnowledgeBase(unittest.TestCase):
    """RAGAgent.search_knowledge_base (direct retrieval, bypasses tools)."""

    def test_search_knowledge_base_rag_disabled(self):
        mock_llm = _make_mock_llm()
        mock_provider = _make_mock_provider(mock_llm)
        with patch(_INIT_LLM, return_value=mock_llm), \
             patch(_GET_PROVIDER, return_value=mock_provider):
            agent = RAGAgent(provider="ollama", enable_rag=False)
        with self.assertRaises(RuntimeError):
            agent.search_knowledge_base("test query")

    def test_search_knowledge_base_success(self):
        mock_results = [{"chunk_id": 1, "content": "Result 1", "similarity_score": 0.95}]
        retriever = Mock()
        retriever.retrieve_context.return_value = mock_results

        mock_llm = _make_mock_llm()
        mock_provider = _make_mock_provider(mock_llm)
        with patch(_INIT_LLM, return_value=mock_llm), \
             patch(_GET_PROVIDER, return_value=mock_provider), \
             patch(_LLP_GET_PROVIDER, return_value=mock_provider), \
             patch(_RAG_RETRIEVER, return_value=retriever):
            agent = RAGAgent(provider="ollama", db_url="postgresql://localhost/test",
                             embeddings=Mock(), enable_rag=True)

        results = agent.search_knowledge_base("revenue?", k=10)
        self.assertEqual(results, mock_results)
        retriever.retrieve_context.assert_called_once_with("revenue?", k=10)


if __name__ == "__main__":
    unittest.main()
