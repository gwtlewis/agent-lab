"""Unit tests for RAG Retriever module"""

import unittest
from unittest.mock import Mock, patch

from rag_retriever import RAGRetriever


class TestRAGRetriever(unittest.TestCase):
    """Test cases for RAGRetriever class"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_embeddings = Mock()
        self.mock_embeddings.embed_query = Mock(return_value=[0.1] * 1536)
        self.mock_embeddings.embed_documents = Mock(
            return_value=[[0.1] * 1536, [0.2] * 1536]
        )
        self.db_url = "postgresql://user:pass@localhost/test"

    @patch("rag_retriever.psycopg2.connect")
    def test_connection_success(self, mock_connect):
        """Test successful database connection"""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        retriever = RAGRetriever(self.db_url, self.mock_embeddings)

        mock_connect.assert_called_once_with(self.db_url)
        self.assertEqual(retriever.conn, mock_conn)
        retriever.conn = None

    @patch("rag_retriever.psycopg2.connect")
    def test_connection_failure(self, mock_connect):
        """Test database connection failure"""
        mock_connect.side_effect = Exception("Connection failed")

        with self.assertRaises(Exception) as context:
            RAGRetriever(self.db_url, self.mock_embeddings)

        self.assertIn("Failed to connect", str(context.exception))

    @patch("rag_retriever.psycopg2.connect")
    def test_retrieve_context_empty_query(self, mock_connect):
        """Test retrieve with empty query"""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        retriever = RAGRetriever(self.db_url, self.mock_embeddings)

        with self.assertRaises(ValueError) as context:
            retriever.retrieve_context("")

        self.assertIn("Query cannot be empty", str(context.exception))

    @patch("rag_retriever.psycopg2.connect")
    def test_retrieve_context_invalid_k(self, mock_connect):
        """Test retrieve with invalid k"""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        retriever = RAGRetriever(self.db_url, self.mock_embeddings)

        with self.assertRaises(ValueError) as context:
            retriever.retrieve_context("test query", k=0)

        self.assertIn("k must be positive", str(context.exception))

    @patch("rag_retriever.psycopg2.connect")
    def test_retrieve_context_success(self, mock_connect):
        """Test successful context retrieval"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (
                1,
                "Test chunk content",
                "Test Document",
                "/path/to.pdf",
                0.95,
                0,
                {"pages": 10},
            ),
            (
                2,
                "Another chunk",
                "Test Document",
                "/path/to.pdf",
                0.85,
                1,
                {"pages": 10},
            ),
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        retriever = RAGRetriever(self.db_url, self.mock_embeddings)
        results = retriever.retrieve_context("financial risks", k=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["document_title"], "Test Document")
        self.assertEqual(results[0]["similarity_score"], 0.95)
        self.assertEqual(results[1]["similarity_score"], 0.85)

    @patch("rag_retriever.psycopg2.connect")
    def test_retrieve_context_no_results(self, mock_connect):
        """Test retrieve with no matching results"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        retriever = RAGRetriever(self.db_url, self.mock_embeddings)
        results = retriever.retrieve_context("obscure query")

        self.assertEqual(len(results), 0)

    @patch("rag_retriever.psycopg2.connect")
    def test_retrieve_by_document(self, mock_connect):
        """Test retrieving chunks by document ID"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (1, "Chunk 1 content", 0),
            (2, "Chunk 2 content", 1),
            (3, "Chunk 3 content", 2),
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        retriever = RAGRetriever(self.db_url, self.mock_embeddings)
        results = retriever.retrieve_by_document(1, limit=3)

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["chunk_id"], 1)
        self.assertEqual(results[0]["chunk_index"], 0)

    @patch("rag_retriever.psycopg2.connect")
    def test_retrieve_document_info_found(self, mock_connect):
        """Test retrieving document info when found"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            1,
            "Test PDF",
            "/path/to.pdf",
            {"pages": 10},
            "2024-01-01",
            25,
        )
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        retriever = RAGRetriever(self.db_url, self.mock_embeddings)
        result = retriever.retrieve_document_info(1)

        self.assertIsNotNone(result)
        self.assertEqual(result["doc_id"], 1)
        self.assertEqual(result["title"], "Test PDF")
        self.assertEqual(result["chunk_count"], 25)

    @patch("rag_retriever.psycopg2.connect")
    def test_retrieve_document_info_not_found(self, mock_connect):
        """Test retrieving document info when not found"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        retriever = RAGRetriever(self.db_url, self.mock_embeddings)
        result = retriever.retrieve_document_info(999)

        self.assertIsNone(result)

    @patch("rag_retriever.psycopg2.connect")
    def test_search_by_title_found(self, mock_connect):
        """Test searching by title when found"""
        mock_conn = Mock()
        mock_cursor = Mock()

        # First query returns doc_id
        mock_cursor.fetchone.side_effect = [
            (1,),  # First call in search_by_title
            (
                1,
                "Test PDF",
                "/path/to.pdf",
                {"pages": 10},
                "2024-01-01",
                25,
            ),  # Second call in retrieve_document_info
        ]

        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        retriever = RAGRetriever(self.db_url, self.mock_embeddings)
        result = retriever.search_by_title("Test PDF")

        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Test PDF")

    @patch("rag_retriever.psycopg2.connect")
    def test_search_by_title_not_found(self, mock_connect):
        """Test searching by title when not found"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        retriever = RAGRetriever(self.db_url, self.mock_embeddings)
        result = retriever.search_by_title("Nonexistent PDF")

        self.assertIsNone(result)

    @patch("rag_retriever.psycopg2.connect")
    def test_get_stats(self, mock_connect):
        """Test retrieving statistics"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (5, 125, 0)  # 5 docs, 125 chunks
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        retriever = RAGRetriever(self.db_url, self.mock_embeddings)
        stats = retriever.get_stats()

        self.assertEqual(stats["total_documents"], 5)
        self.assertEqual(stats["total_chunks"], 125)

    @patch("rag_retriever.psycopg2.connect")
    def test_retrieve_context_with_threshold(self, mock_connect):
        """Test retrieve with similarity threshold"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (1, "Test chunk", "Test Document", "/path/to.pdf", 0.95, 0, {})
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        retriever = RAGRetriever(self.db_url, self.mock_embeddings)
        results = retriever.retrieve_context("query", k=5, similarity_threshold=0.8)

        self.assertEqual(len(results), 1)
        self.assertGreaterEqual(results[0]["similarity_score"], 0.8)


if __name__ == "__main__":
    unittest.main()
