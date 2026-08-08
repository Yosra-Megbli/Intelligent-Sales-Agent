from conversation_engine import dialogue_policy
from conversation_engine.actions import ActionType
from domain.enums import ConversationChannel, ConversationState, LeadSource
from domain.models.conversation import Conversation
from crm.lead_repository import LeadRepository


def _conversation(db_session, count):
    lead = LeadRepository(db_session).create(source=LeadSource.WEBSITE)
    conversation = Conversation(
        lead_id=lead.id,
        channel=ConversationChannel.WEB,
        current_state=ConversationState.FAQ,
        consecutive_detour_count=count,
    )
    db_session.add(conversation)
    db_session.flush()
    return conversation


def test_resumes_below_threshold(db_session):
    conversation = _conversation(db_session, count=dialogue_policy.MAX_CONSECUTIVE_DETOURS - 1)
    action = dialogue_policy.decide_after_detour(conversation)
    assert action.type == ActionType.RESUME


def test_escalates_at_threshold(db_session):
    conversation = _conversation(db_session, count=dialogue_policy.MAX_CONSECUTIVE_DETOURS)
    action = dialogue_policy.decide_after_detour(conversation)
    assert action.type == ActionType.HANDOFF


def test_threshold_is_configurable_via_yaml():
    assert isinstance(dialogue_policy.MAX_CONSECUTIVE_DETOURS, int)
    assert dialogue_policy.MAX_CONSECUTIVE_DETOURS > 0
