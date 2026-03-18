"""RAG Retriever module for querying pgvector embeddings"""

from typing import Dict, List, Optional

import psycopg2


class RAGRetriever:
    """Retrieves relevant documents from pgvector for RAG"""

    def __init__(self, db_url: str, embeddings):
        """
        Initialize RAG Retriever

        Args:
            db_url: PostgreSQL connection string
            embeddings: LangChain embeddings object
        """
        self.db_url = db_url
        self.embeddings = embeddings
        self.conn = None
        self._connect()

    def _connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(self.db_url)
            print(f"✓ RAG Retriever connected to database")
        except Exception as e:
            raise Exception(f"Failed to connect to database: {e}")

    def retrieve_context(
        self, query: str, k: int = 5, similarity_threshold: float = 0.1
    ) -> List[Dict]:
        """
        Retrieve relevant document chunks for a query using semantic similarity

        Args:
            query: Query text to find similar documents for
            k: Number of top results to return
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            List of dictionaries with document chunks and metadata

        Raises:
            Exception: If retrieval fails
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        if k <= 0:
            raise ValueError("k must be positive")

        try:
            # Generate embedding for query using LangChain embeddings
            query_embedding = self.embeddings.embed_query(query)

            cursor = self.conn.cursor()

            # Search for similar chunks using cosine similarity
            # Use <=> operator for cosine similarity (returns -1 to 1, we want 0 to 1)
            cursor.execute(
                """
                SELECT 
                    dc.id,
                    dc.chunk_text,
                    fd.title,
                    fd.source_file,
                    (dc.embedding <=> %s::vector) as similarity,
                    dc.chunk_index,
                    fd.metadata
                FROM document_chunks dc
                JOIN financial_docs fd ON dc.doc_id = fd.id
                WHERE (dc.embedding <=> %s::vector) > %s
                ORDER BY (dc.embedding <=> %s::vector) DESC
                LIMIT %s
            """,
                (
                    query_embedding,
                    query_embedding,
                    similarity_threshold,
                    query_embedding,
                    k,
                ),
            )

            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "chunk_id": row[0],
                        "content": row[1],
                        "document_title": row[2],
                        "source_file": row[3],
                        "similarity_score": float(row[4]),
                        "chunk_index": row[5],
                        "metadata": row[6],
                    }
                )

            cursor.close()
            return results

        except psycopg2.Error as e:
            raise Exception(f"Failed to retrieve context: {e}")

    def retrieve_by_document(self, doc_id: int, limit: int = 10) -> List[Dict]:
        """
        Retrieve all chunks from a specific document

        Args:
            doc_id: Document ID
            limit: Maximum number of chunks to return

        Returns:
            List of document chunks

        Raises:
            Exception: If retrieval fails
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute(
                """
                SELECT 
                    id,
                    chunk_text,
                    chunk_index
                FROM document_chunks
                WHERE doc_id = %s
                ORDER BY chunk_index
                LIMIT %s
            """,
                (doc_id, limit),
            )

            results = []
            for row in cursor.fetchall():
                results.append(
                    {"chunk_id": row[0], "content": row[1], "chunk_index": row[2]}
                )

            cursor.close()
            return results

        except psycopg2.Error as e:
            raise Exception(f"Failed to retrieve document chunks: {e}")

    def retrieve_document_info(self, doc_id: int) -> Optional[Dict]:
        """
        Get metadata about a specific document

        Args:
            doc_id: Document ID

        Returns:
            Dictionary with document metadata or None if not found

        Raises:
            Exception: If retrieval fails
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute(
                """
                SELECT 
                    id,
                    title,
                    source_file,
                    metadata,
                    created_at,
                    (SELECT COUNT(*) FROM document_chunks WHERE doc_id = %s) as chunk_count
                FROM financial_docs
                WHERE id = %s
            """,
                (doc_id, doc_id),
            )

            row = cursor.fetchone()
            cursor.close()

            if not row:
                return None

            return {
                "doc_id": row[0],
                "title": row[1],
                "source_file": row[2],
                "metadata": row[3],
                "created_at": row[4],
                "chunk_count": row[5],
            }

        except psycopg2.Error as e:
            raise Exception(f"Failed to retrieve document info: {e}")

    def search_by_title(self, title: str) -> Optional[Dict]:
        """
        Find a document by title

        Args:
            title: Document title to search for

        Returns:
            Document info or None if not found

        Raises:
            Exception: If search fails
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute(
                """
                SELECT id FROM financial_docs 
                WHERE title ILIKE %s
                LIMIT 1
            """,
                (f"%{title}%",),
            )

            row = cursor.fetchone()
            cursor.close()

            if row:
                return self.retrieve_document_info(row[0])
            return None

        except psycopg2.Error as e:
            raise Exception(f"Failed to search documents: {e}")

    def get_stats(self) -> Dict:
        """
        Get statistics about indexed documents

        Returns:
            Dictionary with statistics

        Raises:
            Exception: If query fails
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT fd.id) as total_documents,
                    COUNT(dc.id) as total_chunks,
                    SUM(COALESCE((fd.metadata->>'chunk_count')::integer, 0)) as total_metadata_chunks
                FROM financial_docs fd
                LEFT JOIN document_chunks dc ON fd.id = dc.doc_id
            """)

            row = cursor.fetchone()
            cursor.close()

            return {
                "total_documents": row[0] or 0,
                "total_chunks": row[1] or 0,
                "total_metadata_chunks": row[2] or 0,
            }

        except psycopg2.Error as e:
            raise Exception(f"Failed to get statistics: {e}")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("✓ RAG Retriever connection closed")
