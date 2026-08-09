"""
Architecture boundary tests.

Phase 4A's whole point (per the architecture review) is that Channels never
know the Business Engine or `ai/*` exist - only `application/
conversation_service.py`'s `ConversationService` does. These tests enforce
that boundary at the import level, so a future channel (Telegram, WhatsApp,
Voice) - or a future edit to this one - can't quietly reach around
`ConversationService` and re-couple a Channel to the Engine, the way
`channels/web.py` itself used to before this layer existed.

Same AST-based technique as the purity tests in ai/extractor.py,
ai/responder.py, ai/rag.py - reading imports rather than running the code,
so this stays fast and can't be fooled by runtime conditionals.
"""

import ast
import inspect

_ENGINE_AND_AI_MODULES = (
    "conversation_engine.engine",
    "conversation_engine.rules",
    "conversation_engine.state_machine",
    "conversation_engine.memory",
    "conversation_engine.transitions",
    "ai.extractor",
    "ai.rag",
    "ai.responder",
)

# `ai.providers.interface`'s `LLMProvider` is the abstract vendor-agnostic
# type Channels accept and pass through to `ConversationService` - it's a
# type contract, not business logic, so importing it doesn't reach around
# the Application layer the way importing ai.extractor/rag/responder would.


def _imported_module_names(module) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_web_channel_never_imports_the_engine_or_ai_directly():
    """channels/web.py must only reach the Engine/ai through
    ConversationService - that's the entire reason Phase 4A exists."""
    from channels import web as web_channel_module

    imported = _imported_module_names(web_channel_module)
    leaked = {name for name in imported if any(name.startswith(m) for m in _ENGINE_AND_AI_MODULES)}
    assert not leaked, f"channels/web.py must not import these directly: {leaked}"


def test_api_routes_never_import_the_engine_ai_or_repositories_directly():
    """api/routes.py must only reach the Engine through WebChannel - not
    even the repositories, so a second HTTP surface (e.g. an admin API)
    can't silently start bypassing the Application layer either."""
    from api import routes as routes_module

    imported = _imported_module_names(routes_module)
    forbidden = _ENGINE_AND_AI_MODULES + ("crm.lead_repository", "crm.conversation_repository")
    leaked = {name for name in imported if any(name.startswith(m) for m in forbidden)}
    assert not leaked, f"api/routes.py must not import these directly: {leaked}"


def test_conversation_service_is_the_only_place_allowed_to_import_both():
    """Sanity check the boundary is meaningful: ConversationService really
    does import both sides, otherwise the two tests above would be trivially
    satisfied by simply never building the feature."""
    from application import conversation_service as service_module

    imported = _imported_module_names(service_module)
    assert any(name.startswith("conversation_engine") for name in imported)
    assert any(name.startswith("ai.") for name in imported)


def test_dashboard_routes_never_import_repositories_or_engine_directly():
    """api/dashboard_routes.py must only reach the data layer through
    DashboardService - same rule as api/routes.py around WebChannel, so a
    read-only dashboard can't quietly become a second, undisciplined path
    into the repositories."""
    from api import dashboard_routes as dashboard_routes_module

    imported = _imported_module_names(dashboard_routes_module)
    forbidden = _ENGINE_AND_AI_MODULES + ("crm.lead_repository", "crm.conversation_repository", "crm.activity_repository")
    leaked = {name for name in imported if any(name.startswith(m) for m in forbidden)}
    assert not leaked, f"api/dashboard_routes.py must not import these directly: {leaked}"


def test_leads_routes_never_import_repositories_or_engine_directly():
    """api/leads_routes.py (CSV import + lead detail/history) must only
    reach the data layer through LeadImportService/DashboardService - same
    rule as api/dashboard_routes.py around DashboardService."""
    from api import leads_routes as leads_routes_module

    imported = _imported_module_names(leads_routes_module)
    forbidden = _ENGINE_AND_AI_MODULES + ("crm.lead_repository", "crm.conversation_repository", "crm.activity_repository")
    leaked = {name for name in imported if any(name.startswith(m) for m in forbidden)}
    assert not leaked, f"api/leads_routes.py must not import these directly: {leaked}"


