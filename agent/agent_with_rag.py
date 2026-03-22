"""RAG-enhanced Agent that integrates financial knowledge from pgvector"""

from typing import Optional

from agent import IntegratedAgent
from langchain_core.messages import HumanMessage, SystemMessage
from rag_retriever import RAGRetriever


class RAGAgent(IntegratedAgent):
    """LangChain Agent enhanced with Retrieval Augmented Generation (RAG)"""

    def __init__(
        self,
        provider: str = "ollama",
        db_url: Optional[str] = None,
        embeddings=None,
        enable_rag: bool = True,
    ):
        """
        Initialize RAG-enhanced Agent

        Args:
            provider: LLM provider ('ollama' or 'openai')
            db_url: PostgreSQL connection string for RAG
            embeddings: LangChain embeddings object (auto-detected if None)
            enable_rag: Whether to enable RAG functionality
        """
        super().__init__(provider)

        self.enable_rag = enable_rag
        self.rag_retriever = None

        if enable_rag and db_url:
            # Auto-detect embeddings if not provided
            if embeddings is None:
                if provider == "openai":
                    import os

                    from langchain_openai import OpenAIEmbeddings

                    embeddings = OpenAIEmbeddings(
                        model="text-embedding-3-small",
                        api_key=os.getenv("OPENAI_API_KEY"),
                    )
                else:
                    import os

                    from langchain_ollama import OllamaEmbeddings

                    embeddings = OllamaEmbeddings(
                        model="nomic-embed-text:latest",
                        base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
                    )

            try:
                self.rag_retriever = RAGRetriever(db_url, embeddings)
                print(
                    "✓ RAG enabled - Agent will use financial knowledge from pgvector"
                )
            except Exception as e:
                print(f"⚠ RAG initialization failed: {e}")
                self.enable_rag = False

    def verify_connection(self) -> bool:
        """Verify both LLM and database connections"""
        # First verify LLM connection
        llm_ok = super().verify_connection()

        if not llm_ok:
            return False

        # Then verify database connection for RAG
        if self.enable_rag:
            try:
                if self.rag_retriever and self.rag_retriever.conn:
                    # Test database connection
                    cursor = self.rag_retriever.conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                    cursor.close()
                    print("✓ Database connection verified for RAG")
                    return True
                else:
                    print("⚠ RAG enabled but database connection failed")
                    return False
            except Exception as e:
                print(f"⚠ Database connection failed: {e}")
                return False

        return True

    def chat(
        self,
        msg: str,
        system_prompt: Optional[str] = None,
        stream: bool = True,
        use_rag: bool = True,
        k_documents: int = 5,
    ) -> str:
        """
        Send a message with optional RAG context

        Args:
            msg: User message
            system_prompt: Optional system prompt
            stream: Whether to stream response
            use_rag: Whether to use RAG for this query
            k_documents: Number of context documents to retrieve

        Returns:
            Agent response as string
        """
        # Retrieve RAG context if enabled
        rag_context = ""
        if use_rag and self.enable_rag and self.rag_retriever:
            try:
                retrieved_docs = self.rag_retriever.retrieve_context(msg, k=k_documents)

                if retrieved_docs:
                    rag_context = self._format_rag_context(retrieved_docs)
                    print(
                        f"\n[RAG] Retrieved {len(retrieved_docs)} relevant document chunks\n"
                    )
            except Exception as e:
                print(f"⚠ RAG retrieval failed: {e}")

        # Build enhanced system prompt with RAG context
        enhanced_system = system_prompt or ""
        if rag_context:
            enhanced_system = f"{enhanced_system}\n\n## Financial Knowledge Base Context:\n{rag_context}".strip()

        # Call parent chat with enhanced prompt
        return super().chat(
            msg,
            system_prompt=enhanced_system if enhanced_system else None,
            stream=stream,
        )

    def _format_rag_context(self, documents: list) -> str:
        """
        Format retrieved documents into context string

        Args:
            documents: List of retrieved document chunks

        Returns:
            Formatted context string
        """
        context_parts = []

        for i, doc in enumerate(documents, 1):
            similarity = doc.get("similarity_score", 0)
            title = doc.get("document_title", "Unknown")
            content = doc.get("content", "")[:500]  # Limit content length

            context_parts.append(
                f"Document {i} ({title}, similarity: {similarity:.2%}):\n{content}"
            )

        return "\n\n".join(context_parts)

    def get_rag_stats(self) -> dict:
        """
        Get statistics about indexed documents

        Returns:
            Dictionary with RAG statistics or empty dict if RAG disabled
        """
        if self.enable_rag and self.rag_retriever:
            try:
                return self.rag_retriever.get_stats()
            except Exception as e:
                print(f"Failed to get RAG stats: {e}")
                return {}
        return {}

    def search_knowledge_base(self, query: str, k: int = 5) -> list:
        """
        Search the financial knowledge base directly

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            List of matching documents
        """
        if not self.enable_rag or not self.rag_retriever:
            raise RuntimeError("RAG is not enabled")

        try:
            return self.rag_retriever.retrieve_context(query, k=k)
        except Exception as e:
            raise Exception(f"Knowledge base search failed: {e}")

    def close(self):
        """Close connections"""
        if self.rag_retriever:
            self.rag_retriever.close()
        super().close()
