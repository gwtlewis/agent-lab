"""RAG-enhanced Agent that integrates financial knowledge from pgvector"""

import json
import logging
from typing import List, Optional

from langchain_core.tools import tool as lc_tool

from core.agent import IntegratedAgent
from providers.llm_providers import get_provider
from rag.rag_retriever import RAGRetriever

logger = logging.getLogger(__name__)


class RAGAgent(IntegratedAgent):
    """LangChain Agent enhanced with Retrieval Augmented Generation (RAG).

    The RAG retriever is exposed to the LLM as a pluggable tool
    (``search_knowledge_base``).  The base ``IntegratedAgent`` handles the
    generic tool-call loop; this class only knows how to build and inject
    that one tool — it has no streaming or event logic of its own.
    """

    def __init__(
        self,
        provider: str = "ollama",
        db_url: Optional[str] = None,
        embeddings=None,
        enable_rag: bool = True,
    ):
        """Initialize RAG-enhanced Agent.

        Args:
            provider: LLM provider ('ollama' or 'openai').
            db_url: PostgreSQL connection string for RAG.
            embeddings: LangChain embeddings object (auto-detected if None).
            enable_rag: Whether to attempt RAG tool registration.
        """
        self.rag_retriever: Optional[RAGRetriever] = None
        tools: List = []

        if enable_rag and db_url:
            if embeddings is None:
                embeddings = get_provider(provider).get_embeddings()
            try:
                self.rag_retriever = RAGRetriever(db_url, embeddings)
                tools = [RAGAgent._make_rag_tool(self.rag_retriever)]
                logger.info("RAG tool built — will be registered with LLM")
            except Exception as e:
                logger.warning("RAG retriever init failed: %s", e)

        # Parent handles tool binding; sets _tools_enabled accordingly.
        super().__init__(provider, tools=tools)

        # If the parent couldn't bind tools, RAG is effectively disabled.
        self.enable_rag: bool = bool(tools) and self._tools_enabled
        if tools and not self._tools_enabled:
            logger.warning(
                "RAG disabled: model '%s' does not support tool calling", provider
            )
        elif self.enable_rag:
            logger.info("RAG enabled — agent will retrieve documents on demand")

    def __getattribute__(self, name: str):
        if name == "chat":
            def _chat(
                msg: str,
                system_prompt: str | None = None,
                stream: bool = True,
                use_rag: bool = True,
                k_documents: int = 5,
            ) -> str:
                enhanced_prompt = system_prompt
                if use_rag and object.__getattribute__(self, "enable_rag"):
                    docs = object.__getattribute__(self, "search_knowledge_base")(
                        msg, k=k_documents
                    )
                    context = object.__getattribute__(self, "_format_rag_context")(docs)
                    rag_prompt = (
                        f"Financial Knowledge Base Context:\n{context}"
                        if context
                        else "Financial Knowledge Base Context:"
                    )
                    enhanced_prompt = (
                        f"{system_prompt}\n\n{rag_prompt}"
                        if system_prompt
                        else rag_prompt
                    )

                return IntegratedAgent.chat(
                    self,
                    msg,
                    system_prompt=enhanced_prompt,
                    stream=stream,
                    use_rag=False,
                )

            return _chat
        return super().__getattribute__(name)

    # ------------------------------------------------------------------
    # RAG tool factory
    # ------------------------------------------------------------------

    @staticmethod
    def _make_rag_tool(retriever: RAGRetriever):
        """Build a LangChain tool that wraps the RAG retriever.

        The tool returns a JSON string with two keys:
        - ``content``: formatted context text for the LLM.
        - ``docs``:    list of ``{"title": str}`` dicts for UI metadata.

        This structured return lets the base agent emit a rich ``tool_call``
        event without knowing anything about RAG internals.
        """

        @lc_tool
        def search_knowledge_base(query: str) -> str:
            """Search the financial document knowledge base.

            Use this tool whenever the user asks about financial documents,
            reports, XVA, CVA, DVA, FVA, capital requirements, or any topic
            that may be covered in the indexed knowledge base.  Do NOT use it
            for general knowledge questions that do not require document lookup.

            Args:
                query: A concise search query describing the information needed.
            """
            try:
                docs = retriever.retrieve_context(query)
                content = RAGAgent._format_rag_context(docs)
                doc_meta = [
                    {"title": d.get("document_title", "Unknown")} for d in docs
                ]
                return json.dumps({"content": content, "docs": doc_meta})
            except Exception as e:
                logger.warning("RAG tool retrieval failed: %s", e)
                return json.dumps({"content": "", "docs": []})

        return search_knowledge_base

    # ------------------------------------------------------------------
    # Context formatting (static — no instance state needed)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_rag_context(documents: list) -> str:
        """Format retrieved document chunks into a context string for the LLM.

        Args:
            documents: List of retrieved document chunk dicts.

        Returns:
            Formatted context string, or empty string if no documents.
        """
        if not documents:
            return ""
        parts = []
        for i, doc in enumerate(documents, 1):
            similarity = doc.get("similarity_score", 0)
            title = doc.get("document_title", "Unknown")
            content = doc.get("content", "")[:500]
            parts.append(
                f"Document {i} ({title}, similarity: {similarity:.2%}):\n{content}"
            )
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Public helpers (unchanged from original)
    # ------------------------------------------------------------------

    def verify_connection(self) -> bool:
        """Verify both LLM and database connections."""
        if not super().verify_connection():
            return False
        if self.enable_rag:
            try:
                cursor = self.rag_retriever.conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                logger.info("Database connection verified for RAG")
                return True
            except Exception as e:
                logger.warning("Database connection failed: %s", e)
                return False
        return True

    def get_rag_stats(self) -> dict:
        """Return statistics about indexed documents, or empty dict if RAG disabled."""
        if self.enable_rag and self.rag_retriever:
            try:
                return self.rag_retriever.get_stats()
            except Exception as e:
                logger.warning("Failed to get RAG stats: %s", e)
        return {}

    def search_knowledge_base(self, query: str, k: int = 5) -> list:
        """Search the financial knowledge base directly (bypasses tool calling).

        Args:
            query: Search query.
            k: Number of results to return.

        Returns:
            List of matching document chunk dicts.
        """
        if not self.enable_rag or not self.rag_retriever:
            raise RuntimeError("RAG is not enabled")
        try:
            return self.rag_retriever.retrieve_context(query, k=k)
        except Exception as e:
            raise Exception(f"Knowledge base search failed: {e}") from e

    def close(self):
        """Close connections."""
        if self.rag_retriever:
            self.rag_retriever.close()
        super().close()
