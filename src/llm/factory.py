"""Pick the LLM provider from env."""

from __future__ import annotations

import os

from llm.client import LLMClient


def get_client() -> LLMClient:
    provider = os.getenv("PIA_LLM_PROVIDER", "claude").lower()
    if provider == "claude":
        from llm.claude import ClaudeClient

        return ClaudeClient()
    if provider == "gemini":
        from llm.gemini import GeminiClient

        return GeminiClient()
    raise ValueError(f"Unknown PIA_LLM_PROVIDER={provider}; expected 'claude' or 'gemini'")
