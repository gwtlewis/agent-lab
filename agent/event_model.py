"""Normalized streaming event model for the agent websocket protocol.

Events flow from the agent server to the UI client in this order:
  status     → signals the server started working
  reasoning  → zero or more chunks of model thinking (Ollama/Qwen reasoning mode)
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

EventType = Literal["status", "reasoning", "token", "final", "error", "pong", "cleared"]


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
    def error(msg: str) -> "AgentEvent":
        return AgentEvent(type="error", content=msg)

    @staticmethod
    def pong() -> "AgentEvent":
        return AgentEvent(type="pong")

    @staticmethod
    def cleared() -> "AgentEvent":
        return AgentEvent(type="cleared")
