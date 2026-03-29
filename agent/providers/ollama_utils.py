"""Utilities for working with Ollama endpoints."""

from urllib.parse import urlparse, urlunparse


def normalize_ollama_host(host: str) -> str:
    """Prefer IPv4 loopback for localhost-based Ollama URLs.

    LangChain's Ollama client can fail against ``localhost`` on some macOS setups
    even when the Ollama server is healthy. Normalizing to ``127.0.0.1`` avoids
    that loopback resolution issue while preserving non-localhost hosts.
    """

    parsed = urlparse(host)
    if parsed.hostname != "localhost":
        return host

    netloc = parsed.netloc.replace("localhost", "127.0.0.1", 1)
    return urlunparse(parsed._replace(netloc=netloc))
