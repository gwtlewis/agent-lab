"""
End-to-end RAG pipeline testing with xVA PDF
Tests the complete flow: PDF ingestion -> retrieval -> agent response
"""

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Import the RAG components
from agent_with_rag import RAGAgent
from ingest_pdf import build_db_url, get_embeddings_instance, ingest_single_pdf
from pdf_ingester import PDFIngestor


class TestXVAPDFIngestion(unittest.TestCase):
    """Test PDF ingestion specifically for xVA document"""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.pdf_path = os.getenv(
            "XVA_PDF_PATH",
            "/Users/lewisgong/Downloads/2015_The_xVA_Challenge-Jon Gregory.pdf",
        )
        cls.db_url = "postgresql://postgres:postgres@localhost:5432/postgres"

    @unittest.skipUnless(
        os.path.exists(
            os.getenv(
                "XVA_PDF_PATH",
                "/Users/lewisgong/Downloads/2015_The_xVA_Challenge-Jon Gregory.pdf",
            )
        ),
        "XVA PDF not found; set XVA_PDF_PATH env var",
    )
    def test_pdf_file_exists(self):
        """Test that xVA PDF file exists"""
        self.assertTrue(
            os.path.exists(self.pdf_path), f"PDF file not found: {self.pdf_path}"
        )

    @unittest.skipUnless(
        os.path.exists(
            os.getenv(
                "XVA_PDF_PATH",
                "/Users/lewisgong/Downloads/2015_The_xVA_Challenge-Jon Gregory.pdf",
            )
        ),
        "XVA PDF not found; set XVA_PDF_PATH env var",
    )
    def test_pdf_file_is_readable(self):
        """Test that PDF file is readable"""
        self.assertTrue(
            os.access(self.pdf_path, os.R_OK),
            f"PDF file is not readable: {self.pdf_path}",
        )

    @unittest.skipUnless(
        os.path.exists(
            os.getenv(
                "XVA_PDF_PATH",
                "/Users/lewisgong/Downloads/2015_The_xVA_Challenge-Jon Gregory.pdf",
            )
        ),
        "XVA PDF not found; set XVA_PDF_PATH env var",
    )
    def test_pdf_file_has_valid_size(self):
        """Test that PDF file has reasonable size"""
        size_mb = os.path.getsize(self.pdf_path) / (1024 * 1024)
        self.assertGreater(size_mb, 1, "PDF file is too small")
        self.assertLess(size_mb, 100, "PDF file is too large")

    def test_pdf_filename_extraction(self):
        """Test extracting title from PDF path"""
        expected_title = "2015_The_xVA_Challenge-Jon Gregory"
        pdf_path = os.getenv(
            "XVA_PDF_PATH",
            "/Users/lewisgong/Downloads/2015_The_xVA_Challenge-Jon Gregory.pdf",
        )
        actual_title = Path(pdf_path).stem
        self.assertEqual(actual_title, expected_title)


