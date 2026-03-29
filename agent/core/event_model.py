"""Normalized streaming event model for the agent websocket protocol.

Events flow from the agent server to the UI client in this order:
  status     → signals the server started working
  reasoning  → zero or more chunks of model thinking (Ollama/Qwen reasoning mode)
  tool_call  → emitted once per tool invocation; carries tool name, query, and result metadata
  board      → emitted when render_dashboard tool is called; carries an HTML fragment for the UI panel
  token      → zero or more chunks of the answer text
  final      → marks end of a turn; carries the complete answer and metadata
  error      → carries a human-readable error message; ends the turn

Clients that do not understand a new event type can safely skip it by checking
the ``type`` field before processing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Literal

EventType = Literal["status", "reasoning", "token", "tool_call", "board", "final", "error", "pong", "cleared"]


@dataclass
class AgentEvent:
    """A single normalized event emitted by the agent streaming pipeline."""

    type: EventType
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {"type": self.type, "content": self.content, "metadata": self.metadata}
        )

    @staticmethod
    def status(msg: str = "thinking") -> "AgentEvent":
        return AgentEvent(type="status", content=msg)

    @staticmethod
    def reasoning(chunk: str) -> "AgentEvent":
        return AgentEvent(type="reasoning", content=chunk)

    @staticmethod
    def token(chunk: str) -> "AgentEvent":
        return AgentEvent(type="token", content=chunk)

    @staticmethod
    def final(full_text: str, reasoning_shown: bool = False) -> "AgentEvent":
        return AgentEvent(
            type="final",
            content=full_text,
            metadata={"reasoning_shown": reasoning_shown},
        )

    @staticmethod
    def tool_call(tool_name: str, query: str, docs: list) -> "AgentEvent":
        """Emitted once per tool invocation during a streaming turn.

        Args:
            tool_name: The registered name of the tool that was called.
            query:     The input string/query the model passed to the tool.
            docs:      List of dicts with at least a ``title`` key for each
                       document chunk surfaced by the tool (may be empty for
                       non-RAG tools).
        """
        return AgentEvent(
            type="tool_call",
            content=query,
            metadata={"tool": tool_name, "docs": docs},
        )

    @staticmethod
    def board(html: str) -> "AgentEvent":
        """Emitted when the agent calls render_dashboard; carries an HTML fragment.

        The frontend renders this inside a sandboxed iframe panel.
        """
        return AgentEvent(type="board", content=html)

    @staticmethod
    def error(msg: str) -> "AgentEvent":
        return AgentEvent(type="error", content=msg)

    @staticmethod
    def pong() -> "AgentEvent":
        return AgentEvent(type="pong")

    @staticmethod
    def cleared() -> "AgentEvent":
        return AgentEvent(type="cleared")
