"""Pluggable LLM provider abstraction.

This module is the **single source of truth** for all LLM provider configuration.
No other module should read Ollama- or OpenAI-related environment variables directly.

Usage::

    from llm_providers import get_provider

    provider = get_provider()                     # reads LLM_PROVIDER env var
    llm      = provider.get_chat_model()          # ChatOllama | ChatOpenAI
    emb      = provider.get_embeddings()          # OllamaEmbeddings | OpenAIEmbeddings
    tokens   = provider.get_max_tokens()          # int context window
    ok       = provider.is_available()            # health check
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any

import requests
from dotenv import load_dotenv
from pydantic import SecretStr

from providers.ollama_utils import normalize_ollama_host

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """Abstract interface that every LLM provider must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. ``'ollama'`` or ``'openai'``."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Active chat/completion model name."""

    @property
    @abstractmethod
    def embedding_model_name(self) -> str:
        """Active embeddings model name."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider endpoint is reachable and the model exists."""

    @abstractmethod
    def get_chat_model(self, reasoning: bool = False) -> Any:
        """Return a LangChain chat model instance.

        Args:
            reasoning: When True, enable extended reasoning / chain-of-thought
                       if the provider supports it (currently Ollama only).

        Returns:
            A LangChain ``BaseChatModel`` (e.g. ``ChatOllama`` or ``ChatOpenAI``).
        """

    @abstractmethod
    def get_embeddings(self) -> Any:
        """Return a LangChain embeddings instance for this provider."""

    @abstractmethod
    def get_max_tokens(self) -> int:
        """Return the context-window size for the active chat model."""


# ---------------------------------------------------------------------------
# Ollama provider
# ---------------------------------------------------------------------------

_DEFAULT_OLLAMA_MAX_TOKENS = 8192


class OllamaProvider(LLMProvider):
    """LLM provider backed by a local (or remote) Ollama server.

    Configuration (read from environment / .env):
        OLLAMA_HOST            – base URL of the Ollama server
                                 (default: ``http://127.0.0.1:11434``)
        OLLAMA_MODEL           – chat model to use (default: ``qwen3:8b``)
        OLLAMA_EMBEDDING_MODEL – embeddings model (default: ``nomic-embed-text:latest``)
        OLLAMA_MAX_TOKENS      – override context-window size (optional integer)
    """

    def __init__(self) -> None:
        raw_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        self._base_url: str = normalize_ollama_host(raw_host)
        self._model: str = os.getenv("OLLAMA_MODEL", "qwen3:8b")
        self._embedding_model: str = os.getenv(
            "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text:latest"
        )
        self._max_tokens_override: str | None = os.getenv("OLLAMA_MAX_TOKENS")

    # -- properties -----------------------------------------------------------

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def embedding_model_name(self) -> str:
        return self._embedding_model

    @property
    def base_url(self) -> str:
        """Resolved Ollama base URL (localhost → 127.0.0.1 normalised)."""
        return self._base_url

    # -- interface ------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True when Ollama is reachable and the configured model is present."""
        try:
            r = requests.get(f"{self._base_url}/api/tags", timeout=5)
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            if self._model not in models:
                logger.warning(
                    "Ollama model '%s' not found. Available: %s",
                    self._model,
                    models,
                )
                return False
            return True
        except Exception as exc:
            logger.warning("Ollama not reachable at %s: %s", self._base_url, exc)
            return False

    def get_chat_model(self, reasoning: bool = False) -> Any:
        """Return a ``ChatOllama`` instance.

        Args:
            reasoning: If True, passes ``reasoning=True`` to ChatOllama so the
                       model emits extended chain-of-thought tokens.

        Returns:
            A ``langchain_ollama.ChatOllama`` instance, or raises ``RuntimeError``
            if Ollama is unavailable.
        """
        from langchain_ollama import ChatOllama  # local import to stay optional

        if not self.is_available():
            raise RuntimeError(
                f"Ollama is unavailable or model '{self._model}' is missing. "
                f"Run: ollama pull {self._model}"
            )
        kwargs: dict[str, Any] = {
            "model": self._model,
            "base_url": self._base_url,
        }
        if reasoning:
            kwargs["reasoning"] = True
        return ChatOllama(**kwargs)

    def get_embeddings(self) -> Any:
        """Return an ``OllamaEmbeddings`` instance."""
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(
            model=self._embedding_model,
            base_url=self._base_url,
        )

    def get_max_tokens(self) -> int:
        """Return the context-window size.

        Priority:
        1. ``OLLAMA_MAX_TOKENS`` env var (if set and numeric)
        2. ``max_tokens`` / ``context_length`` from ``/api/tags`` response
        3. Built-in default (``8192``)
        """
        if self._max_tokens_override and self._max_tokens_override.isdigit():
            return int(self._max_tokens_override)
        try:
            r = requests.get(f"{self._base_url}/api/tags", timeout=5)
            for m in r.json().get("models", []):
                if m.get("name") == self._model:
                    if "max_tokens" in m:
                        return int(m["max_tokens"])
                    if "context_length" in m:
                        return int(m["context_length"])
        except Exception:
            pass
        return _DEFAULT_OLLAMA_MAX_TOKENS


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

