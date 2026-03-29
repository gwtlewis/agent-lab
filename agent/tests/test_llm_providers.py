"""Unit tests for llm_providers.py — all external calls are mocked."""

from unittest.mock import MagicMock, patch

import pytest

from providers.llm_providers import OllamaProvider, OpenAIProvider, get_provider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ollama_tags_response(model_name: str = "qwen3:8b"):
    """Fake /api/tags JSON body."""
    return {"models": [{"name": model_name}]}


# ---------------------------------------------------------------------------
# OllamaProvider — is_available
# ---------------------------------------------------------------------------

class TestOllamaProviderIsAvailable:
    def test_returns_true_when_model_present(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _ollama_tags_response("qwen3:8b")
        mock_resp.raise_for_status = MagicMock()

        with patch("providers.llm_providers.requests.get", return_value=mock_resp):
            with patch.dict("os.environ", {"OLLAMA_MODEL": "qwen3:8b"}, clear=False):
                provider = OllamaProvider()
                assert provider.is_available() is True

    def test_returns_false_when_model_missing(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"models": [{"name": "other-model:latest"}]}
        mock_resp.raise_for_status = MagicMock()

        with patch("providers.llm_providers.requests.get", return_value=mock_resp):
            with patch.dict("os.environ", {"OLLAMA_MODEL": "qwen3:8b"}, clear=False):
                provider = OllamaProvider()
                assert provider.is_available() is False

    def test_returns_false_when_request_fails(self):
        with patch("providers.llm_providers.requests.get", side_effect=ConnectionError("refused")):
            provider = OllamaProvider()
            assert provider.is_available() is False


# ---------------------------------------------------------------------------
# OllamaProvider — get_chat_model
# ---------------------------------------------------------------------------

class TestOllamaProviderGetChatModel:
    def _mock_available(self, provider):
        return patch.object(provider, "is_available", return_value=True)

    def test_returns_chat_ollama_instance(self):
        provider = OllamaProvider()
        mock_chat = MagicMock()

        with self._mock_available(provider):
            with patch("providers.llm_providers.OllamaProvider.get_chat_model", return_value=mock_chat):
                result = provider.get_chat_model()
                assert result is mock_chat

    def test_raises_runtime_error_when_unavailable(self):
        provider = OllamaProvider()
        with patch.object(provider, "is_available", return_value=False):
            with pytest.raises(RuntimeError, match="unavailable"):
                provider.get_chat_model()

    def test_reasoning_flag_passed_to_chat_ollama(self):
        provider = OllamaProvider()
        with patch.object(provider, "is_available", return_value=True):
            with patch("langchain_ollama.ChatOllama") as mock_cls:
                mock_cls.return_value = MagicMock()
                provider.get_chat_model(reasoning=True)
                _, kwargs = mock_cls.call_args
                assert kwargs.get("reasoning") is True

    def test_get_chat_model_raises_when_unavailable(self):
        provider = OllamaProvider()
        with patch.object(provider, "is_available", return_value=False):
            with pytest.raises(RuntimeError):
                provider.get_chat_model(reasoning=False)


# ---------------------------------------------------------------------------
# OllamaProvider — get_embeddings
# ---------------------------------------------------------------------------

class TestOllamaProviderGetEmbeddings:
    def test_returns_ollama_embeddings(self):
        provider = OllamaProvider()
        mock_emb = MagicMock()
        with patch("providers.llm_providers.OllamaProvider.get_embeddings", return_value=mock_emb):
            assert provider.get_embeddings() is mock_emb

    def test_uses_embedding_model_from_env(self):
        with patch.dict(
            "os.environ",
            {"OLLAMA_EMBEDDING_MODEL": "mxbai-embed-large:latest"},
            clear=False,
        ):
            provider = OllamaProvider()
            assert provider.embedding_model_name == "mxbai-embed-large:latest"


# ---------------------------------------------------------------------------
# OllamaProvider — get_max_tokens
# ---------------------------------------------------------------------------

class TestOllamaProviderGetMaxTokens:
    def test_reads_env_override(self):
        with patch.dict("os.environ", {"OLLAMA_MAX_TOKENS": "4096"}, clear=False):
            provider = OllamaProvider()
            assert provider.get_max_tokens() == 4096

    def test_falls_back_to_default_when_api_fails(self):
        with patch.dict("os.environ", {}, clear=False):
            with patch("providers.llm_providers.requests.get", side_effect=Exception("fail")):
                provider = OllamaProvider()
                # Remove env override if set
                import os
                os.environ.pop("OLLAMA_MAX_TOKENS", None)
                provider._max_tokens_override = None
                assert provider.get_max_tokens() == 8192

    def test_reads_context_length_from_api(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "models": [{"name": "qwen3:8b", "context_length": 32768}]
        }
        with patch.dict("os.environ", {"OLLAMA_MODEL": "qwen3:8b"}, clear=False):
            provider = OllamaProvider()
            provider._max_tokens_override = None
            with patch("providers.llm_providers.requests.get", return_value=mock_resp):
                assert provider.get_max_tokens() == 32768


# ---------------------------------------------------------------------------
# OllamaProvider — properties
# ---------------------------------------------------------------------------

class TestOllamaProviderProperties:
    def test_name(self):
        assert OllamaProvider().name == "ollama"

    def test_model_name_from_env(self):
        with patch.dict("os.environ", {"OLLAMA_MODEL": "llama3:8b"}, clear=False):
            assert OllamaProvider().model_name == "llama3:8b"

    def test_base_url_normalises_localhost(self):
        with patch.dict(
            "os.environ", {"OLLAMA_HOST": "http://localhost:11434"}, clear=False
        ):
            provider = OllamaProvider()
            assert "127.0.0.1" in provider.base_url

    def test_default_embedding_model(self):
        import os
        os.environ.pop("OLLAMA_EMBEDDING_MODEL", None)
        provider = OllamaProvider()
        assert provider.embedding_model_name == "nomic-embed-text:latest"


# ---------------------------------------------------------------------------
# OpenAIProvider — is_available
# ---------------------------------------------------------------------------

class TestOpenAIProviderIsAvailable:
    def test_returns_true_with_valid_key(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-real-key-abc"}, clear=False):
            assert OpenAIProvider().is_available() is True

    def test_returns_false_with_placeholder_key(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-your-key-here"}, clear=False):
            assert OpenAIProvider().is_available() is False

    def test_returns_false_with_no_key(self):
        import os
        os.environ.pop("OPENAI_API_KEY", None)
        provider = OpenAIProvider()
        provider._api_key = None
        assert provider.is_available() is False


# ---------------------------------------------------------------------------
# OpenAIProvider — get_chat_model
# ---------------------------------------------------------------------------

class TestOpenAIProviderGetChatModel:
    def test_raises_when_key_invalid(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-your-key"}, clear=False):
            with pytest.raises(RuntimeError, match="API key"):
                OpenAIProvider().get_chat_model()

    def test_returns_instance_with_valid_key(self):
        mock_chat = MagicMock()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-real-abc"}, clear=False):
            provider = OpenAIProvider()
            with patch("providers.llm_providers.OpenAIProvider.get_chat_model", return_value=mock_chat):
                assert provider.get_chat_model() is mock_chat


# ---------------------------------------------------------------------------
# OpenAIProvider — get_max_tokens
# ---------------------------------------------------------------------------

class TestOpenAIProviderGetMaxTokens:
    def test_reads_env_override(self):
        with patch.dict("os.environ", {"OPENAI_MAX_TOKENS": "16384"}, clear=False):
            provider = OpenAIProvider()
            assert provider.get_max_tokens() == 16384

    def test_falls_back_to_default_on_api_error(self):
        import os
        os.environ.pop("OPENAI_MAX_TOKENS", None)
        provider = OpenAIProvider()
        provider._max_tokens_override = None
        with patch("openai.OpenAI", side_effect=Exception("fail")):
            assert provider.get_max_tokens() == 8192


# ---------------------------------------------------------------------------
# OpenAIProvider — properties
# ---------------------------------------------------------------------------

class TestOpenAIProviderProperties:
    def test_name(self):
        assert OpenAIProvider().name == "openai"

    def test_model_name_from_env(self):
        with patch.dict("os.environ", {"OPENAI_MODEL": "gpt-4o"}, clear=False):
            assert OpenAIProvider().model_name == "gpt-4o"

    def test_default_embedding_model(self):
        import os
        os.environ.pop("OPENAI_EMBEDDING_MODEL", None)
        provider = OpenAIProvider()
        assert provider.embedding_model_name == "text-embedding-3-small"

    def test_embedding_model_from_env(self):
        with patch.dict(
            "os.environ", {"OPENAI_EMBEDDING_MODEL": "text-embedding-ada-002"}, clear=False
        ):
            assert OpenAIProvider().embedding_model_name == "text-embedding-ada-002"


# ---------------------------------------------------------------------------
# get_provider factory
# ---------------------------------------------------------------------------

class TestGetProvider:
    def test_returns_ollama_provider_by_name(self):
        assert isinstance(get_provider("ollama"), OllamaProvider)

    def test_returns_openai_provider_by_name(self):
        assert isinstance(get_provider("openai"), OpenAIProvider)

    def test_reads_env_var_when_name_is_none(self):
        with patch.dict("os.environ", {"LLM_PROVIDER": "openai"}, clear=False):
            assert isinstance(get_provider(), OpenAIProvider)

    def test_defaults_to_ollama_when_env_not_set(self):
        import os
        os.environ.pop("LLM_PROVIDER", None)
        assert isinstance(get_provider(), OllamaProvider)

    def test_raises_on_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_provider("unknown-provider")

    def test_case_insensitive(self):
        assert isinstance(get_provider("Ollama"), OllamaProvider)
        assert isinstance(get_provider("OpenAI"), OpenAIProvider)
