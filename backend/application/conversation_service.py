"""
Conversation Service (Application / Use-Cases layer).

Phase 4A: sits between every Channel (Web, Telegram, WhatsApp, Voice, ...)
and the pure Business Engine + `ai/*` packages. This is the *only* module
allowed to import both `conversation_engine/` and `ai/*` - no Channel does
this directly anymore (see `channels/web.py`, now a thin adapter).

Each Channel converts its own transport format (HTTP JSON, a Telegram
`Update`, a WhatsApp webhook payload, a voice transcript...) into a
`ConversationRequest`, calls `ConversationService.handle_message()`, and
turns the returned `ConversationResponse` back into whatever that channel
needs to send. A second, third, or fourth channel gets the full extractor
-> engine -> rag -> responder -> persistence pipeline for free, instead of
re-implementing (or subtly re-diverging from) it per channel.

This module contains no business logic of its own: every decision it
relays comes from `conversation_engine` (what to do) or `ai` (what to say)
- it only sequences the calls, maps between their two different
vocabularies (`_REQUIRED_ACTION_TO_EXPECTED_FIELD` and
`_RAG_CATEGORY_BY_ACTION` below are purely mechanical lookups, not
decisions), and persists messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from ai.extractor import Extractor
from ai.providers.interface import LLMProvider
from ai.rag import Rag
from ai.responder import Responder
from conversation_engine.engine import ConversationEngine, EngineResult
from conversation_engine.memory import ConversationMemory
from conversation_engine.transitions import Event, EventType
from crm.conversation_repository import ConversationRepository
from crm.lead_repository import LeadRepository
from domain.enums import ConversationChannel, ConversationState, LeadSource, MessageRole
from domain.models.conversation import Conversation
from domain.models.lead import Lead
from domain.models.message import Message

# Maps a `required_action` (the *previous* turn's question, read from
# ConversationMemory) to the field-group name ai/extractor.py accepts as
# `expected_field` context. Purely a vocabulary bridge between the two
# layers' naming - the extractor never learns what a "ConversationState" is,
# and this map doesn't decide anything either layer wouldn't already agree on.
_REQUIRED_ACTION_TO_EXPECTED_FIELD: dict[str, str] = {
    "ASK_CUSTOMER_TYPE": "customer_type",
    "ASK_LOCATION": "location",
    "ASK_SUPPLIER": "current_supplier",
    "ASK_CONTACT": "contact",
    "ASK_EAN": "ean",
    "ASK_EAN_CORRECTION": "ean",
    "ASK_CONTACT_CORRECTION": "contact",
}

# Maps the engine's required_action to the RAG category to query. Only these
# two actions ever need a looked-up fact; every other action's talking point
# is fixed (see ai/responder.py's _TALKING_POINTS).
_RAG_CATEGORY_BY_ACTION: dict[str, str] = {
    "ANSWER_FAQ": "faq",
    "ANSWER_OBJECTION": "objection",
}

# Maps a Channel to the LeadSource a new lead started on that channel should
# be recorded with. Falls back to WEBSITE for any channel not listed yet
# (e.g. before WhatsApp/Voice get their own LeadSource values).
_LEAD_SOURCE_BY_CHANNEL: dict[ConversationChannel, LeadSource] = {
    ConversationChannel.WEB: LeadSource.WEBSITE,
    ConversationChannel.TELEGRAM: LeadSource.TELEGRAM,
    ConversationChannel.WHATSAPP: LeadSource.WHATSAPP,
    ConversationChannel.VOICE: LeadSource.VOICE,
}


@dataclass
class ConversationRequest:
    """Channel-agnostic input to `ConversationService.handle_message()`.

    Every channel builds one of these from its own transport format -
    a Telegram channel reads `update.message.text`, a WhatsApp channel
    reads the webhook's message body, a voice channel reads a transcript -
    but the field names here never leak any transport-specific shape.
    """

    conversation_id: UUID
    text: str


@dataclass
class ConversationResponse:
    """Channel-agnostic output. `engine_result` is kept for
    debugging/observability (e.g. logging which required_action fired) -
    channels are free to ignore it and only look at `response_text` /
    `state`."""

    response_text: Optional[str]
    state: str
    required_action: Optional[str]
    engine_result: EngineResult


class ConversationService:
    """The Application layer's one use case: "handle one customer message,
    on any channel, and reply." Also owns starting a new conversation and
    reading its history, so channels never touch the repositories directly.

    `provider` is optional: without one, the Extractor is skipped (every
    message becomes a plain `CUSTOMER_MESSAGE` event) and the Responder
    always uses its fixed fallback text - a degraded but never-crashing
    mode, useful for tests or a deployment with no LLM configured yet.
    """

    def __init__(self, db_session, provider: Optional[LLMProvider] = None, rag: Optional[Rag] = None):
        self.db = db_session
        self.engine = ConversationEngine(db_session, provider=provider)
        self.memory = ConversationMemory(db_session)
        self.conversation_repo = ConversationRepository(db_session)
        self.lead_repo = LeadRepository(db_session)
        self.extractor = Extractor(provider) if provider is not None else None
        self.responder = Responder(provider)
        self.rag = rag if rag is not None else Rag()

    def start_conversation(
        self,
        channel: ConversationChannel,
        *,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        language: str = "fr",
        external_id: Optional[str] = None,
    ) -> tuple[Lead, Conversation]:
        source = _LEAD_SOURCE_BY_CHANNEL.get(channel, LeadSource.WEBSITE)
        lead = self.lead_repo.create(
            source=source, first_name=first_name, last_name=last_name, email=email, phone=phone
        )
        conversation = self.conversation_repo.create(
            lead_id=lead.id, channel=channel, language=language, external_id=external_id
        )
        return lead, conversation

    def get_conversation_by_external_id(
        self, channel: ConversationChannel, external_id: str
    ) -> Optional[Conversation]:
        return self.conversation_repo.get_by_external_id(channel, external_id)

    def get_conversation(self, conversation_id: UUID) -> Optional[Conversation]:
        return self.conversation_repo.get_by_id(conversation_id)

    def get_history(self, conversation_id: UUID, limit: int = 50) -> list[Message]:
        conversation = self.conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            return []
        return self.conversation_repo.get_history(conversation, limit=limit)

    def start_and_greet(
        self,
        channel: ConversationChannel,
        *,
        existing_lead_id: Optional[UUID] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        language: str = "fr",
        external_id: Optional[str] = None,
    ) -> tuple[Lead, Conversation, ConversationResponse]:
        """Outbound entry point (Phase 5): Sophie initiates, there is no
        customer message yet. Drives the conversation through
        START -> GREETING via a `CONVERSATION_STARTED` event (the state
        machine's START branch doesn't inspect event content - any event
        moves it to GREETING - see conversation_engine/state_machine.py) and
        generates the opening message through the same Responder used for
        every other turn. Unlike `handle_message`, no USER message is
        logged - the customer hasn't said anything.

        Pass `existing_lead_id` when the caller already has a Lead (the
        normal outbound case: `outbound/sender.py` already selected this
        lead via `CampaignEngine`) - this only creates a new Conversation for
        it, not a second Lead. Without it, behaves like `start_conversation`
        and creates a new Lead too (e.g. a hypothetical outbound channel that
        only has a phone number/chat_id and no CRM record yet).
        """
        if existing_lead_id is not None:
            lead = self.lead_repo.get_by_id(existing_lead_id)
            if lead is None:
                raise ValueError(f"No lead found for existing_lead_id={existing_lead_id}")
            conversation = self.conversation_repo.create(
                lead_id=lead.id, channel=channel, language=language, external_id=external_id
            )
        else:
            lead, conversation = self.start_conversation(
                channel,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                language=language,
                external_id=external_id,
            )

        result = self.engine.process_turn(conversation.id, Event(type=EventType.CONVERSATION_STARTED))

        conversation = self.conversation_repo.get_by_id(conversation.id)
        response_text = self._generate_response(result, conversation, raw_text="")

        if response_text:
            self.conversation_repo.add_message(conversation, MessageRole.ASSISTANT, response_text)

        response = ConversationResponse(
            response_text=response_text,
            state=conversation.current_state.value,
            required_action=result.required_action,
            engine_result=result,
        )
        return lead, conversation, response

    def send_follow_up(self, conversation_id: UUID) -> ConversationResponse:
        """Phase 6 entry point: sends a scheduler-triggered follow-up on a
        conversation already in WAITING_CUSTOMER (see followup/engine.py,
        which decides *whether* a follow-up is due - this method only
        drives the one it already decided to send through the normal
        engine/responder pipeline). Like `start_and_greet`, no USER message
        is logged - the customer hasn't said anything.
        """
        result = self.engine.process_turn(conversation_id, Event(type=EventType.FOLLOW_UP_DUE))

        conversation = self.conversation_repo.get_by_id(conversation_id)
        response_text = self._generate_response(result, conversation, raw_text="")

        if response_text:
            self.conversation_repo.add_message(conversation, MessageRole.ASSISTANT, response_text)

        return ConversationResponse(
            response_text=response_text,
            state=conversation.current_state.value,
            required_action=result.required_action,
            engine_result=result,
        )

    def handle_message(self, request: ConversationRequest) -> ConversationResponse:
        context = self.memory.load(request.conversation_id)

        event = self._extract_event(request.text, context.last_question_action)
        self.conversation_repo.add_message(context.conversation, MessageRole.USER, request.text)

        result = self.engine.process_turn(request.conversation_id, event)

        conversation = self.conversation_repo.get_by_id(request.conversation_id)
        response_text = self._generate_response(result, conversation, request.text)

        if response_text:
            self.conversation_repo.add_message(conversation, MessageRole.ASSISTANT, response_text)

        # F-011 fix (extended - regression covered by
        # test_reaching_qualified_also_notifies_sales_team_in_the_same_turn):
        # several states are decided purely by rules.py from data already on
        # the Lead, with no new customer input required to advance past them
        # - DATA_VALIDATION (decide_validation() re-checks the fields that
        # were *just* completed this same turn, e.g. the EAN submitted right
        # now) and QUALIFIED (always advances straight to HANDOFF,
        # NOTIFY_SALES_TEAM). Without chaining, a customer whose last
        # message completed qualification (e.g. submitted a valid EAN) would
        # land on DATA_VALIDATION and see nothing but the "let me check that"
        # turn, since nothing guarantees they send one more message
        # afterwards - the confirmation and handoff would only fire on some
        # future, possibly never-sent, message. Chain every such turn
        # automatically, server-side, within this same request/response
        # cycle, using a dedicated system-triggered event (never produced by
        # the Extractor) so each transition and its audit trail stays
        # explicit about happening without new customer input. The loop
        # stops as soon as a turn lands anywhere else - most commonly
        # HANDOFF, but also a collection state if decide_validation() sent
        # an invalid field back for correction (CORRECT_FIELD), which *does*
        # require a new customer reply and must not be chained through.
        _AUTO_ADVANCE_STATES = (ConversationState.DATA_VALIDATION, ConversationState.QUALIFIED)
        _MAX_CHAINED_TURNS = 5  # generous bound; a real chain is at most 2 steps today
        chained_turns = 0
        while result.next_state in _AUTO_ADVANCE_STATES and chained_turns < _MAX_CHAINED_TURNS:
            chained_turns += 1
            chained_result = self.engine.process_turn(
                request.conversation_id, Event(type=EventType.QUALIFICATION_ADVANCE)
            )
            conversation = self.conversation_repo.get_by_id(request.conversation_id)
            chained_text = self._generate_response(chained_result, conversation, raw_text="")

            if chained_text:
                self.conversation_repo.add_message(conversation, MessageRole.ASSISTANT, chained_text)
                response_text = f"{response_text}\n\n{chained_text}" if response_text else chained_text

            result = chained_result

        return ConversationResponse(
            response_text=response_text,
            state=conversation.current_state.value,
            required_action=result.required_action,
            engine_result=result,
        )

    def _extract_event(self, raw_text: str, last_question_action: Optional[str]) -> Event:
        if self.extractor is None:
            return Event(type=EventType.CUSTOMER_MESSAGE, raw_answer_text=raw_text)

        expected_field = _REQUIRED_ACTION_TO_EXPECTED_FIELD.get(last_question_action or "")
        return self.extractor.extract(raw_text, expected_field=expected_field)

    def _generate_response(self, result: EngineResult, conversation: Conversation, raw_text: str) -> Optional[str]:
        rag_answer = None
        rag_category = _RAG_CATEGORY_BY_ACTION.get(result.required_action or "")
        if rag_category:
            rag_answer = self.rag.answer(raw_text, category=rag_category)

        return self.responder.respond(
            result.required_action,
            conversation=conversation,
            rejection_reason=result.rejection_reason,
            rag_answer=rag_answer,
        )