_DEFAULT_OPENAI_MAX_TOKENS = 8192


class OpenAIProvider(LLMProvider):
    """LLM provider backed by OpenAI's API.

    Configuration (read from environment / .env):
        OPENAI_API_KEY         – OpenAI API key (required)
        OPENAI_MODEL           – chat model (default: ``gpt-4``)
        OPENAI_EMBEDDING_MODEL – embeddings model
                                 (default: ``text-embedding-3-small``)
        OPENAI_MAX_TOKENS      – override context-window size (optional integer)
    """

    def __init__(self) -> None:
        self._api_key: str | None = os.getenv("OPENAI_API_KEY")
        self._model: str = os.getenv("OPENAI_MODEL", "gpt-4")
        self._embedding_model: str = os.getenv(
            "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
        )
        self._max_tokens_override: str | None = os.getenv("OPENAI_MAX_TOKENS")

    # -- properties -----------------------------------------------------------

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def embedding_model_name(self) -> str:
        return self._embedding_model

    # -- helpers --------------------------------------------------------------

    def _key_is_valid(self) -> bool:
        return bool(self._api_key) and not (
            self._api_key and self._api_key.startswith("sk-your")
        )

    # -- interface ------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True when a valid API key is present."""
        return self._key_is_valid()

    def get_chat_model(self, reasoning: bool = False) -> Any:
        """Return a ``ChatOpenAI`` instance.

        Args:
            reasoning: Ignored for OpenAI (extended reasoning not yet supported
                       through this interface).

        Returns:
            A ``langchain_openai.ChatOpenAI`` instance, or raises ``RuntimeError``
            if the API key is missing or a placeholder.
        """
        from langchain_openai import ChatOpenAI

        if not self._key_is_valid():
            raise RuntimeError(
                "OpenAI API key is missing or unconfigured. "
                "Set OPENAI_API_KEY in your .env file."
            )
        return ChatOpenAI(
            api_key=SecretStr(self._api_key),  # type: ignore[arg-type]
            model=self._model,
        )

    def get_embeddings(self) -> Any:
        """Return an ``OpenAIEmbeddings`` instance."""
        from langchain_openai import OpenAIEmbeddings

        if not self._key_is_valid():
            raise RuntimeError(
                "OpenAI API key is missing or unconfigured. "
                "Set OPENAI_API_KEY in your .env file."
            )
        return OpenAIEmbeddings(
            model=self._embedding_model,
            api_key=self._api_key,
        )

    def get_max_tokens(self) -> int:
        """Return the context-window size.

        Priority:
        1. ``OPENAI_MAX_TOKENS`` env var (if set and numeric)
        2. OpenAI models API (``context_length`` / ``max_tokens`` field)
        3. Built-in default (``8192``)
        """
        if self._max_tokens_override and self._max_tokens_override.isdigit():
            return int(self._max_tokens_override)
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self._api_key)
            mdl = client.models.retrieve(self._model)
            return getattr(
                mdl,
                "context_length",
                getattr(mdl, "max_tokens", _DEFAULT_OPENAI_MAX_TOKENS),
            )
        except Exception:
            return _DEFAULT_OPENAI_MAX_TOKENS


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[LLMProvider]] = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
}


def get_provider(name: str | None = None) -> LLMProvider:
    """Return an ``LLMProvider`` instance for the requested provider.

    Args:
        name: Provider name (``'ollama'`` or ``'openai'``).
              If *None*, reads the ``LLM_PROVIDER`` environment variable
              (default: ``'ollama'``).

    Returns:
        A concrete ``LLMProvider`` instance.

    Raises:
        ValueError: If *name* is not a recognised provider.
    """
    resolved = (name or os.getenv("LLM_PROVIDER", "ollama")).lower()
    cls = _REGISTRY.get(resolved)
    if cls is None:
        raise ValueError(
            f"Unknown LLM provider: '{resolved}'. "
            f"Valid options: {list(_REGISTRY)}"
        )
    return cls()