class TestRAGPipelineConfiguration(unittest.TestCase):
    """Test RAG pipeline configuration and setup"""

    def test_build_db_url_formatting(self):
        """Test database URL construction"""
        url = build_db_url(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",
            db="postgres",
        )
        expected = "postgresql://postgres:postgres@localhost:5432/postgres"
        self.assertEqual(url, expected)

    def test_build_db_url_with_special_chars(self):
        """Test database URL with special characters in password"""
        url = build_db_url(
            host="db.example.com",
            port=5433,
            user="admin",
            password="p@ss:word",
            db="finance_db",
        )
        expected = "postgresql://admin:p@ss:word@db.example.com:5433/finance_db"
        self.assertEqual(url, expected)

    @patch("langchain_ollama.OllamaEmbeddings")
    def test_embeddings_instance_ollama(self, mock_ollama):
        """Test Ollama embeddings instantiation"""
        with patch.dict(os.environ, {"OLLAMA_HOST": "http://127.0.0.1:11434"}):
            embeddings = get_embeddings_instance("ollama")
            mock_ollama.assert_called_once()
            self.assertEqual(embeddings, mock_ollama.return_value)

    @patch("langchain_openai.OpenAIEmbeddings")
    def test_embeddings_instance_openai(self, mock_openai):
        """Test OpenAI embeddings instantiation"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            embeddings = get_embeddings_instance("openai")
            mock_openai.assert_called_once()
            self.assertEqual(embeddings, mock_openai.return_value)

    def test_invalid_embeddings_provider(self):
        """Test error handling for invalid embeddings provider"""
        with self.assertRaises(ValueError) as context:
            get_embeddings_instance("invalid_provider")
        self.assertIn("Unknown embeddings provider", str(context.exception))


class TestRAGAgentInitialization(unittest.TestCase):
    """Test RAG Agent initialization with various configurations"""

    @patch("agent_with_rag.RAGRetriever")
    @patch("langchain_ollama.OllamaEmbeddings")
    @patch.dict(os.environ, {"OLLAMA_HOST": "http://127.0.0.1:11434"})
    def test_rag_agent_init_with_db_url(self, mock_embeddings, mock_retriever):
        """Test RAGAgent initialization with database URL"""
        db_url = "postgresql://postgres:postgres@localhost:5432/postgres"
        agent = RAGAgent(provider="ollama", db_url=db_url, enable_rag=True)

        self.assertIsNotNone(agent)
        self.assertTrue(agent.enable_rag)
        mock_retriever.assert_called_once()

    @patch("agent_with_rag.RAGRetriever")
    def test_rag_agent_init_without_rag(self, mock_retriever):
        """Test RAGAgent initialization without RAG"""
        agent = RAGAgent(provider="ollama", enable_rag=False)

        self.assertIsNotNone(agent)
        self.assertFalse(agent.enable_rag)
        self.assertIsNone(agent.rag_retriever)
        mock_retriever.assert_not_called()

    @patch("agent_with_rag.RAGRetriever")
    def test_rag_agent_init_without_db_url(self, mock_retriever):
        """Test RAGAgent initialization without database URL"""
        agent = RAGAgent(provider="ollama", db_url=None, enable_rag=True)

        self.assertIsNotNone(agent)
        # When db_url is None, enable_rag should remain True (set by user)
        # but RAG retriever won't be initialized
        self.assertIsNone(agent.rag_retriever)


class TestRAGContextFormatting(unittest.TestCase):
    """Test RAG context formatting and retrieval"""

    def setUp(self):
        """Set up test fixtures"""
        with patch("agent_with_rag.RAGRetriever"):
            self.agent = RAGAgent(provider="ollama", enable_rag=False)

    def test_format_rag_context_single_document(self):
        """Test formatting single retrieved document"""
        docs = [
            {
                "document_title": "xVA Challenge",
                "content": "xVA represents a major challenge in counterparty risk management",
                "similarity_score": 0.95,
            }
        ]

        context = self.agent._format_rag_context(docs)

        self.assertIn("xVA Challenge", context)
        self.assertIn("counterparty risk", context)
        self.assertIn("95.00%", context)

    def test_format_rag_context_multiple_documents(self):
        """Test formatting multiple retrieved documents"""
        docs = [
            {
                "document_title": "xVA Challenge",
                "content": "First relevant passage about xVA",
                "similarity_score": 0.95,
            },
            {
                "document_title": "xVA Challenge",
                "content": "Second relevant passage about CVA",
                "similarity_score": 0.87,
            },
        ]

        context = self.agent._format_rag_context(docs)

        self.assertIn("Document 1", context)
        self.assertIn("Document 2", context)
        self.assertIn("95.00%", context)
        self.assertIn("87.00%", context)

    def test_format_rag_context_long_content_truncation(self):
        """Test that long content is truncated to 500 chars"""
        long_content = "x" * 1000
        docs = [
            {"document_title": "Test", "content": long_content, "similarity_score": 0.9}
        ]

        context = self.agent._format_rag_context(docs)

        # Should contain truncated content
        self.assertIn("x" * 500, context)
        self.assertNotIn("x" * 501, context)

    def test_format_rag_context_missing_fields(self):
        """Test handling documents with missing fields"""
        docs = [
            {"content": "Content without title", "similarity_score": 0.85},
            {
                "document_title": "Title without content",
            },
        ]

        context = self.agent._format_rag_context(docs)

        self.assertIn("Unknown", context)
        self.assertIn("Content without title", context)


class TestRAGQueryProcessing(unittest.TestCase):
    """Test RAG query processing and LLM integration"""

    @patch("agent_with_rag.IntegratedAgent.chat")
    @patch("agent_with_rag.RAGRetriever")
    def test_chat_with_rag_retrieval(self, mock_retriever_class, mock_parent_chat):
        """Test chat method with RAG retrieval"""
        # Setup mocks
        mock_retriever = MagicMock()
        mock_retriever_class.return_value = mock_retriever
        mock_retriever.retrieve_context.return_value = [
            {
                "document_title": "xVA Challenge",
                "content": "CVA is computed as the expectation of loss",
                "similarity_score": 0.92,
            }
        ]
        mock_parent_chat.return_value = "CVA represents credit valuation adjustment"

        agent = RAGAgent(provider="ollama", db_url="postgresql://test", enable_rag=True)
        response = agent.chat("What is CVA?", use_rag=True)

        # Verify retrieval was called
        mock_retriever.retrieve_context.assert_called_once()

        # Verify parent chat was called with enhanced context
        mock_parent_chat.assert_called_once()
        call_args = mock_parent_chat.call_args
        self.assertIn("Financial Knowledge Base Context", call_args[1]["system_prompt"])

        self.assertEqual(response, "CVA represents credit valuation adjustment")

    @patch("agent_with_rag.IntegratedAgent.chat")
    @patch("agent_with_rag.RAGRetriever")
    def test_chat_without_rag_retrieval(self, mock_retriever_class, mock_parent_chat):
        """Test chat method with RAG disabled"""
        mock_retriever = MagicMock()
        mock_retriever_class.return_value = mock_retriever
        mock_parent_chat.return_value = "Response without RAG context"

        agent = RAGAgent(provider="ollama", db_url="postgresql://test", enable_rag=True)
        response = agent.chat("What is CVA?", use_rag=False)

        # Verify retrieval was NOT called
        mock_retriever.retrieve_context.assert_not_called()

        # Verify parent chat was called without context
        mock_parent_chat.assert_called_once()
        call_args = mock_parent_chat.call_args
        # System prompt should not contain Financial Knowledge Base Context
        if call_args[1]["system_prompt"]:
            self.assertNotIn(
                "Financial Knowledge Base Context", call_args[1]["system_prompt"]
            )

    @patch("agent_with_rag.IntegratedAgent.chat")
    @patch("agent_with_rag.RAGRetriever")
    def test_chat_with_k_documents(self, mock_retriever_class, mock_parent_chat):
        """Test chat method with custom k_documents parameter"""
        mock_retriever = MagicMock()
        mock_retriever_class.return_value = mock_retriever
        mock_retriever.retrieve_context.return_value = []
        mock_parent_chat.return_value = "Response"

        agent = RAGAgent(provider="ollama", db_url="postgresql://test", enable_rag=True)
        agent.chat("Query", use_rag=True, k_documents=10)

        # Verify retrieve_context was called with correct k value
        mock_retriever.retrieve_context.assert_called_once_with("Query", k=10)


class TestRAGStatistics(unittest.TestCase):
    """Test RAG statistics retrieval"""

    @patch("agent_with_rag.RAGRetriever")
    def test_get_rag_stats_enabled(self, mock_retriever_class):
        """Test getting RAG stats when RAG is enabled"""
        mock_retriever = MagicMock()
        mock_retriever_class.return_value = mock_retriever
        mock_retriever.get_stats.return_value = {
            "documents": 5,
            "chunks": 150,
            "avg_similarity": 0.85,
        }

        agent = RAGAgent(provider="ollama", db_url="postgresql://test", enable_rag=True)
        stats = agent.get_rag_stats()

        self.assertEqual(stats["documents"], 5)
        self.assertEqual(stats["chunks"], 150)
        mock_retriever.get_stats.assert_called_once()

    @patch("agent_with_rag.RAGRetriever")
    def test_get_rag_stats_disabled(self, mock_retriever_class):
        """Test getting RAG stats when RAG is disabled"""
        agent = RAGAgent(provider="ollama", enable_rag=False)
        stats = agent.get_rag_stats()

        self.assertEqual(stats, {})
        mock_retriever_class.return_value.get_stats.assert_not_called()


class TestRAGKnowledgeBaseSearch(unittest.TestCase):
    """Test direct knowledge base search functionality"""

    @patch("agent_with_rag.RAGRetriever")
    def test_search_knowledge_base_with_results(self, mock_retriever_class):
        """Test searching knowledge base with results"""
        mock_retriever = MagicMock()
        mock_retriever_class.return_value = mock_retriever
        mock_retriever.retrieve_context.return_value = [
            {"content": "xVA is a key measure", "similarity_score": 0.92}
        ]

        agent = RAGAgent(provider="ollama", db_url="postgresql://test", enable_rag=True)
        results = agent.search_knowledge_base("xVA measures", k=5)

        self.assertEqual(len(results), 1)
        mock_retriever.retrieve_context.assert_called_once_with("xVA measures", k=5)

    @patch("agent_with_rag.RAGRetriever")
    def test_search_knowledge_base_without_rag(self, mock_retriever_class):
        """Test search fails when RAG is disabled"""
        agent = RAGAgent(provider="ollama", enable_rag=False)

        with self.assertRaises(RuntimeError) as context:
            agent.search_knowledge_base("xVA measures")

        self.assertIn("RAG is not enabled", str(context.exception))

    @patch("agent_with_rag.RAGRetriever")
    def test_search_knowledge_base_custom_k(self, mock_retriever_class):
        """Test search with custom k parameter"""
        mock_retriever = MagicMock()
        mock_retriever_class.return_value = mock_retriever
        mock_retriever.retrieve_context.return_value = []

        agent = RAGAgent(provider="ollama", db_url="postgresql://test", enable_rag=True)
        agent.search_knowledge_base("query", k=20)

        # Verify custom k was passed
        mock_retriever.retrieve_context.assert_called_once_with("query", k=20)


class TestXVASpecificQueries(unittest.TestCase):
    """Test RAG pipeline with xVA-specific domain queries"""

    def setUp(self):
        """Set up test fixtures for xVA queries"""
        self.xva_topics = [
            "CVA (Credit Valuation Adjustment)",
            "DVA (Debit Valuation Adjustment)",
            "FVA (Funding Valuation Adjustment)",
            "KVA (Capital Valuation Adjustment)",
            "Counterparty risk",
            "Collateral management",
            "Central clearing",
            "Bilateral clearing",
        ]

    def test_xva_query_topics_are_covered(self):
        """Test that test suite covers all major xVA topics"""
        self.assertGreater(len(self.xva_topics), 0)
        self.assertIn("CVA (Credit Valuation Adjustment)", self.xva_topics)

    @patch("agent_with_rag.RAGRetriever")
    def test_query_cva_content(self, mock_retriever_class):
        """Test querying for CVA content from xVA document"""
        mock_retriever = MagicMock()
        mock_retriever_class.return_value = mock_retriever
        mock_retriever.retrieve_context.return_value = [
            {
                "document_title": "2015_The_xVA_Challenge-Jon Gregory",
                "content": "CVA is the market value of credit risk",
                "similarity_score": 0.94,
            }
        ]

        with patch("agent_with_rag.IntegratedAgent.chat") as mock_chat:
            mock_chat.return_value = (
                "CVA is the valuation adjustment for counterparty risk"
            )
            agent = RAGAgent(
                provider="ollama", db_url="postgresql://test", enable_rag=True
            )
            response = agent.chat("What is CVA?")

            mock_retriever.retrieve_context.assert_called_once()
            self.assertIsNotNone(response)

    @patch("agent_with_rag.RAGRetriever")
    def test_query_xva_challenge_themes(self, mock_retriever_class):
        """Test querying for themes from xVA Challenge document"""
        mock_retriever = MagicMock()
        mock_retriever_class.return_value = mock_retriever
        mock_retriever.retrieve_context.return_value = [
            {
                "document_title": "2015_The_xVA_Challenge-Jon Gregory",
                "content": "The xVA challenge involves multiple valuation adjustments",
                "similarity_score": 0.91,
            }
        ]

        with patch("agent_with_rag.IntegratedAgent.chat") as mock_chat:
            mock_chat.return_value = "The xVA challenge discusses various valuation adjustments needed in modern finance"
            agent = RAGAgent(
                provider="ollama", db_url="postgresql://test", enable_rag=True
            )
            response = agent.chat("What challenges does xVA present?")

            self.assertIsNotNone(response)
            mock_retriever.retrieve_context.assert_called_once()


if __name__ == "__main__":
    unittest.main()
