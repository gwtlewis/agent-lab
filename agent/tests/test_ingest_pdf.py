"""Comprehensive tests for ingest_pdf.py CLI module"""

import argparse
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import scripts.ingest_pdf as ingest_pdf


class TestBuildDbUrl(unittest.TestCase):
    """Test database URL building"""

    def test_build_db_url_default(self):
        """Test building URL with default values"""
        url = ingest_pdf.build_db_url("localhost", 5432, "postgres", "password", "mydb")
        self.assertEqual(url, "postgresql://postgres:password@localhost:5432/mydb")

    def test_build_db_url_custom_host(self):
        """Test building URL with custom host"""
        url = ingest_pdf.build_db_url("db.example.com", 5432, "user", "pass", "db")
        self.assertEqual(url, "postgresql://user:pass@db.example.com:5432/db")

    def test_build_db_url_custom_port(self):
        """Test building URL with custom port"""
        url = ingest_pdf.build_db_url("localhost", 6543, "postgres", "password", "mydb")
        self.assertIn(":6543", url)


class TestGetEmbeddingsValidation(unittest.TestCase):
    """Test embeddings validation"""

    def test_invalid_provider(self):
        """Test error with invalid provider"""
        with self.assertRaises(ValueError):
            ingest_pdf.get_embeddings_instance("invalid")

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    def test_openai_not_configured(self):
        """Test error when OpenAI not configured"""
        with self.assertRaises(ValueError):
            ingest_pdf.get_embeddings_instance("openai")


class TestIngestSinglePdf(unittest.TestCase):
    """Test single PDF ingestion"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_args = argparse.Namespace(
            db_host="localhost",
            db_port=5432,
            db_user="postgres",
            db_password="postgres",
            db_name="postgres",
            embeddings="ollama",
            title=None,
            verbose=False,
        )

    def test_pdf_not_found(self):
        """Test error when PDF file not found"""
        with self.assertRaises(FileNotFoundError):
            ingest_pdf.ingest_single_pdf("/nonexistent/file.pdf", self.mock_args)

    def test_not_pdf_file(self):
        """Test error when file is not PDF"""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with self.assertRaises(ValueError):
                ingest_pdf.ingest_single_pdf(tmp_path, self.mock_args)
        finally:
            os.unlink(tmp_path)

    @patch("scripts.ingest_pdf.PDFIngestor")
    @patch("scripts.ingest_pdf.get_embeddings_instance")
    def test_ingest_success(self, mock_get_emb, mock_ingestor_class):
        """Test successful PDF ingestion"""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            mock_ingestor = Mock()
            mock_ingestor.ingest_pdf.return_value = {
                "doc_id": 1,
                "title": "test",
                "pages": 10,
                "chunks": 50,
                "status": "success",
            }
            mock_ingestor_class.return_value = mock_ingestor
            mock_get_emb.return_value = Mock()

            result = ingest_pdf.ingest_single_pdf(tmp_path, self.mock_args)

            self.assertEqual(result["doc_id"], 1)
            self.assertEqual(result["pages"], 10)
        finally:
            os.unlink(tmp_path)


class TestListDocuments(unittest.TestCase):
    """Test document listing"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_args = argparse.Namespace(
            db_host="localhost",
            db_port=5432,
            db_user="postgres",
            db_password="postgres",
            db_name="postgres",
            embeddings="ollama",
        )

    @patch("scripts.ingest_pdf.PDFIngestor")
    @patch("scripts.ingest_pdf.get_embeddings_instance")
    def test_list_success(self, mock_get_emb, mock_ingestor_class):
        """Test successful document listing"""
        mock_ingestor = Mock()
        mock_ingestor.list_documents.return_value = [
            {"id": 1, "title": "Report", "metadata": {"page_count": 10}}
        ]
        mock_ingestor_class.return_value = mock_ingestor
        mock_get_emb.return_value = Mock()

        documents = ingest_pdf.list_documents(self.mock_args)

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["id"], 1)


class TestDeleteDocument(unittest.TestCase):
    """Test document deletion"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_args = argparse.Namespace(
            db_host="localhost",
            db_port=5432,
            db_user="postgres",
            db_password="postgres",
            db_name="postgres",
            embeddings="ollama",
        )

    @patch("scripts.ingest_pdf.PDFIngestor")
    @patch("scripts.ingest_pdf.get_embeddings_instance")
    def test_delete_success(self, mock_get_emb, mock_ingestor_class):
        """Test successful document deletion"""
        mock_ingestor = Mock()
        mock_ingestor.delete_document.return_value = True
        mock_ingestor_class.return_value = mock_ingestor
        mock_get_emb.return_value = Mock()

        success = ingest_pdf.delete_document(1, self.mock_args)

        self.assertTrue(success)


if __name__ == "__main__":
    unittest.main()
