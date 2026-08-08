"""
Tests for the Phase 3A LLM adapter.

Uses a fake Groq client (duck-typed: `.chat.completions.create(**kwargs)`)
instead of the real `groq` SDK, so these tests run without network access
and without the package installed - only `GroqProvider(client=fake)` needs
it, never the module import.
"""

import pytest

from ai.providers.groq import GroqProvider
from ai.providers.interface import (
    LLMAuthenticationError,
    LLMError,
    LLMMessage,
    LLMRateLimitError,
    LLMRole,
    LLMTimeoutError,
)


# --- fakes ------------------------------------------------------------


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeUsage:
    def __init__(self, prompt_tokens=10, completion_tokens=5):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class FakeCompletion:
    def __init__(self, content, model="llama-3.3-70b-versatile"):
        self.choices = [FakeChoice(content)]
        self.usage = FakeUsage()
        self.model = model

    def model_dump(self):
        return {"model": self.model, "choices": ["..."]}


class RateLimitError(Exception):
    pass


class APITimeoutError(Exception):
    pass


class APIConnectionError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class BadRequestError(Exception):
    pass


class FakeCompletions:
    def __init__(self, responses):
        # responses: list of FakeCompletion or Exception instances, consumed in order
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeChat:
    def __init__(self, completions):
        self.completions = completions


class FakeGroqClient:
    def __init__(self, responses):
        self.chat = FakeChat(FakeCompletions(responses))


# --- helpers ------------------------------------------------------------


def make_provider(responses, max_retries=3, monkeypatch=None):
    client = FakeGroqClient(responses)
    if monkeypatch is not None:
        monkeypatch.setattr("ai.providers.groq.time.sleep", lambda _seconds: None)
    return GroqProvider(client=client, max_retries=max_retries), client


# --- tests ------------------------------------------------------------


def test_generate_happy_path(monkeypatch):
    provider, client = make_provider([FakeCompletion("Bonjour, comment puis-je vous aider ?")])

    response = provider.generate([LLMMessage(role=LLMRole.USER, content="Bonjour")])

    assert response.content == "Bonjour, comment puis-je vous aider ?"
    assert response.prompt_tokens == 10
    assert response.completion_tokens == 5
    assert client.chat.completions.calls[0]["model"] == provider.model


def test_generate_sends_roles_as_plain_strings():
    provider, client = make_provider([FakeCompletion("ok")])

    provider.generate(
        [
            LLMMessage(role=LLMRole.SYSTEM, content="You are Sophie."),
            LLMMessage(role=LLMRole.USER, content="Bonjour"),
        ]
    )

    sent = client.chat.completions.calls[0]["messages"]
    assert sent == [
        {"role": "system", "content": "You are Sophie."},
        {"role": "user", "content": "Bonjour"},
    ]


def test_json_mode_sets_response_format():
    provider, client = make_provider([FakeCompletion('{"intent": "question"}')])

    provider.generate([LLMMessage(role=LLMRole.USER, content="?")], json_mode=True)

    assert client.chat.completions.calls[0]["response_format"] == {"type": "json_object"}


def test_json_mode_defaults_to_off():
    provider, client = make_provider([FakeCompletion("plain text")])

    provider.generate([LLMMessage(role=LLMRole.USER, content="hi")])

    assert "response_format" not in client.chat.completions.calls[0]


def test_retries_transient_errors_then_succeeds(monkeypatch):
    provider, client = make_provider(
        [APITimeoutError("slow"), RateLimitError("429"), FakeCompletion("recovered")],
        max_retries=3,
        monkeypatch=monkeypatch,
    )

    response = provider.generate([LLMMessage(role=LLMRole.USER, content="hi")])

    assert response.content == "recovered"
    assert len(client.chat.completions.calls) == 3


def test_exhausted_retries_raise_rate_limit_error(monkeypatch):
    provider, _ = make_provider(
        [RateLimitError("429"), RateLimitError("429"), RateLimitError("429")],
        max_retries=3,
        monkeypatch=monkeypatch,
    )

    with pytest.raises(LLMRateLimitError):
        provider.generate([LLMMessage(role=LLMRole.USER, content="hi")])


def test_exhausted_retries_on_timeout_raise_llm_timeout_error(monkeypatch):
    provider, _ = make_provider(
        [APITimeoutError("t"), APIConnectionError("c"), APITimeoutError("t")],
        max_retries=3,
        monkeypatch=monkeypatch,
    )

    with pytest.raises(LLMTimeoutError):
        provider.generate([LLMMessage(role=LLMRole.USER, content="hi")])


def test_authentication_error_is_never_retried():
    provider, client = make_provider([AuthenticationError("bad key"), FakeCompletion("unreachable")])

    with pytest.raises(LLMAuthenticationError):
        provider.generate([LLMMessage(role=LLMRole.USER, content="hi")])

    assert len(client.chat.completions.calls) == 1


def test_non_retryable_error_is_wrapped_and_not_retried():
    provider, client = make_provider([BadRequestError("malformed"), FakeCompletion("unreachable")])

    with pytest.raises(LLMError):
        provider.generate([LLMMessage(role=LLMRole.USER, content="hi")])

    assert len(client.chat.completions.calls) == 1


def test_missing_api_key_raises_authentication_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(LLMAuthenticationError):
        GroqProvider()


def test_model_defaults_to_env_var(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "custom-model")
    client = FakeGroqClient([FakeCompletion("ok")])

    provider = GroqProvider(client=client)

    assert provider.model == "custom-model"


def test_explicit_model_overrides_env_var(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "custom-model")
    client = FakeGroqClient([FakeCompletion("ok")])

    provider = GroqProvider(client=client, model="explicit-model")

    assert provider.model == "explicit-model"


def test_groq_module_never_touches_the_database_or_crm():
    """Golden rule from ai/README.md: nothing in ai/ may write to
    Lead.status, Lead.qualification_score, or Conversation.current_state -
    checked via AST, same technique as
    test_rules_module_never_touches_the_database, so this holds even as the
    provider grows (retries, streaming, new vendors) without relying on a
    reviewer noticing an extra import by hand.
    """
    import ast
    import inspect

    from ai.providers import groq as groq_module

    tree = ast.parse(inspect.getsource(groq_module))

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = getattr(node, "module", None) or ""
            names = [alias.name for alias in node.names]
            assert "crm" not in module_name and not any(
                "repository" in n.lower() for n in names
            ), f"ai/providers/groq.py must not import repositories, found: {module_name or names}"
            assert "domain" not in module_name, (
                f"ai/providers/groq.py must not import domain models - it doesn't know "
                f"what a Lead is, found: {module_name}"
            )
