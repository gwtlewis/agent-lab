"""
WebSocket server protocol tests.

Uses FastAPI's TestClient + httpx for HTTP and the built-in
WebSocket test client for WebSocket flows.  All LLM calls are mocked.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _chunk(content="", reasoning=""):
    c = MagicMock()
    c.content = content
    c.additional_kwargs = {"reasoning_content": reasoning} if reasoning else {}
    return c


def _mock_agent(stream_chunks):
    """Return a patched IntegratedAgent where llm.stream yields chunks."""
    with (
        patch("agent.requests.get") as mock_get,
        patch("agent.ChatOllama") as mock_llm_cls,
    ):
        resp = MagicMock()
        resp.json.return_value = {"models": [{"name": "qwen3:8b"}]}
        mock_get.return_value = resp
        llm_instance = MagicMock()
        llm_instance.stream.return_value = stream_chunks
        mock_llm_cls.return_value = llm_instance
        from agent import IntegratedAgent
        return IntegratedAgent()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def client():
    """TestClient wired to the FastAPI app with a mocked agent."""
    with (
        patch("web_server.IntegratedAgent") as mock_agent_cls,
        patch("agent.requests.get") as mock_get,
        patch("agent.ChatOllama"),
    ):
        resp = MagicMock()
        resp.json.return_value = {"models": [{"name": "qwen3:8b"}]}
        mock_get.return_value = resp

        agent_instance = MagicMock()
        agent_instance.stream_events.return_value = iter([])
        mock_agent_cls.return_value = agent_instance

        from web_server import app
        with TestClient(app) as c:
            c._mock_agent = agent_instance
            yield c


# ── HTTP endpoint tests ───────────────────────────────────────────────────────

class TestHTTPEndpoints:
    def test_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "provider" in data

    def test_index_returns_html_or_json(self, client):
        r = client.get("/")
        assert r.status_code == 200


# ── WebSocket protocol tests ──────────────────────────────────────────────────

class TestWebSocketHandshake:
    def test_initial_connected_event(self, client):
        with client.websocket_connect("/ws") as ws:
            ev = json.loads(ws.receive_text())
        assert ev["type"] == "status"
        assert ev["content"] == "connected"
        assert "provider" in ev["metadata"]
        assert "model" in ev["metadata"]


class TestWebSocketPing:
    def test_ping_returns_pong(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()  # consume handshake
            ws.send_json({"type": "ping"})
            ev = json.loads(ws.receive_text())
        assert ev["type"] == "pong"


class TestWebSocketClear:
    def test_clear_returns_cleared(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()  # handshake
            ws.send_json({"type": "clear"})
            ev = json.loads(ws.receive_text())
        assert ev["type"] == "cleared"
        client._mock_agent.clear_memory.assert_called_once()


class TestWebSocketMessage:
    def _make_event(self, type_, content="", metadata=None):
        from event_model import AgentEvent
        return AgentEvent(type=type_, content=content, metadata=metadata or {})

    def test_message_triggers_stream(self, client):
        from event_model import AgentEvent
        client._mock_agent.stream_events.return_value = iter([
            AgentEvent.status("thinking"),
            AgentEvent.token("hi"),
            AgentEvent.final("hi", reasoning_shown=False),
        ])
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()  # handshake
            ws.send_json({"type": "message", "content": "hello"})
            events = [json.loads(ws.receive_text()) for _ in range(3)]
        types = [e["type"] for e in events]
        assert "status" in types
        assert "token" in types
        assert "final" in types

    def test_empty_message_returns_error(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()  # handshake
            ws.send_json({"type": "message", "content": "   "})
            ev = json.loads(ws.receive_text())
        assert ev["type"] == "error"
        assert "Empty" in ev["content"]

    def test_invalid_json_returns_error(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()  # handshake
            ws.send_text("not json at all")
            ev = json.loads(ws.receive_text())
        assert ev["type"] == "error"

    def test_whitespace_only_returns_error(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
            ws.send_json({"type": "message", "content": "\n\t  \n"})
            ev = json.loads(ws.receive_text())
        assert ev["type"] == "error"

    def test_missing_content_field_returns_error(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
            ws.send_json({"type": "message"})
            ev = json.loads(ws.receive_text())
        assert ev["type"] == "error"

    def test_unknown_message_type_ignored(self, client):
        """Unknown types must not crash the server."""
        from event_model import AgentEvent
        # After sending an unknown type, a subsequent ping should still work
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
            ws.send_json({"type": "unknown_future_feature"})
            ws.send_json({"type": "ping"})
            ev = json.loads(ws.receive_text())
        assert ev["type"] == "pong"


class TestWebSocketReasoningFlag:
    def test_enable_reasoning_forwarded(self, client):
        from event_model import AgentEvent
        client._mock_agent.stream_events.return_value = iter([
            AgentEvent.final("ok"),
        ])
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
            ws.send_json({"type": "message", "content": "q", "enable_reasoning": True})
            ws.receive_text()
        call_kwargs = client._mock_agent.stream_events.call_args
        assert call_kwargs.kwargs.get("enable_reasoning") is True

    def test_disable_reasoning_forwarded(self, client):
        from event_model import AgentEvent
        client._mock_agent.stream_events.return_value = iter([
            AgentEvent.final("ok"),
        ])
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
            ws.send_json({"type": "message", "content": "q", "enable_reasoning": False})
            ws.receive_text()
        call_kwargs = client._mock_agent.stream_events.call_args
        assert call_kwargs.kwargs.get("enable_reasoning") is False
