"""Comprehensive unit tests for RAG-enhanced Agent"""

import os
import unittest
from unittest.mock import MagicMock, Mock, call, patch

from agent_with_rag import RAGAgent


class TestRAGAgentInitialization(unittest.TestCase):
    """Test cases for RAGAgent initialization"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_url = "postgresql://postgres:postgres@localhost:5432/postgres"
        self.mock_embeddings = Mock()

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    def test_init_without_rag(self, mock_parent_init):
        """Test initialization with RAG disabled"""
        agent = RAGAgent(provider="ollama", enable_rag=False)

        self.assertFalse(agent.enable_rag)
        self.assertIsNone(agent.rag_retriever)

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    def test_init_with_rag_enabled_no_db_url(self, mock_parent_init):
        """Test initialization with RAG enabled but no db_url"""
        agent = RAGAgent(provider="ollama", db_url=None, enable_rag=True)

        self.assertTrue(agent.enable_rag)
        self.assertIsNone(agent.rag_retriever)

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    @patch("agent_with_rag.RAGRetriever")
    def test_init_with_rag_success_ollama(self, mock_retriever_class, mock_parent_init):
        """Test successful initialization with Ollama and RAG"""
        mock_retriever = Mock()
        mock_retriever_class.return_value = mock_retriever

        agent = RAGAgent(
            provider="ollama",
            db_url=self.db_url,
            embeddings=self.mock_embeddings,
            enable_rag=True,
        )

        self.assertTrue(agent.enable_rag)
        self.assertEqual(agent.rag_retriever, mock_retriever)
        mock_retriever_class.assert_called_once_with(self.db_url, self.mock_embeddings)

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    @patch("agent_with_rag.RAGRetriever")
    def test_init_with_rag_failure(self, mock_retriever_class, mock_parent_init):
        """Test initialization with RAG retriever connection failure"""
        mock_retriever_class.side_effect = Exception("Database connection failed")

        agent = RAGAgent(
            provider="ollama",
            db_url=self.db_url,
            embeddings=self.mock_embeddings,
            enable_rag=True,
        )

        self.assertFalse(agent.enable_rag)
        self.assertIsNone(agent.rag_retriever)

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    @patch("langchain_openai.OpenAIEmbeddings")
    @patch("agent_with_rag.RAGRetriever")
    def test_init_auto_detect_openai_embeddings(
        self, mock_retriever_class, mock_embeddings_class, mock_parent_init
    ):
        """Test auto-detection of OpenAI embeddings when provider is openai"""
        os.environ["OPENAI_API_KEY"] = "test-key"
        mock_embeddings_instance = Mock()
        mock_embeddings_class.return_value = mock_embeddings_instance
        mock_retriever = Mock()
        mock_retriever_class.return_value = mock_retriever

        agent = RAGAgent(provider="openai", db_url=self.db_url, enable_rag=True)

        self.assertTrue(agent.enable_rag)
        mock_retriever_class.assert_called_once_with(
            self.db_url, mock_embeddings_instance
        )

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    @patch("langchain_ollama.OllamaEmbeddings")
    @patch("agent_with_rag.RAGRetriever")
    def test_init_auto_detect_ollama_embeddings(
        self, mock_retriever_class, mock_embeddings_class, mock_parent_init
    ):
        """Test auto-detection of Ollama embeddings when provider is ollama"""
        mock_embeddings_instance = Mock()
        mock_embeddings_class.return_value = mock_embeddings_instance
        mock_retriever = Mock()
        mock_retriever_class.return_value = mock_retriever

        agent = RAGAgent(provider="ollama", db_url=self.db_url, enable_rag=True)

        self.assertTrue(agent.enable_rag)
        mock_retriever_class.assert_called_once_with(
            self.db_url, mock_embeddings_instance
        )


class TestRAGAgentChat(unittest.TestCase):
    """Test cases for RAGAgent chat method"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_url = "postgresql://postgres:postgres@localhost:5432/postgres"
        self.mock_embeddings = Mock()
        self.mock_retriever = Mock()

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    @patch("agent_with_rag.IntegratedAgent.chat", return_value="Response")
    @patch("agent_with_rag.RAGRetriever")
    def test_chat_without_rag(
        self, mock_retriever_class, mock_parent_chat, mock_parent_init
    ):
        """Test chat without RAG enabled"""
        agent = RAGAgent(provider="ollama", enable_rag=False)

        response = agent.chat("What is finance?")

        self.assertEqual(response, "Response")
        mock_parent_chat.assert_called_once_with(
            "What is finance?", system_prompt=None, stream=True
        )

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    @patch("agent_with_rag.IntegratedAgent.chat", return_value="Response with context")
    @patch("agent_with_rag.RAGRetriever")
    def test_chat_with_rag_retrieval_success(
        self, mock_retriever_class, mock_parent_chat, mock_parent_init
    ):
        """Test chat with successful RAG retrieval"""
        mock_retriever = Mock()
        mock_retriever.retrieve_context.return_value = [
            {
                "chunk_id": 1,
                "content": "Financial data summary",
                "document_title": "Annual Report 2024",
                "source_file": "/path/to/report.pdf",
                "similarity_score": 0.85,
                "chunk_index": 0,
                "metadata": {},
            },
            {
                "chunk_id": 2,
                "content": "Revenue increased by 20%",
                "document_title": "Annual Report 2024",
                "source_file": "/path/to/report.pdf",
                "similarity_score": 0.78,
                "chunk_index": 1,
                "metadata": {},
            },
        ]
        mock_retriever_class.return_value = mock_retriever

        agent = RAGAgent(
            provider="ollama",
            db_url=self.db_url,
            embeddings=self.mock_embeddings,
            enable_rag=True,
        )

        response = agent.chat("What was the revenue growth?")

        self.assertEqual(response, "Response with context")
        mock_retriever.retrieve_context.assert_called_once_with(
            "What was the revenue growth?", k=5
        )

        # Verify that parent chat was called with context in system prompt
        call_args = mock_parent_chat.call_args
        self.assertIn("Financial Knowledge Base Context", call_args[1]["system_prompt"])
        self.assertIn("Financial data summary", call_args[1]["system_prompt"])

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    @patch("agent_with_rag.IntegratedAgent.chat", return_value="Response")
    @patch("agent_with_rag.RAGRetriever")
    def test_chat_with_rag_disabled_for_query(
        self, mock_retriever_class, mock_parent_chat, mock_parent_init
    ):
        """Test chat with RAG disabled for a specific query"""
        mock_retriever = Mock()
        mock_retriever_class.return_value = mock_retriever

        agent = RAGAgent(
            provider="ollama",
            db_url=self.db_url,
            embeddings=self.mock_embeddings,
            enable_rag=True,
        )

        response = agent.chat("What is this?", use_rag=False)

        # RAG retriever should not be called
        mock_retriever.retrieve_context.assert_not_called()
        mock_parent_chat.assert_called_once()

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    @patch("agent_with_rag.IntegratedAgent.chat", return_value="Response")
    @patch("agent_with_rag.RAGRetriever")
    def test_chat_with_custom_k_documents(
        self, mock_retriever_class, mock_parent_chat, mock_parent_init
    ):
        """Test chat with custom k_documents parameter"""
        mock_retriever = Mock()
        mock_retriever.retrieve_context.return_value = []
        mock_retriever_class.return_value = mock_retriever

        agent = RAGAgent(
            provider="ollama",
            db_url=self.db_url,
            embeddings=self.mock_embeddings,
            enable_rag=True,
        )

        agent.chat("Test query", k_documents=10)

        mock_retriever.retrieve_context.assert_called_once_with("Test query", k=10)

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    @patch("agent_with_rag.IntegratedAgent.chat", return_value="Response")
    @patch("agent_with_rag.RAGRetriever")
    def test_chat_with_retrieval_error(
        self, mock_retriever_class, mock_parent_chat, mock_parent_init
    ):
        """Test chat when RAG retrieval fails"""
        mock_retriever = Mock()
        mock_retriever.retrieve_context.side_effect = Exception("Retrieval failed")
        mock_retriever_class.return_value = mock_retriever

        agent = RAGAgent(
            provider="ollama",
            db_url=self.db_url,
            embeddings=self.mock_embeddings,
            enable_rag=True,
        )

        # Should not raise exception, should continue without RAG context
        response = agent.chat("Test query")

        self.assertEqual(response, "Response")
        mock_parent_chat.assert_called_once()

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    @patch("agent_with_rag.IntegratedAgent.chat", return_value="Response")
    @patch("agent_with_rag.RAGRetriever")
    def test_chat_with_custom_system_prompt(
        self, mock_retriever_class, mock_parent_chat, mock_parent_init
    ):
        """Test chat with custom system prompt"""
        mock_retriever = Mock()
        mock_retriever.retrieve_context.return_value = []
        mock_retriever_class.return_value = mock_retriever

        agent = RAGAgent(
            provider="ollama",
            db_url=self.db_url,
            embeddings=self.mock_embeddings,
            enable_rag=True,
        )

        custom_prompt = "You are a financial expert."
        agent.chat("Test", system_prompt=custom_prompt)

        call_args = mock_parent_chat.call_args
        self.assertIn(custom_prompt, call_args[1]["system_prompt"])


