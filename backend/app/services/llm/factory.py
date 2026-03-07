from app.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.anthropic import AnthropicProvider
from app.services.llm.openai import OpenAIProvider


def get_llm_provider() -> LLMProvider:
    """
    Returns the configured LLM provider based on settings.llm_provider.
    Swap providers by changing the LLM_PROVIDER env var.
    """
    match settings.llm_provider:
        case "anthropic":
            return AnthropicProvider()
        case "openai":
            return OpenAIProvider()
        case _:
            raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
