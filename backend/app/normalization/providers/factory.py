import os
from typing import Optional
from app.normalization.providers.base import AIProvider
from app.normalization.providers.mock import MockAIProvider
from app.normalization.providers.openai_provider import OpenAICompatibleProvider
from app.normalization.providers.gemini_provider import GeminiProvider

_PROVIDER_INSTANCE: Optional[AIProvider] = None

def get_ai_provider() -> AIProvider:
    """
    Returns configured AI provider singleton based on AI_PROVIDER environment variable.
    Options: 'mock' (default), 'openai', 'gemini', 'local'.
    """
    global _PROVIDER_INSTANCE
    if _PROVIDER_INSTANCE is not None:
        return _PROVIDER_INSTANCE

    provider_type = os.getenv("AI_PROVIDER", "mock").lower()

    if provider_type in ("mock", "test"):
        _PROVIDER_INSTANCE = MockAIProvider()
    elif provider_type in ("openai", "openai_compatible", "local", "deepseek", "ollama"):
        _PROVIDER_INSTANCE = OpenAICompatibleProvider()
    elif provider_type == "gemini":
        _PROVIDER_INSTANCE = GeminiProvider()
    else:
        _PROVIDER_INSTANCE = MockAIProvider()

    return _PROVIDER_INSTANCE

def reset_ai_provider():
    """Reset provider cache (useful for testing)."""
    global _PROVIDER_INSTANCE
    _PROVIDER_INSTANCE = None