def test_campaign_routes_never_import_repositories_engine_or_outbound_internals_directly():
    """api/campaign_routes.py (Phase 8) must only reach the data layer
    through CampaignService - same rule as api/dashboard_routes.py around
    DashboardService, extended to also forbid reaching around CampaignService
    into CampaignEngine/OutboundSender/OutboundScheduler directly."""
    from api import campaign_routes as campaign_routes_module

    imported = _imported_module_names(campaign_routes_module)
    forbidden = _ENGINE_AND_AI_MODULES + (
        "crm.lead_repository",
        "crm.conversation_repository",
        "crm.activity_repository",
        "crm.campaign_repository",
        "outbound.campaign_engine",
        "outbound.sender",
        "outbound.scheduler",
    )
    leaked = {name for name in imported if any(name.startswith(m) for m in forbidden)}
    assert not leaked, f"api/campaign_routes.py must not import these directly: {leaked}"


def test_voice_routes_never_import_repositories_engine_or_outbound_internals_directly():
    """api/voice_routes.py (Voice E, outbound dial-out) must only reach the
    data layer through VoiceOutboundService - same rule as
    api/campaign_routes.py around CampaignService, extended to also forbid
    reaching around it into the repositories, OutboundVoiceSender, or a
    concrete TelephonyProvider implementation directly."""
    from api import voice_routes as voice_routes_module

    imported = _imported_module_names(voice_routes_module)
    forbidden = _ENGINE_AND_AI_MODULES + (
        "crm.lead_repository",
        "crm.conversation_repository",
        "crm.activity_repository",
        "crm.campaign_repository",
        "outbound.voice_sender",
        "channels.voice.providers.twilio_telephony",
    )
    leaked = {name for name in imported if any(name.startswith(m) for m in forbidden)}
    assert not leaked, f"api/voice_routes.py must not import these directly: {leaked}"


def test_voice_outbound_service_never_imports_ai_or_conversation_engine():
    """VoiceOutboundService (Voice E) only resolves lead_id/campaign_id
    into rows and hands them to OutboundVoiceSender - same rule as
    CampaignService, it never needs the Engine or ai/* directly."""
    from application import voice_outbound_service as voice_outbound_service_module

    imported = _imported_module_names(voice_outbound_service_module)
    leaked = {name for name in imported if any(name.startswith(m) for m in _ENGINE_AND_AI_MODULES)}
    assert not leaked, f"application/voice_outbound_service.py must not import these directly: {leaked}"


def test_outbound_voice_sender_never_imports_ai_or_conversation_engine():
    """outbound/voice_sender.py places a call and updates CRM bookkeeping
    only - like outbound/sender.py, it must never import the Engine or
    ai/* directly (see its own module docstring's PURITY BOUNDARY note)."""
    import outbound.voice_sender as voice_sender_module

    imported = _imported_module_names(voice_sender_module)
    leaked = {name for name in imported if any(name.startswith(m) for m in _ENGINE_AND_AI_MODULES)}
    assert not leaked, f"outbound/voice_sender.py must not import these directly: {leaked}"


def test_telephony_providers_never_import_the_engine_ai_or_application_layer():
    """Same discipline as
    test_voice_stt_and_tts_providers_never_import_the_engine_ai_or_application_layer:
    even the outbound dial-out TelephonyProvider abstraction and its Twilio
    implementation must not know ConversationService, the Engine, or ai/*
    exist - dialing a phone is a transport concern, never a business
    decision."""
    from channels.voice.providers import telephony_interface as telephony_interface_module
    from channels.voice.providers import twilio_telephony as twilio_telephony_module

    forbidden = _ENGINE_AND_AI_MODULES + ("application",)
    for module in (telephony_interface_module, twilio_telephony_module):
        imported = _imported_module_names(module)
        leaked = {name for name in imported if any(name.startswith(m) for m in forbidden)}
        assert not leaked, f"{module.__name__} must not import these directly: {leaked}"


def test_campaign_service_never_imports_ai_or_conversation_engine():
    """CampaignService (Phase 8) orchestrates CampaignEngine/OutboundScheduler
    - it never needs to know the Engine or ai/* exist directly, same rule as
    CampaignEngine itself."""
    from application import campaign_service as campaign_service_module

    imported = _imported_module_names(campaign_service_module)
    leaked = {name for name in imported if any(name.startswith(m) for m in _ENGINE_AND_AI_MODULES)}
    assert not leaked, f"application/campaign_service.py must not import these directly: {leaked}"


