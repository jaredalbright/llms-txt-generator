"""Tests for error sanitization."""

import asyncio

import httpx
import pytest

from app.services.errors import sanitize_error


# --- Anthropic auth error ---

def test_anthropic_auth_error():
    try:
        import anthropic
    except ImportError:
        pytest.skip("anthropic not installed")

    exc = anthropic.AuthenticationError(
        message="Invalid API Key sk-ant-api03-XXXX...",
        response=httpx.Response(401, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")),
        body={"error": {"type": "authentication_error", "message": "invalid x-api-key"}},
    )
    result = sanitize_error(exc)
    assert result == "LLM service authentication failed. Check API key configuration."
    assert "sk-ant" not in result


# --- OpenAI auth error ---

def test_openai_auth_error():
    try:
        import openai
    except ImportError:
        pytest.skip("openai not installed")

    exc = openai.AuthenticationError(
        message="Incorrect API key provided: sk-proj-XXXX...",
        response=httpx.Response(401, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions")),
        body={"error": {"message": "Incorrect API key", "type": "invalid_request_error"}},
    )
    result = sanitize_error(exc)
    assert result == "LLM service authentication failed. Check API key configuration."
    assert "sk-proj" not in result


# --- Timeout ---

def test_timeout_error():
    result = sanitize_error(asyncio.TimeoutError())
    assert "timed out" in result


# --- HTTP errors ---

def test_http_error():
    exc = httpx.ConnectError("Connection refused")
    result = sanitize_error(exc)
    assert result == "Failed to fetch website content. The site may be unreachable."
    assert "Connection refused" not in result


# --- ValueError (JSON parse) ---

def test_value_error():
    exc = ValueError("No JSON found in response at /app/services/llm/utils.py:42")
    result = sanitize_error(exc)
    assert result == "AI returned an unexpected response. Please try again."
    assert "/app/services" not in result


# --- Fallback ---

def test_fallback_unknown_exception():
    exc = RuntimeError("segfault in worker pool at 0xDEADBEEF")
    result = sanitize_error(exc)
    assert result == "An unexpected error occurred. Please try again."
    assert "segfault" not in result
    assert "0xDEADBEEF" not in result


def test_original_details_never_leak():
    """Verify that no sanitized message contains the original exception text."""
    cases = [
        asyncio.TimeoutError(),
        httpx.ConnectError("secret-internal-host.corp:5432"),
        ValueError("/home/deploy/app/secrets.py line 12"),
        RuntimeError("password=hunter2"),
    ]
    for exc in cases:
        result = sanitize_error(exc)
        assert str(exc) not in result or str(exc) == ""
