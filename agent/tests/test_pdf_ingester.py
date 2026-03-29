"""Unit tests for PDF Ingester module"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

from rag.pdf_ingester import PDFIngestor


class TestPDFIngestor(unittest.TestCase):
    """Test cases for PDFIngestor class"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_embeddings = Mock()
        self.mock_embeddings.embed_documents = Mock(
            return_value=[[0.1] * 1536, [0.2] * 1536]
        )
        self.db_url = "postgresql://user:pass@localhost/test"

    @patch("rag.pdf_ingester.psycopg2.connect")
    def test_connection_success(self, mock_connect):
        """Test successful database connection"""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        ingester = PDFIngestor(self.db_url, self.mock_embeddings)

        mock_connect.assert_called_once_with(self.db_url)
        self.assertEqual(ingester.conn, mock_conn)
        ingester.conn = None  # Cleanup

    @patch("rag.pdf_ingester.psycopg2.connect")
    def test_connection_failure(self, mock_connect):
        """Test database connection failure"""
        mock_connect.side_effect = Exception("Connection failed")

        with self.assertRaises(Exception) as context:
            PDFIngestor(self.db_url, self.mock_embeddings)

        self.assertIn("Failed to connect", str(context.exception))

    @patch("rag.pdf_ingester.psycopg2.connect")
    def test_verify_tables_missing(self, mock_connect):
        """Test table verification with missing tables"""
        mock_conn = Mock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (False,)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        ingester = PDFIngestor(self.db_url, self.mock_embeddings)

        with self.assertRaises(Exception) as context:
            ingester._verify_tables()

        self.assertIn("financial_docs table not found", str(context.exception))

    @patch("rag.pdf_ingester.PyPDFLoader")
    @patch("rag.pdf_ingester.RecursiveCharacterTextSplitter")
    @patch("rag.pdf_ingester.psycopg2.connect")
    def test_ingest_pdf_file_not_found(self, mock_connect, mock_splitter, mock_loader):
        """Test ingestion with non-existent PDF"""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        ingester = PDFIngestor(self.db_url, self.mock_embeddings)

        with self.assertRaises(FileNotFoundError) as context:
            ingester.ingest_pdf("/nonexistent/file.pdf")

        self.assertIn("PDF file not found", str(context.exception))

    @patch("rag.pdf_ingester.execute_values")
    @patch("rag.pdf_ingester.PyPDFLoader")
    @patch("rag.pdf_ingester.RecursiveCharacterTextSplitter")
    @patch("rag.pdf_ingester.psycopg2.connect")
    def test_ingest_pdf_success(
        self, mock_connect, mock_splitter_class, mock_loader_class, mock_execute_values
    ):
        """Test successful PDF ingestion"""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [
            (True,),
            (True,),
            (1,),
        ]  # table exists, table exists, doc_id
        mock_cursor.rowcount = 2
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Mock document loading
        mock_doc = Mock()
        mock_doc.page_content = "Test content"
        mock_loader = Mock()
        mock_loader.load.return_value = [mock_doc, mock_doc]
        mock_loader_class.return_value = mock_loader

        # Mock chunking
        mock_chunk = Mock()
        mock_chunk.page_content = "Chunk content"
        mock_splitter = Mock()
        mock_splitter.split_documents.return_value = [mock_chunk, mock_chunk]
        mock_splitter_class.return_value = mock_splitter

        # Create test PDF file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = f.name

        try:
            ingester = PDFIngestor(self.db_url, self.mock_embeddings)
            result = ingester.ingest_pdf(pdf_path, title="Test PDF")

            # Verify results
            self.assertEqual(result["doc_id"], 1)
            self.assertEqual(result["title"], "Test PDF")
            self.assertEqual(result["pages"], 2)
            self.assertEqual(result["chunks"], 2)
            self.assertEqual(result["status"], "success")

        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

    @patch("rag.pdf_ingester.PyPDFLoader")
    @patch("rag.pdf_ingester.psycopg2.connect")
    def test_ingest_pdf_empty_content(self, mock_connect, mock_loader_class):
        """Test ingestion with empty PDF"""
        mock_conn = Mock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [(True,), (True,)]  # table exists checks
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Mock empty document
        mock_loader = Mock()
        mock_loader.load.return_value = []
        mock_loader_class.return_value = mock_loader

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = f.name

        try:
            ingester = PDFIngestor(self.db_url, self.mock_embeddings)
            with self.assertRaises(ValueError) as context:
                ingester.ingest_pdf(pdf_path)

            self.assertIn("No content extracted", str(context.exception))
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

    @patch("rag.pdf_ingester.psycopg2.connect")
    def test_list_documents_success(self, mock_connect):
        """Test listing documents"""
        mock_conn = Mock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            (1, "Test PDF", "/path/to/pdf", {"pages": 10}, "2024-01-01"),
            (2, "Another PDF", "/path/to/pdf2", {"pages": 5}, "2024-01-02"),
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        ingester = PDFIngestor(self.db_url, self.mock_embeddings)
        docs = ingester.list_documents()

        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0]["title"], "Test PDF")
        self.assertEqual(docs[1]["title"], "Another PDF")

    @patch("rag.pdf_ingester.psycopg2.connect")
    def test_delete_document_success(self, mock_connect):
        """Test deleting a document"""
        mock_conn = Mock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.rowcount = 1
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        ingester = PDFIngestor(self.db_url, self.mock_embeddings)
        result = ingester.delete_document(1)

        self.assertTrue(result)
        mock_conn.commit.assert_called_once()

    @patch("rag.pdf_ingester.psycopg2.connect")
    def test_delete_document_not_found(self, mock_connect):
        """Test deleting non-existent document"""
        mock_conn = Mock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.rowcount = 0
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        ingester = PDFIngestor(self.db_url, self.mock_embeddings)
        result = ingester.delete_document(999)

        self.assertFalse(result)


class TestPDFIngestorIntegration(unittest.TestCase):
    """Integration tests for PDFIngestor (requires database)"""

    def setUp(self):
        """Set up test database connection"""
        self.db_url = os.getenv(
            "TEST_DB_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
        )
        self.mock_embeddings = Mock()
        self.mock_embeddings.embed_documents = Mock(
            return_value=[[0.1] * 1536, [0.2] * 1536]
        )

    @unittest.skipIf(os.getenv("SKIP_INTEGRATION_TESTS"), "Integration tests skipped")
    def test_integration_full_workflow(self):
        """Test full PDF ingestion workflow"""
        try:
            ingester = PDFIngestor(self.db_url, self.mock_embeddings)

            # Verify tables exist
            ingester._verify_tables()

            # List documents (should not raise)
            docs = ingester.list_documents()
            self.assertIsInstance(docs, list)

            ingester.close()
        except Exception as e:
            # Skip integration test if database not available
            if "connect" in str(e).lower():
                self.skipTest("Database not available")
            else:
                raise


if __name__ == "__main__":
    unittest.main()
