"""Sanitize internal exceptions into user-friendly messages.

Keeps sensitive details (file paths, API key prefixes, stack traces) out of
SSE error events while preserving full context in server logs.
"""

import asyncio

try:
    import anthropic as _anthropic
except ImportError:
    _anthropic = None  # type: ignore[assignment]

try:
    import openai as _openai
except ImportError:
    _openai = None  # type: ignore[assignment]

import httpx


def sanitize_error(exc: Exception) -> str:
    """Map an exception to a safe, user-facing error message."""

    # LLM authentication errors
    if _anthropic and isinstance(exc, _anthropic.AuthenticationError):
        return "LLM service authentication failed. Check API key configuration."
    if _openai and isinstance(exc, _openai.AuthenticationError):
        return "LLM service authentication failed. Check API key configuration."

    # Timeouts
    if isinstance(exc, asyncio.TimeoutError):
        return "Generation timed out. The site may be too large or the AI service is slow."

    # HTTP fetch failures
    if isinstance(exc, httpx.HTTPError):
        return "Failed to fetch website content. The site may be unreachable."

    # JSON parse / value errors from extract_json
    if isinstance(exc, ValueError):
        return "AI returned an unexpected response. Please try again."

    # Fallback — never leak internal details
    return "An unexpected error occurred. Please try again."
