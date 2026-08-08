# Phase 2 — Architecture Review Deliverables

Requested before starting Phase 3. Reflects the code as of the Phase 2
follow-up refactor (Action model, Intent Classifier, Dialogue Policy).

## 1. Complete transition table

`event` columns marked "—" mean that event isn't specifically handled in
that state (it falls through to the state's default branch, shown in the
Default row). Global overrides (`REQUEST_HUMAN`, `EXTRACTION_FAILED`,
`QUESTION`, `OBJECTION`) apply from every state below unless the state's own
row overrides them (only FAQ/OBJECTION do, since that's what they exist to
handle).

| Current state | Event | Next state | Notes |
|---|---|---|---|
| *(any state)* | REQUEST_HUMAN | HANDOFF | global override |
| *(any state)* | EXTRACTION_FAILED | *(unchanged)* | global override, ASK_CLARIFICATION, never a state change |
| *(any state, except FAQ/OBJECTION themselves)* | QUESTION | FAQ | remembers previous state |
| *(any state, except FAQ/OBJECTION themselves)* | OBJECTION | OBJECTION | remembers previous state |
| START | any | GREETING | SEND_GREETING |
| GREETING | any | DISCOVERY | ASK_INTENT |
| DISCOVERY | PROVIDE_INFORMATION / CUSTOMER_MESSAGE | INTENT_CONFIRMATION | CONFIRM_INTENT |
| DISCOVERY | *(default)* | DISCOVERY | ASK_INTENT |
| INTENT_CONFIRMATION | CHANGE_INTENT_YES | → rules.next_qualification_action() | usually COLLECT_CUSTOMER_TYPE on a fresh lead |
| INTENT_CONFIRMATION | CHANGE_INTENT_NO | REJECTED | reason=NO_CHANGE_INTENT |
| INTENT_CONFIRMATION | *(default)* | *(unchanged)* | ASK_CLARIFICATION |
| COLLECT_CUSTOMER_TYPE / COLLECT_LOCATION / COLLECT_SUPPLIER / COLLECT_CONTACT / COLLECT_EAN | any | → rules.next_qualification_action() | next missing field, or DATA_VALIDATION if none missing |
| DATA_VALIDATION | any | → rules.decide_validation() | QUALIFIED, REJECTED(OUT_OF_COVERAGE), or back to COLLECT_EAN/COLLECT_CONTACT on correction |
| QUALIFIED | any | HANDOFF | NOTIFY_SALES_TEAM |
| HANDOFF | any | CLOSED | — |
| FAQ / OBJECTION | any | → dialogue_policy.decide_after_detour() | RESUME (back to remembered state) or HANDOFF if consecutive_detour_count >= 3 |
| WAITING_CUSTOMER | FOLLOW_UP_DUE | WAITING_CUSTOMER | SEND_FOLLOW_UP |
| WAITING_CUSTOMER | *(any real reply)* | → rules.next_qualification_action() | resumes qualification where it stopped |
| CLOSED | any | CLOSED | terminal |

## 2. YAML business rules (as currently loaded)

`business_rules/qualification_rules.yaml`:
```yaml
required_fields_order:
  - customer_type
  - location
  - current_supplier
  - contact
  - ean
coverage:
  allowed_regions:
    - Wallonie
    - Flandre
    - Bruxelles
```

`business_rules/validation_rules.yaml`:
```yaml
ean: { length: 18, numeric_only: true }
email: { must_contain: "@" }
phone: { country: BE, pattern: "^0[0-9]{8,9}$" }
```

`business_rules/dialogue_policy.yaml` (new, added in this review round):
```yaml
max_consecutive_detours: 3
```

All three files are pure data - no conditionals, no expressions. Confirmed
by `tests/test_rules.py::test_rules_module_never_touches_the_database`
(AST-based check) that `rules.py` never imports a repository or calls
`.flush()/.commit()/.add()/.save()`; `dialogue_policy.py` follows the same
purity discipline.

## 3. State machine diagram

```
START ──▶ GREETING ──▶ DISCOVERY ──▶ INTENT_CONFIRMATION
                                          │yes            │no
                                          ▼               ▼
                              COLLECT_CUSTOMER_TYPE     REJECTED
                                          │                (NO_CHANGE_INTENT)
                                          ▼
                                COLLECT_LOCATION
                                          ▼
                                COLLECT_SUPPLIER
                                          ▼
                                 COLLECT_CONTACT
                                          ▼
                                   COLLECT_EAN
                                          ▼
                                 DATA_VALIDATION ──▶ REJECTED (OUT_OF_COVERAGE)
                                    │           │
                              valid │           │ invalid contact/EAN
                                    ▼           ▼
                                QUALIFIED   COLLECT_CONTACT / COLLECT_EAN
                                    │
                                    ▼
                                 HANDOFF ──▶ CLOSED

Detours (from any COLLECT_*/DISCOVERY/DATA_VALIDATION state):
   QUESTION  ──▶ FAQ ───────┐
   OBJECTION ──▶ OBJECTION ─┤──▶ dialogue_policy ──▶ RESUME (back to remembered state)
                             └────────────────────▶ HANDOFF (if >=3 consecutive detours)

REQUEST_HUMAN (from anywhere) ──▶ HANDOFF
EXTRACTION_FAILED (from anywhere) ──▶ (state unchanged), ASK_CLARIFICATION
```

