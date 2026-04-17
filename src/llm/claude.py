"""Anthropic Claude client. Default provider."""

from __future__ import annotations

import os

from anthropic import Anthropic

from llm.client import (
    LLMClient,
    LLMResponse,
    Message,
    StopReason,
    ToolCall,
    ToolSpec,
)

# Claude pricing (USD per million tokens). Keep in sync with pricing page.
PRICING = {
    "claude-opus-4-7": (15.00, 75.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-haiku-4-5": (0.80, 4.00),
}

STOP_MAP = {
    "end_turn": StopReason.END_TURN,
    "tool_use": StopReason.TOOL_USE,
    "max_tokens": StopReason.MAX_TOKENS,
    "stop_sequence": StopReason.STOP_SEQUENCE,
    "refusal": StopReason.REFUSAL,
}


class ClaudeClient(LLMClient):
    provider = "anthropic"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or os.getenv("PIA_LLM_MODEL_CLAUDE", "claude-opus-4-7")
        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))

    def _estimate_cost(self, in_tok: int, out_tok: int) -> float:
        in_rate, out_rate = PRICING.get(self.model, (0.0, 0.0))
        return (in_tok / 1_000_000) * in_rate + (out_tok / 1_000_000) * out_rate

    def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        api_tools = (
            [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools]
            if tools
            else None
        )
        api_messages = [{"role": m.role, "content": m.content} for m in messages]

        kwargs: dict = {
            "model": self.model,
            "system": system,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if api_tools:
            kwargs["tools"] = api_tools

        response = self.client.messages.create(**kwargs)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
                )

        in_tok = response.usage.input_tokens
        out_tok = response.usage.output_tokens

        return LLMResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=STOP_MAP.get(response.stop_reason or "end_turn", StopReason.END_TURN),
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=self._estimate_cost(in_tok, out_tok),
            model=self.model,
            raw={"id": response.id, "stop_reason": response.stop_reason},
        )

    def format_tool_result(self, tool_call_id: str, content: str) -> Message:
        return Message(
            role="user",
            content=[
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": content,
                }
            ],
        )
