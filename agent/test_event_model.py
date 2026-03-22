"""Unit tests for event_model.py"""
import json
import pytest
from event_model import AgentEvent, EventType


class TestAgentEventFactory:
    def test_status_event(self):
        ev = AgentEvent.status("thinking")
        assert ev.type == "status"
        assert ev.content == "thinking"
        assert ev.metadata == {}

    def test_status_default(self):
        ev = AgentEvent.status()
        assert ev.content == "thinking"

    def test_reasoning_event(self):
        ev = AgentEvent.reasoning("some thought")
        assert ev.type == "reasoning"
        assert ev.content == "some thought"

    def test_token_event(self):
        ev = AgentEvent.token("hello ")
        assert ev.type == "token"
        assert ev.content == "hello "

    def test_final_event_default(self):
        ev = AgentEvent.final("The answer is 4.")
        assert ev.type == "final"
        assert ev.content == "The answer is 4."
        assert ev.metadata == {"reasoning_shown": False}

    def test_final_event_with_reasoning(self):
        ev = AgentEvent.final("answer", reasoning_shown=True)
        assert ev.metadata["reasoning_shown"] is True

    def test_error_event(self):
        ev = AgentEvent.error("timeout")
        assert ev.type == "error"
        assert ev.content == "timeout"

    def test_pong_event(self):
        ev = AgentEvent.pong()
        assert ev.type == "pong"
        assert ev.content == ""

    def test_cleared_event(self):
        ev = AgentEvent.cleared()
        assert ev.type == "cleared"


class TestAgentEventSerialization:
    def test_to_json_round_trip(self):
        ev = AgentEvent.final("hi", reasoning_shown=True)
        data = json.loads(ev.to_json())
        assert data["type"] == "final"
        assert data["content"] == "hi"
        assert data["metadata"]["reasoning_shown"] is True

    def test_to_json_contains_all_keys(self):
        ev = AgentEvent.token("x")
        data = json.loads(ev.to_json())
        assert "type" in data
        assert "content" in data
        assert "metadata" in data

    def test_empty_metadata_serializes(self):
        ev = AgentEvent.status("connected")
        data = json.loads(ev.to_json())
        assert data["metadata"] == {}

    def test_reasoning_with_unicode(self):
        ev = AgentEvent.reasoning("思考中…")
        data = json.loads(ev.to_json())
        assert data["content"] == "思考中…"
