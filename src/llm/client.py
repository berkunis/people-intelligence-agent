"""Provider-agnostic LLM client protocol.

Why we wrote this ourselves instead of using LiteLLM:
  - LiteLLM hides token accounting details we need for cost governance
  - We want provider choice to be a deploy-time config, not a runtime abstraction
  - ~150 lines of protocol-level code signals that we understand the abstraction,
    not that we imported one. See docs/adr/0002-llm-abstraction.md.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StopReason(str, Enum):
    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    REFUSAL = "refusal"
    ERROR = "error"


@dataclass(frozen=True)
class ToolSpec:
    """What a tool looks like to the LLM. Same shape for Claude and Gemini."""

    name: str
    description: str
    input_schema: dict[str, Any]  # JSON Schema


@dataclass
class ToolCall:
    """A model-generated request to invoke a tool."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    """One turn in a conversation. Role is user | assistant | tool_result."""

    role: str
    content: str | list[dict[str, Any]]


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: StopReason = StopReason.END_TURN
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class LLMClient(ABC):
    """Protocol implemented by Claude and Gemini clients."""

    provider: str
    model: str

    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Synchronous completion. Returns the full response or raises."""

    @abstractmethod
    def format_tool_result(self, tool_call_id: str, content: str) -> Message:
        """Each provider expects tool results in a specific shape."""
