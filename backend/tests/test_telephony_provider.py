"""
Tests for channels/voice/providers/telephony_interface.py - the outbound
dial-out abstraction (Voice E). Same discipline as
tests/test_voice_stt_provider.py/tests/test_voice_tts_provider.py: plain
dataclass/exception-shape tests plus an architecture-purity check (also
re-asserted in tests/test_architecture_boundaries.py).
"""

import pytest

from channels.voice.providers.telephony_interface import (
    CallRequest,
    CallResult,
    InvalidPhoneNumberError,
    TelephonyAuthenticationError,
    TelephonyError,
    TelephonyNotConfiguredError,
    TelephonyProvider,
    TelephonyUnavailableError,
)


def test_call_request_carries_the_webhook_url_through_unmodified():
    request = CallRequest(to_number="+32491234567", webhook_url="https://api.ecofix.be/api/voice/twiml")
    assert request.webhook_url == "https://api.ecofix.be/api/voice/twiml"
    assert request.from_number is None


def test_call_result_defaults_raw_to_an_empty_dict_not_none():
    result = CallResult(provider_call_id="CA123", status="queued")
    assert result.raw == {}


def test_every_telephony_exception_is_a_telephony_error():
    for exc_cls in (
        TelephonyUnavailableError,
        TelephonyAuthenticationError,
        InvalidPhoneNumberError,
        TelephonyNotConfiguredError,
    ):
        assert issubclass(exc_cls, TelephonyError)


def test_telephony_provider_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        TelephonyProvider()  # type: ignore[abstract]


def test_a_minimal_concrete_provider_must_implement_initiate_call():
    class Incomplete(TelephonyProvider):
        pass

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]

    class Minimal(TelephonyProvider):
        def initiate_call(self, request):
            return CallResult(provider_call_id="CA1", status="queued")

    provider = Minimal()
    result = provider.initiate_call(CallRequest(to_number="+32491234567", webhook_url="https://x/twiml"))
    assert result.status == "queued"


# --- architecture purity ------------------------------------------------------


def test_telephony_interface_module_never_imports_conversation_engine_or_application_layer():
    import ast
    import inspect

    from channels.voice.providers import telephony_interface as telephony_interface_module

    tree = ast.parse(inspect.getsource(telephony_interface_module))
    forbidden_prefixes = ("conversation_engine", "application", "ai.extractor", "ai.rag", "ai.responder", "crm")

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = getattr(node, "module", None) or ""
            names = [alias.name for alias in node.names]
            assert not any(module_name.startswith(p) for p in forbidden_prefixes), (
                f"channels/voice/providers/telephony_interface.py must not import: {module_name or names}"
            )
