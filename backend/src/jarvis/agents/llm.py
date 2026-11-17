"""Provider-independent LLM adapter.

Supports OpenAI-compatible, Anthropic, and Ollama backends.
All LLM output is returned as raw text — callers MUST validate
against a Pydantic schema before use.

Set AI_PROVIDER=openai|anthropic|ollama in .env.
Leave blank → raises ConfigurationError at call time (not at import).
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
import structlog

from jarvis.core.errors import ConfigurationError, DependencyUnavailableError, retry_async

logger = structlog.get_logger(__name__)

_PROVIDER = os.getenv("AI_PROVIDER", "").strip().lower()
_OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
_ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")


class LLMError(DependencyUnavailableError):
    code = "llm_error"
    public_message = "LLM request failed."


async def complete(
    system: str,
    user: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    timeout: float = 60.0,
) -> str:
    """Send a system+user prompt, return the assistant text content.

    Provider is selected from AI_PROVIDER env var.
    Raises ConfigurationError if provider is not configured.
    """
    provider = _PROVIDER
    if not provider:
        raise ConfigurationError("AI_PROVIDER is not set — add it to .env before Phase 2")

    if provider == "openai":
        return await _openai_complete(system, user, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
    if provider == "anthropic":
        return await _anthropic_complete(system, user, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
    if provider == "ollama":
        return await _ollama_complete(system, user, temperature=temperature, max_tokens=max_tokens, timeout=timeout)

    raise ConfigurationError(f"Unknown AI_PROVIDER '{provider}'. Use: openai, anthropic, ollama")


async def complete_json(
    system: str,
    user: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Like complete() but parses and returns JSON. Retries on parse failure."""
    async def _attempt() -> dict[str, Any]:
        text = await complete(system, user, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
        # Strip markdown code fences if present
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0]
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM returned non-JSON: {text[:200]}") from exc

    return await retry_async(_attempt, attempts=3, base_delay=1.0, retry_on=(LLMError,), operation="llm.complete_json")


# ------------------------------------------------------------------ #
# OpenAI-compatible
# ------------------------------------------------------------------ #
async def _openai_complete(system: str, user: str, *, temperature: float, max_tokens: int, timeout: float) -> str:
    if not _OPENAI_KEY:
        raise ConfigurationError("OPENAI_API_KEY is not set")

    async def _call() -> str:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {_OPENAI_KEY}", "Content-Type": "application/json"},
                json={
                    "model": _OPENAI_MODEL,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            if response.status_code != 200:
                raise LLMError(f"OpenAI HTTP {response.status_code}")
            data = response.json()
            return data["choices"][0]["message"]["content"]

    return await retry_async(_call, attempts=3, base_delay=2.0, retry_on=(LLMError, httpx.TransportError), operation="llm.openai")


# ------------------------------------------------------------------ #
# Anthropic
# ------------------------------------------------------------------ #
async def _anthropic_complete(system: str, user: str, *, temperature: float, max_tokens: int, timeout: float) -> str:
    if not _ANTHROPIC_KEY:
        raise ConfigurationError("ANTHROPIC_API_KEY is not set")

    async def _call() -> str:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": _ANTHROPIC_KEY,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _ANTHROPIC_MODEL,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            if response.status_code != 200:
                raise LLMError(f"Anthropic HTTP {response.status_code}: {response.text[:200]}")
            data = response.json()
            return data["content"][0]["text"]

    return await retry_async(_call, attempts=3, base_delay=2.0, retry_on=(LLMError, httpx.TransportError), operation="llm.anthropic")


# ------------------------------------------------------------------ #
# Ollama
# ------------------------------------------------------------------ #
async def _ollama_complete(system: str, user: str, *, temperature: float, max_tokens: int, timeout: float) -> str:
    async def _call() -> str:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{_OLLAMA_URL}/api/chat",
                json={
                    "model": _OLLAMA_MODEL,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            if response.status_code != 200:
                raise LLMError(f"Ollama HTTP {response.status_code}")
            data = response.json()
            return data["message"]["content"]

    return await retry_async(_call, attempts=3, base_delay=1.0, retry_on=(LLMError, httpx.TransportError), operation="llm.ollama")
