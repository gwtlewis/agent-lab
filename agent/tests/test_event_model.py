"""Unit tests for event_model.py"""
import json
import pytest
from core.event_model import AgentEvent, EventType


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


class TestToolCallEvent:
    """Tests for AgentEvent.tool_call factory."""

    def test_tool_call_event_type(self):
        ev = AgentEvent.tool_call("search_knowledge_base", "XVA credit", [])
        assert ev.type == "tool_call"

    def test_tool_call_event_content(self):
        ev = AgentEvent.tool_call("search_knowledge_base", "XVA credit valuation", [])
        assert ev.content == "XVA credit valuation"

    def test_tool_call_event_metadata_tool_name(self):
        ev = AgentEvent.tool_call("search_knowledge_base", "query", [])
        assert ev.metadata["tool"] == "search_knowledge_base"

    def test_tool_call_event_metadata_docs(self):
        docs = [{"title": "Report 2024"}, {"title": "CVA Guide"}]
        ev = AgentEvent.tool_call("search_knowledge_base", "query", docs)
        assert ev.metadata["docs"] == docs

    def test_tool_call_event_json_round_trip(self):
        docs = [{"title": "Report 2024"}]
        ev = AgentEvent.tool_call("search_knowledge_base", "XVA", docs)
        data = json.loads(ev.to_json())
        assert data["type"] == "tool_call"
        assert data["content"] == "XVA"
        assert data["metadata"]["tool"] == "search_knowledge_base"
        assert data["metadata"]["docs"] == docs

    def test_tool_call_event_empty_docs(self):
        ev = AgentEvent.tool_call("some_tool", "query", [])
        assert ev.metadata["docs"] == []
        data = json.loads(ev.to_json())
        assert data["metadata"]["docs"] == []


class TestBoardEvent:
    """Tests for AgentEvent.board factory."""

    def test_board_event_type(self):
        ev = AgentEvent.board("<table></table>")
        assert ev.type == "board"

    def test_board_event_content(self):
        html = '<canvas id="myChart"></canvas>'
        ev = AgentEvent.board(html)
        assert ev.content == html

    def test_board_event_empty_metadata(self):
        ev = AgentEvent.board("<p>hi</p>")
        assert ev.metadata == {}

    def test_board_event_json_round_trip(self):
        html = "<table><tr><td>CVA</td><td>1.5M</td></tr></table>"
        ev = AgentEvent.board(html)
        data = json.loads(ev.to_json())
        assert data["type"] == "board"
        assert data["content"] == html
        assert data["metadata"] == {}

    def test_board_event_empty_html(self):
        ev = AgentEvent.board("")
        assert ev.type == "board"
        assert ev.content == ""