def test_lead_import_service_never_imports_the_engine_or_ai():
    """LeadImportService only creates/updates CRM data from a CSV row - it
    never makes a qualification/dialogue decision, so it must never import
    conversation_engine or ai/* (same rule as DashboardService/CampaignEngine)."""
    from application import lead_import_service as lead_import_service_module

    imported = _imported_module_names(lead_import_service_module)
    leaked = {name for name in imported if any(name.startswith(m) for m in _ENGINE_AND_AI_MODULES)}
    assert not leaked, f"application/lead_import_service.py must not import these directly: {leaked}"


def test_lead_service_never_imports_the_engine_or_ai():
    """LeadService (Dashboard edit/delete-lead actions) only writes CRM
    data - same rule as LeadImportService: it must never import
    conversation_engine or ai/*, since a field edit or delete is never a
    qualification/dialogue decision."""
    from application import lead_service as lead_service_module

    imported = _imported_module_names(lead_service_module)
    leaked = {name for name in imported if any(name.startswith(m) for m in _ENGINE_AND_AI_MODULES)}
    assert not leaked, f"application/lead_service.py must not import these directly: {leaked}"


def test_dashboard_service_never_imports_the_engine_or_ai():
    """DashboardService is read-only reporting, not a use-case that talks to
    the LLM or the Business Engine - unlike ConversationService, it should
    never need either."""
    from application import dashboard_service as dashboard_service_module

    imported = _imported_module_names(dashboard_service_module)
    leaked = {name for name in imported if any(name.startswith(m) for m in _ENGINE_AND_AI_MODULES)}
    assert not leaked, f"application/dashboard_service.py must not import these directly: {leaked}"


def test_campaign_engine_never_imports_ai_or_conversation_engine():
    """CampaignEngine decides WHO/WHEN to contact - never the language
    (ai/*) and never the dialogue/qualification logic (conversation_engine).
    Sending + greeting is outbound/sender.py's job, via ConversationService."""
    import outbound.campaign_engine as campaign_engine_module

    imported = _imported_module_names(campaign_engine_module)
    assert not any(name.startswith("ai.") or name == "ai" for name in imported)
    assert not any(name.startswith("conversation_engine") for name in imported)


def test_voice_session_manager_never_imports_the_engine_or_ai_directly():
    """channels/voice/session_manager.py (Voice C) must only reach the
    Engine/ai through ConversationService, exactly like every other
    channel - see docs/architecture/voice_c_responsibilities.md."""
    from channels.voice import session_manager as voice_session_manager_module

    imported = _imported_module_names(voice_session_manager_module)
    leaked = {name for name in imported if any(name.startswith(m) for m in _ENGINE_AND_AI_MODULES)}
    assert not leaked, f"channels/voice/session_manager.py must not import these directly: {leaked}"


def test_voice_stt_and_tts_providers_never_import_the_engine_ai_or_application_layer():
    """Even the Tier A Twilio STT/TTS providers - which make no network or
    business decisions at all - must not know ConversationService, the
    Engine, or ai/* exist. (Each provider module also carries its own
    dedicated copy of this check in tests/test_voice_stt_provider.py /
    test_voice_tts_provider.py; re-asserted here too so this file remains
    the single place that lists every architectural boundary in one spot.)
    """
    from channels.voice.providers import twilio_stt as twilio_stt_module
    from channels.voice.providers import twilio_tts as twilio_tts_module

    forbidden = _ENGINE_AND_AI_MODULES + ("application",)
    for module in (twilio_stt_module, twilio_tts_module):
        imported = _imported_module_names(module)
        leaked = {name for name in imported if any(name.startswith(m) for m in forbidden)}
        assert not leaked, f"{module.__name__} must not import these directly: {leaked}"
    """Architecture review requirement: 'no Prompt is written inside Python;
    every Prompt is Markdown or YAML under prompts/'. ai/extractor.py and
    ai/responder.py must load all prompt/talking-point/fallback text via
    ai.prompt_loader, never define it as a Python string literal themselves.
    """
    import ai.extractor as extractor_module
    import ai.responder as responder_module

    for module in (extractor_module, responder_module):
        tree = ast.parse(inspect.getsource(module))
        imported = _imported_module_names(module)
        assert "ai.prompt_loader" in imported, (
            f"{module.__name__} must load its prompt content via ai.prompt_loader"
        )
        for node in ast.walk(tree):
            # A module-level assignment to a multi-line string literal is
            # exactly the "hardcoded prompt" shape this test guards against.
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, str) and "\n" in node.value.value:
                    raise AssertionError(
                        f"{module.__name__} appears to hardcode a multi-line "
                        f"string (a prompt) instead of loading it from prompts/"
                    )