## 4. Engine sequence diagram (one `process_turn` call)

```
Caller                Engine              Memory        IntentClassifier   Rules/DialoguePolicy   StateMachine   Repositories        ActivityRepo
  │  process_turn(conv_id, event)
  │────────────────────▶│
  │                     │  load(conv_id)
  │                     │───────────────▶│
  │                     │◀───────────────│ (lead, conversation, missing_fields)
  │                     │ merge event.entities onto lead (data assignment only)
  │                     │
  │                     │  decide(state, event, lead, conversation)
  │                     │───────────────────────────────────────────▶│
  │                     │                     classify(event)         │
  │                     │                 ◀───────────────────────────│
  │                     │                                              │ next_qualification_action(lead)
  │                     │                                              │ / decide_validation(lead)
  │                     │                                              │ / decide_after_detour(conversation)
  │                     │◀─────────────────────────────────────────────│ StateDecision
  │                     │
  │                     │  transition_state(...) or resume_previous_state(...)
  │                     │─────────────────────────────────────────────────────▶│
  │                     │  increment/reset_detour_count(...)
  │                     │─────────────────────────────────────────────────────▶│
  │                     │  set_status(lead, ...)              (if LeadStatus changed)
  │                     │─────────────────────────────────────────────────────▶│
  │                     │  log(lead_id, STATE_CHANGED / QUALIFIED / REJECTED / HUMAN_HANDOFF)
  │                     │──────────────────────────────────────────────────────────────────────▶│
  │                     │  save_last_question(conv_id, required_action)
  │                     │───────────────▶│ (Redis cache, best-effort)
  │◀────────────────────│ EngineResult(previous_state, next_state, required_action, rejection_reason)
```

Note: no LLM appears anywhere in this diagram - `event` arrives already
classified (by tests today, by the Phase 3 Extractor tomorrow), and the
result is a structured `EngineResult`, not a sentence. Phase 3's Responder
will consume `EngineResult` to generate the actual message.

## 5. Action model

```python
class ActionType(str, Enum):
    ASK_FIELD = "ASK_FIELD"
    VALIDATE = "VALIDATE"
    CORRECT_FIELD = "CORRECT_FIELD"
    QUALIFY = "QUALIFY"
    REJECT = "REJECT"
    HANDOFF = "HANDOFF"
    CLOSE = "CLOSE"
    ANSWER_FAQ = "ANSWER_FAQ"
    ANSWER_OBJECTION = "ANSWER_OBJECTION"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    CONFIRM_INTENT = "CONFIRM_INTENT"
    ASK_INTENT = "ASK_INTENT"
    SEND_GREETING = "SEND_GREETING"
    RESUME = "RESUME"
    SEND_FOLLOW_UP = "SEND_FOLLOW_UP"
    NONE = "NONE"

@dataclass
class Action:
    type: ActionType
    field: Optional[str] = None      # which field group (ASK_FIELD/CORRECT_FIELD)
    reason: Optional[RejectionReason] = None   # for REJECT
```

`rules.py` and `dialogue_policy.py` are the only modules that construct an
`Action`. `state_machine.py` is the only module that translates an `Action`
into a `ConversationState` (via `_resolve_qualification_action()` and the
FAQ/OBJECTION branch). This is what makes the Action channel-agnostic:
a Telegram/WhatsApp/Voice channel implementation later would consume the
same `Action` (through `EngineResult.required_action` today, or the `Action`
object directly if we later expose it) without any of `rules.py` or
`dialogue_policy.py` needing to know a `ConversationState` exists.

## Answers to the 6 review points

1. **YAML stays declarative** - confirmed, see section 2 above.
2. **Rules return an Action, not a State** - done (`rules.next_qualification_action`,
   `rules.decide_validation`); `state_machine.py` is now the sole Action→State translator.
3. **Intent Classifier layer added** - `conversation_engine/intent_classifier.py`,
   called first inside `state_machine.decide()`. Today it normalizes/validates a
   pre-classified `Event`; Phase 3C replaces its internals with real NLP-backed
   classification behind the same contract.
4. **Dialogue Policy added** - `conversation_engine/dialogue_policy.py` now owns
   the "resume vs escalate" decision after a FAQ/OBJECTION detour, backed by a
   new `Conversation.consecutive_detour_count` field and
   `business_rules/dialogue_policy.yaml`.
5. **Rules never touch the CRM** - confirmed (and now enforced by an AST-based
   test, `test_rules_module_never_touches_the_database`, not just a comment).
6. **Transition table** - section 1 above.
