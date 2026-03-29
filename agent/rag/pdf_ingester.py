"""PDF Ingestion module for financial documents into pgvector"""

import os
from typing import List, Optional

import psycopg2
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from psycopg2.extras import execute_values


class PDFIngestor:
    """Ingests PDF files into PostgreSQL with pgvector embeddings"""

    def __init__(self, db_url: str, embeddings):
        """
        Initialize PDFIngestor

        Args:
            db_url: PostgreSQL connection string
            embeddings: LangChain embeddings object (OpenAI or Ollama)
        """
        self.db_url = db_url
        self.embeddings = embeddings
        self.conn = None
        self._connect()

    def _connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(self.db_url)
            print(f"✓ Connected to database")
        except Exception as e:
            raise Exception(f"Failed to connect to database: {e}")

    def _verify_tables(self):
        """Verify required tables exist"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'financial_docs'
                    )
                """)
                if not cursor.fetchone()[0]:
                    raise Exception(
                        "financial_docs table not found. Run init-scripts/01-vectors.sql"
                    )

                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'document_chunks'
                    )
                """)
                if not cursor.fetchone()[0]:
                    raise Exception(
                        "document_chunks table not found. Run init-scripts/01-vectors.sql"
                    )
        except psycopg2.Error as e:
            raise Exception(f"Table verification failed: {e}")

    def ingest_pdf(self, pdf_path: str, title: Optional[str] = None) -> dict:
        """
        Load PDF, chunk it, embed, and store in pgvector

        Args:
            pdf_path: Path to PDF file
            title: Optional title for the document

        Returns:
            Dictionary with ingestion results

        Raises:
            FileNotFoundError: If PDF file not found
            Exception: If ingestion fails
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        self._verify_tables()

        try:
            # 1. Load PDF
            print(f"Loading PDF: {pdf_path}")
            loader = PyPDFLoader(pdf_path)
            documents = loader.load()

            if not documents:
                raise ValueError(f"No content extracted from PDF: {pdf_path}")

            # 2. Split into chunks
            print(f"Splitting {len(documents)} pages into chunks...")
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, chunk_overlap=200, separators=["\n\n", "\n", " ", ""]
            )
            chunks = splitter.split_documents(documents)

            if not chunks:
                raise ValueError("No chunks created from PDF")

            # 3. Generate embeddings using LangChain API
            print(f"Generating embeddings for {len(chunks)} chunks...")
            chunk_texts = [chunk.page_content for chunk in chunks]

            # Use LangChain embeddings API
            try:
                embeddings_list = self.embeddings.embed_documents(chunk_texts)
                if len(embeddings_list) != len(chunks):
                    raise ValueError(
                        f"Mismatch between chunks ({len(chunks)}) and embeddings ({len(embeddings_list)})"
                    )
            except Exception as e:
                raise Exception(f"Failed to generate embeddings: {e}")

            # 4. Store in database
            print("Storing in database...")

            doc_title = title or os.path.splitext(os.path.basename(pdf_path))[0]

            import json

            with self.conn.cursor() as cursor:
                # Insert document record
                cursor.execute(
                    """INSERT INTO financial_docs (title, source_file, content, embedding, metadata)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                    (
                        doc_title,
                        pdf_path,
                        "".join([c.page_content for c in chunks[:5]]),
                        embeddings_list[0] if embeddings_list else None,
                        json.dumps(
                            {
                                "page_count": len(documents),
                                "chunk_count": len(chunks),
                                "file_name": os.path.basename(pdf_path),
                            }
                        ),
                    ),
                )
                doc_id = cursor.fetchone()[0]

                # Insert chunks
                chunk_values = [
                    (doc_id, i, chunk.page_content, embedding)
                    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings_list))
                ]

                execute_values(
                    cursor,
                    """INSERT INTO document_chunks (doc_id, chunk_index, chunk_text, embedding)
                       VALUES %s""",
                    chunk_values,
                )

            self.conn.commit()

            result = {
                "doc_id": doc_id,
                "title": doc_title,
                "pages": len(documents),
                "chunks": len(chunks),
                "status": "success",
            }

            print(f"✓ Successfully ingested {len(chunks)} chunks from {pdf_path}")
            return result

        except (ValueError, FileNotFoundError) as e:
            self.conn.rollback()
            raise
        except Exception as e:
            self.conn.rollback()
            raise Exception(f"PDF ingestion failed: {e}")

    def list_documents(self) -> List[dict]:
        """List all ingested documents"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, title, source_file, metadata, created_at
                    FROM financial_docs
                    ORDER BY created_at DESC
                """)

                documents = []
                for row in cursor.fetchall():
                    documents.append(
                        {
                            "id": row[0],
                            "title": row[1],
                            "source_file": row[2],
                            "metadata": row[3],
                            "created_at": row[4],
                        }
                    )

            return documents

        except psycopg2.Error as e:
            raise Exception(f"Failed to list documents: {e}")

    def delete_document(self, doc_id: int) -> bool:
        """Delete a document and its chunks"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("DELETE FROM financial_docs WHERE id = %s", (doc_id,))
                deleted = cursor.rowcount > 0
            self.conn.commit()
            return deleted
        except psycopg2.Error as e:
            self.conn.rollback()
            raise Exception(f"Failed to delete document: {e}")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("✓ Database connection closed")