class TestRAGAgentFormatContext(unittest.TestCase):
    """Test cases for RAGAgent context formatting"""

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    def test_format_rag_context_empty(self, mock_parent_init):
        """Test formatting empty document list"""
        agent = RAGAgent(provider="ollama", enable_rag=False)

        result = agent._format_rag_context([])

        self.assertEqual(result, "")

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    def test_format_rag_context_single_document(self, mock_parent_init):
        """Test formatting single document"""
        agent = RAGAgent(provider="ollama", enable_rag=False)

        docs = [
            {
                "similarity_score": 0.95,
                "document_title": "Report Q1",
                "content": "Revenue was $1M" * 200,
            }
        ]

        result = agent._format_rag_context(docs)

        self.assertIn("Document 1", result)
        self.assertIn("Report Q1", result)
        self.assertIn("95", result)  # Check for percentage (95.00%)
        self.assertIn("Revenue was $1M", result)

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    def test_format_rag_context_multiple_documents(self, mock_parent_init):
        """Test formatting multiple documents"""
        agent = RAGAgent(provider="ollama", enable_rag=False)

        docs = [
            {
                "similarity_score": 0.95,
                "document_title": "Report Q1",
                "content": "First report",
            },
            {
                "similarity_score": 0.87,
                "document_title": "Report Q2",
                "content": "Second report",
            },
        ]

        result = agent._format_rag_context(docs)

        self.assertIn("Document 1 (Report Q1", result)
        self.assertIn("Document 2 (Report Q2", result)
        self.assertIn("95", result)  # Check for percentage
        self.assertIn("87", result)  # Check for percentage

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    def test_format_rag_context_content_truncation(self, mock_parent_init):
        """Test that long content is truncated"""
        agent = RAGAgent(provider="ollama", enable_rag=False)

        long_content = "A" * 1000
        docs = [
            {"similarity_score": 0.9, "document_title": "Test", "content": long_content}
        ]

        result = agent._format_rag_context(docs)

        # Content should be limited to 500 chars
        self.assertLess(len(result), len(long_content))


