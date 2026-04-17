"""Google Gemini client. Alternate provider for GCP-native deployments."""

from __future__ import annotations

import json
import os
import uuid

from google import genai
from google.genai import types

from llm.client import (
    LLMClient,
    LLMResponse,
    Message,
    StopReason,
    ToolCall,
    ToolSpec,
)

# Gemini pricing (USD per million tokens).
PRICING = {
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
}


def _to_gemini_schema(schema: dict) -> dict:
    """Gemini's function-calling schema is JSON-Schema-ish but stricter."""
    return schema


class GeminiClient(LLMClient):
    provider = "google"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or os.getenv("PIA_LLM_MODEL_GEMINI", "gemini-2.0-flash")
        self.client = genai.Client(api_key=api_key or os.getenv("GOOGLE_API_KEY"))

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
        function_decls = (
            [
                types.FunctionDeclaration(
                    name=t.name,
                    description=t.description,
                    parameters=_to_gemini_schema(t.input_schema),
                )
                for t in tools
            ]
            if tools
            else None
        )
        gemini_tools = [types.Tool(function_declarations=function_decls)] if function_decls else None

        # Gemini uses a Content list with role in {user, model}. Map assistant→model.
        contents = []
        for m in messages:
            role = "model" if m.role == "assistant" else m.role
            if isinstance(m.content, str):
                contents.append(types.Content(role=role, parts=[types.Part(text=m.content)]))
            else:
                # Tool results arrive as list[dict]; flatten to text for Gemini's simpler shape.
                text_chunks = [json.dumps(c) if isinstance(c, dict) else str(c) for c in m.content]
                contents.append(types.Content(role=role, parts=[types.Part(text="\n".join(text_chunks))]))

        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=temperature,
            tools=gemini_tools,
        )
        response = self.client.models.generate_content(
            model=self.model, contents=contents, config=config
        )

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        stop_reason = StopReason.END_TURN

        for candidate in response.candidates or []:
            for part in candidate.content.parts or []:
                if getattr(part, "text", None):
                    text_parts.append(part.text)
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    tool_calls.append(
                        ToolCall(
                            id=str(uuid.uuid4()),
                            name=fc.name,
                            arguments=dict(fc.args or {}),
                        )
                    )
                    stop_reason = StopReason.TOOL_USE

        usage = response.usage_metadata
        in_tok = usage.prompt_token_count if usage else 0
        out_tok = usage.candidates_token_count if usage else 0

        return LLMResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=self._estimate_cost(in_tok, out_tok),
            model=self.model,
            raw={},
        )

    def format_tool_result(self, tool_call_id: str, content: str) -> Message:
        return Message(
            role="user",
            content=[{"tool_call_id": tool_call_id, "content": content}],
        )
