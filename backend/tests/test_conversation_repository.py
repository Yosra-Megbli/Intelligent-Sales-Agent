from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import ConversationChannel, ConversationState, LeadSource, MessageRole


def _make_lead_and_conversation(db_session):
    lead = LeadRepository(db_session).create(source=LeadSource.WEBSITE)
    conversation = ConversationRepository(db_session).create(
        lead_id=lead.id, channel=ConversationChannel.WEB
    )
    return lead, conversation


def test_new_conversation_starts_at_start_state(db_session):
    _, conversation = _make_lead_and_conversation(db_session)
    assert conversation.current_state == ConversationState.START


def test_transition_state_updates_current_state(db_session):
    repo = ConversationRepository(db_session)
    _, conversation = _make_lead_and_conversation(db_session)

    repo.transition_state(conversation, ConversationState.GREETING)
    assert conversation.current_state == ConversationState.GREETING


def test_count_active_excludes_closed_but_includes_handoff_and_rejected(db_session):
    repo = ConversationRepository(db_session)
    _, open_conv = _make_lead_and_conversation(db_session)
    _, handoff_conv = _make_lead_and_conversation(db_session)
    repo.transition_state(handoff_conv, ConversationState.HANDOFF)
    _, rejected_conv = _make_lead_and_conversation(db_session)
    repo.transition_state(rejected_conv, ConversationState.REJECTED)
    _, closed_conv = _make_lead_and_conversation(db_session)
    repo.transition_state(closed_conv, ConversationState.CLOSED)

    assert repo.count_active() == 3


def test_count_distinct_leads_in_state_deduplicates_per_lead(db_session):
    repo = ConversationRepository(db_session)
    lead = LeadRepository(db_session).create(source=LeadSource.WEBSITE)
    web_conv = repo.create(lead_id=lead.id, channel=ConversationChannel.WEB)
    telegram_conv = repo.create(lead_id=lead.id, channel=ConversationChannel.TELEGRAM)
    repo.transition_state(web_conv, ConversationState.HANDOFF)
    repo.transition_state(telegram_conv, ConversationState.HANDOFF)
    _, other_conv = _make_lead_and_conversation(db_session)
    repo.transition_state(other_conv, ConversationState.HANDOFF)

    assert repo.count_distinct_leads_in_state(ConversationState.HANDOFF) == 2


def test_detour_remembers_previous_state_and_resumes(db_session):
    repo = ConversationRepository(db_session)
    _, conversation = _make_lead_and_conversation(db_session)

    repo.transition_state(conversation, ConversationState.COLLECT_SUPPLIER)
    # Customer asks an off-topic question -> FAQ detour
    repo.transition_state(conversation, ConversationState.FAQ, remember_previous=True)
    assert conversation.current_state == ConversationState.FAQ
    assert conversation.previous_state == ConversationState.COLLECT_SUPPLIER

    # After answering the FAQ, resume exactly where we left off
    repo.resume_previous_state(conversation)
    assert conversation.current_state == ConversationState.COLLECT_SUPPLIER
    assert conversation.previous_state is None


def test_add_message_and_get_history_preserves_order(db_session):
    repo = ConversationRepository(db_session)
    _, conversation = _make_lead_and_conversation(db_session)

    repo.add_message(conversation, MessageRole.ASSISTANT, "Bonjour, je suis Sophie d'Ecofix.")
    repo.add_message(conversation, MessageRole.USER, "Je veux changer de fournisseur.")
    repo.add_message(conversation, MessageRole.ASSISTANT, "Dans quelle ville habitez-vous ?")

    history = repo.get_history(conversation)
    assert [m.role for m in history] == [
        MessageRole.ASSISTANT,
        MessageRole.USER,
        MessageRole.ASSISTANT,
    ]
    assert history[-1].content == "Dans quelle ville habitez-vous ?"
