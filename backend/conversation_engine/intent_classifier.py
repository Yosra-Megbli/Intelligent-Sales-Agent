"""
Intent Classifier.

Architecture review requirement: there must be an explicit layer between
"what came in" and the State Machine, and it must not live inside the LLM.

Phase 2 contract (kept unchanged): the caller passes in an `Event` already
resolved by upstream (Phase 3B: ai/extractor.py, one LLM call per message,
no conversation context). This classifier *normalizes/validates* it into
one of the fixed intents the State Machine understands - an unrecognized/
malformed event always becomes EXTRACTION_FAILED. It never touches
Conversation.current_state or the CRM itself; state_machine.py is still the
only place an Event turns into a state transition.

Phase 3C addition: the Extractor is deliberately single-message and
context-light (docs: ai/README.md). When it can't confidently classify a
message it falls back to EventType.CUSTOMER_MESSAGE. That's exactly the
case this layer exists for - it's the one place with access to
conversation-level context (which step Sophie is on right now), so it's the
right place to take a second, state-aware look, not the Extractor. This is
an *optional* second LLM call, only for that fallback case, so a normal
turn's cost stays a single extraction: `IntentClassifier()` with no
provider (or any confidently-classified event) behaves exactly like Phase 2.
On any failure - no provider configured, malformed JSON, LLM error - it
falls back to the Extractor's original classification. It never returns
something worse than what came in.
"""

from __future__ import annotations

import json
from typing import Optional

from ai.providers.interface import LLMError, LLMMessage, LLMProvider, LLMRole
from conversation_engine.transitions import Event, EventType
from domain.enums import ConversationState

_KNOWN_EVENT_TYPES = set(EventType)

# The vocabulary a second-pass disambiguation call is allowed to pick from -
# identical to the Extractor's (ai/extractor.py), since this is still
# "what kind of message was this", just with more context, not a new kind
# of decision.
_CANDIDATE_EVENT_TYPES = [
    EventType.PROVIDE_INFORMATION,
    EventType.QUESTION,
    EventType.OBJECTION,
    EventType.CHANGE_INTENT_YES,
    EventType.CHANGE_INTENT_NO,
    EventType.REQUEST_HUMAN,
    EventType.CUSTOMER_MESSAGE,
]
_CANDIDATE_EVENT_TYPE_VALUES = {e.value for e in _CANDIDATE_EVENT_TYPES}

_SYSTEM_PROMPT = """You are a conversation-intent disambiguator. A first \
pass already read this customer message and could not confidently classify \
it, so it was tagged as a generic message. You are given the dialogue step \
Sophie was on when the customer replied - use ONLY that to resolve short or \
ambiguous replies (e.g. a bare "oui"/"non" right after a yes/no question). \
Output ONLY a JSON object, no other text:

{"event_type": one of PROVIDE_INFORMATION, QUESTION, OBJECTION, \
CHANGE_INTENT_YES, CHANGE_INTENT_NO, REQUEST_HUMAN, CUSTOMER_MESSAGE}

If you are still not confident given the context, output CUSTOMER_MESSAGE -\
 do not guess."""


class IntentClassifier:
    """Normalizes an incoming Event before it reaches the State Machine.

    `provider` is optional: without one (or for any event the Extractor
    already classified confidently), this behaves exactly like the Phase 2
    passthrough. With one, a CUSTOMER_MESSAGE fallback gets one extra,
    context-aware attempt at classification.
    """

    def __init__(self, provider: Optional[LLMProvider] = None):
        self._provider = provider

    def classify(self, event: Event, *, current_state: Optional[ConversationState] = None) -> Event:
        if event.type not in _KNOWN_EVENT_TYPES:
            return Event(type=EventType.EXTRACTION_FAILED)

        if event.type == EventType.CUSTOMER_MESSAGE and self._provider is not None and event.raw_answer_text:
            return self._disambiguate(event, current_state)

        return event

    def _disambiguate(self, event: Event, current_state: Optional[ConversationState]) -> Event:
        state_label = current_state.value if isinstance(current_state, ConversationState) else current_state
        context = f"\n\nContext: Sophie's dialogue step was {state_label}." if state_label else ""
        messages = [
            LLMMessage(role=LLMRole.SYSTEM, content=_SYSTEM_PROMPT + context),
            LLMMessage(role=LLMRole.USER, content=event.raw_answer_text),
        ]

        try:
            response = self._provider.generate(messages, temperature=0.0, json_mode=True)
        except LLMError:
            return event

        try:
            parsed = json.loads(response.content)
        except (TypeError, ValueError):
            return event
        if not isinstance(parsed, dict):
            return event

        new_type = parsed.get("event_type")
        if new_type not in _CANDIDATE_EVENT_TYPE_VALUES:
            return event

        return Event(type=EventType(new_type), entities=event.entities, raw_answer_text=event.raw_answer_text)
