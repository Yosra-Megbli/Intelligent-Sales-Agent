"""
LLM Provider interface.

This is the abstraction boundary between the rest of the system and any
concrete LLM vendor (Groq today, Gemini/OpenAI later per docs/08_LLM_ARCHITECTURE.md).
Everything above this layer (extractor, responder, RAG - Phase 3B/3C/3D/3E)
talks to an `LLMProvider`, never to a vendor SDK directly. Swapping Groq for
another provider means writing a new class in this package; nothing else in
the codebase changes.

Golden rule (from ai/README.md): this package only calls an LLM and returns
its raw text output. It never decides a Lead's status, qualification score,
or Conversation's current_state - those decisions belong to the Business
Rules Engine (Phase 2). This layer doesn't know what a "Lead" is.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class LLMRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class LLMMessage:
    role: LLMRole
    content: str


@dataclass
class LLMResponse:
    """The full result of one call. `content` is the only field Phase
    3B/3C/3D actually need; the rest is kept for logging/cost tracking."""

    content: str
    model: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    raw: dict[str, Any] = field(default_factory=dict)


class LLMError(Exception):
    """Base class for every error this package raises. Callers catch this -
    never a vendor-specific exception - so the rest of the system stays
    decoupled from which provider is configured."""


class LLMTimeoutError(LLMError):
    """The provider did not respond in time, including after retries."""


class LLMRateLimitError(LLMError):
    """The provider rejected the call for rate-limit reasons, including
    after retries."""


class LLMAuthenticationError(LLMError):
    """Missing or invalid API key. Never retried."""


class LLMProvider(ABC):
    """Every concrete provider (Groq, Gemini, OpenAI, ...) implements this
    contract. `generate` is intentionally the only method: structured
    extraction is "ask for JSON text and let ai/extractor.py (Phase 3B)
    parse and validate it", not a separate code path per vendor.
    """

    @abstractmethod
    def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Send `messages` to the LLM and return its response.

        `json_mode=True` asks the provider to constrain output to valid JSON
        where the vendor supports it. Callers are still responsible for
        parsing/validating that JSON - this layer never interprets content.

        Must raise an `LLMError` subclass on failure, never a vendor SDK
        exception directly.
        """
        raise NotImplementedError