class TestRAGAgentStats(unittest.TestCase):
    """Test cases for RAG statistics methods"""

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    def test_get_rag_stats_disabled(self, mock_parent_init):
        """Test getting stats when RAG is disabled"""
        agent = RAGAgent(provider="ollama", enable_rag=False)

        stats = agent.get_rag_stats()

        self.assertEqual(stats, {})

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    @patch("agent_with_rag.RAGRetriever")
    def test_get_rag_stats_success(self, mock_retriever_class, mock_parent_init):
        """Test getting RAG stats successfully"""
        mock_retriever = Mock()
        expected_stats = {
            "total_documents": 5,
            "total_chunks": 150,
            "average_similarity": 0.82,
        }
        mock_retriever.get_stats.return_value = expected_stats
        mock_retriever_class.return_value = mock_retriever

        agent = RAGAgent(
            provider="ollama",
            db_url="postgresql://localhost/test",
            embeddings=Mock(),
            enable_rag=True,
        )

        stats = agent.get_rag_stats()

        self.assertEqual(stats, expected_stats)

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    @patch("agent_with_rag.RAGRetriever")
    def test_get_rag_stats_error(self, mock_retriever_class, mock_parent_init):
        """Test getting RAG stats when retriever fails"""
        mock_retriever = Mock()
        mock_retriever.get_stats.side_effect = Exception("Stats failed")
        mock_retriever_class.return_value = mock_retriever

        agent = RAGAgent(
            provider="ollama",
            db_url="postgresql://localhost/test",
            embeddings=Mock(),
            enable_rag=True,
        )

        stats = agent.get_rag_stats()

        self.assertEqual(stats, {})


class TestRAGAgentSearchKnowledgeBase(unittest.TestCase):
    """Test cases for knowledge base search"""

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    def test_search_knowledge_base_rag_disabled(self, mock_parent_init):
        """Test search when RAG is disabled"""
        agent = RAGAgent(provider="ollama", enable_rag=False)

        with self.assertRaises(RuntimeError):
            agent.search_knowledge_base("test query")

    @patch("agent_with_rag.IntegratedAgent.__init__", return_value=None)
    @patch("agent_with_rag.RAGRetriever")
    def test_search_knowledge_base_success(
        self, mock_retriever_class, mock_parent_init
    ):
        """Test successful knowledge base search"""
        mock_retriever = Mock()
        mock_results = [
            {"chunk_id": 1, "content": "Result 1", "similarity_score": 0.95},
            {"chunk_id": 2, "content": "Result 2", "similarity_score": 0.87},
        ]
        mock_retriever.retrieve_context.return_value = mock_results
        mock_retriever_class.return_value = mock_retriever

        agent = RAGAgent(
            provider="ollama",
            db_url="postgresql://localhost/test",
            embeddings=Mock(),
            enable_rag=True,
        )

        results = agent.search_knowledge_base("What is revenue?", k=10)

        self.assertEqual(results, mock_results)
        mock_retriever.retrieve_context.assert_called_once_with(
            "What is revenue?", k=10
        )


if __name__ == "__main__":
    unittest.main()
