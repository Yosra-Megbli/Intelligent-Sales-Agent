"""
Groq provider.

Concrete `LLMProvider` implementation backed by Groq's OpenAI-compatible
chat completions API. Retries transient failures (timeouts, connection
errors, rate limits) with exponential backoff; translates every vendor
exception into an `LLMError` subclass so nothing above this module ever
needs to know Groq exists.

The `groq` package is an optional dependency: importing this module never
fails even if it isn't installed, so `pytest tests/` still works without it.
Only instantiating `GroqProvider` (or injecting a fake `client=`) requires
it, or an explicit `client=` for tests.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

from ai.providers.interface import (
    LLMAuthenticationError,
    LLMError,
    LLMMessage,
    LLMProvider,
    LLMRateLimitError,
    LLMResponse,
    LLMRole,
    LLMTimeoutError,
)

try:
    from groq import Groq
except ImportError:  # pragma: no cover - exercised via injected `client=` in tests
    Groq = None  # type: ignore[assignment,misc]

# openai/gpt-oss-120b: Groq's largest general-purpose model as of 2026-08,
# chosen over the smaller/faster llama-3.3-70b-versatile for better
# conversational quality on sales/negotiation dialogue - this is what the
# client demo is judged on. (meta-llama/llama-4-maverick-17b-128e-instruct,
# used previously, was deprecated by Groq on 2026-02-20 in favor of this
# model.) Still fully free-tier eligible; override with GROQ_MODEL env var
# to trade quality for the smaller/faster models if rate limits become an
# issue during the pilot.
DEFAULT_MODEL = "openai/gpt-oss-120b"

# Vendor exception class names that are worth retrying vs. failing fast.
# Matched by name (not isinstance) so this module works whether or not the
# real `groq` package is installed - a fake client in tests can raise plain
# exceptions with these names and get the same retry behaviour as production.
_RETRYABLE_ERROR_NAMES = {"RateLimitError", "APITimeoutError", "APIConnectionError"}
_AUTH_ERROR_NAMES = {"AuthenticationError"}


class GroqProvider(LLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 20.0,
        max_retries: int = 3,
        client: Optional[Any] = None,
    ):
        self.model = model or os.getenv("GROQ_MODEL", DEFAULT_MODEL)
        self.max_retries = max_retries

        if client is not None:
            self._client = client
            return

        api_key = api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise LLMAuthenticationError("GROQ_API_KEY is not set")
        if Groq is None:
            raise LLMError(
                "the 'groq' package is not installed - run: pip install groq"
            )
        self._client = Groq(api_key=api_key, timeout=timeout)

    def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResponse:
        payload = [
            {"role": m.role.value if isinstance(m.role, LLMRole) else m.role, "content": m.content}
            for m in messages
        ]
        kwargs: dict[str, Any] = dict(
            model=self.model,
            messages=payload,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                completion = self._client.chat.completions.create(**kwargs)
                return self._to_llm_response(completion)
            except Exception as exc:  # noqa: BLE001 - classified by name below
                error_name = type(exc).__name__

                if error_name in _AUTH_ERROR_NAMES:
                    raise LLMAuthenticationError(str(exc)) from exc

                if error_name in _RETRYABLE_ERROR_NAMES:
                    last_error = exc
                    if attempt < self.max_retries - 1:
                        self._sleep_backoff(attempt)
                    continue

                # Anything else (bad request, malformed response, ...) is not
                # transient - retrying it would just fail the same way again.
                raise LLMError(str(exc)) from exc

        if isinstance(last_error, Exception) and type(last_error).__name__ == "RateLimitError":
            raise LLMRateLimitError(str(last_error)) from last_error
        raise LLMTimeoutError(str(last_error)) from last_error

    @staticmethod
    def _to_llm_response(completion: Any) -> LLMResponse:
        choice = completion.choices[0]
        usage = getattr(completion, "usage", None)
        raw: dict[str, Any] = {}
        if hasattr(completion, "model_dump"):
            try:
                raw = completion.model_dump()
            except Exception:  # noqa: BLE001 - raw payload is best-effort only
                raw = {}
        return LLMResponse(
            content=choice.message.content or "",
            model=getattr(completion, "model", None) or "",
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            raw=raw,
        )

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        time.sleep(min(2**attempt * 0.5, 8))
