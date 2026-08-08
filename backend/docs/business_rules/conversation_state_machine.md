# Sophie — Conversation State Machine (reference for `conversation_engine/`)

This is the authoritative design. Code in `conversation_engine/` must match
this document; if they ever disagree, this document wins and the code is the
bug.

## Two separate state spaces

- **LeadStatus** (`domain/enums.py`) — the CRM lifecycle / business journey.
  Lives on `Lead.status`.
- **ConversationState** (`domain/enums.py`) — what Sophie does on the next
  turn. Lives on `Conversation.current_state`.

They are related (e.g. reaching `QUALIFIED` conversation state causes
`LeadStatus.QUALIFIED`) but are never the same field and never confused.

## Main flow

```
START
  |
GREETING
  |
DISCOVERY
  |
INTENT_CONFIRMATION
  |
COLLECT_CUSTOMER_TYPE
  |
COLLECT_LOCATION
  |
COLLECT_SUPPLIER
  |
COLLECT_CONTACT
  |
COLLECT_EAN
  |
DATA_VALIDATION
  |
QUALIFIED
  |
HANDOFF
  |
CLOSED
```

Qualification field order is fixed and never decided by the LLM:
`customer_type -> location -> current_supplier -> contact (name/email/phone) -> EAN`.
EAN is asked last because it is sensitive information, requested only after
trust has been established.

## Detours (always return to where they interrupted)

- **FAQ** — customer asks an off-topic question. Answered (RAG, Phase 3),
  then `resume_previous_state()` returns to the exact state that was active.
- **OBJECTION** — customer raises a sales objection (price, loyalty to
  current supplier, "I'll think about it"). Same return-to-previous pattern.
- **ERROR_RECOVERY** — API error, unparseable message, or empty LLM
  extraction. Does **not** change `current_state` at all; the engine simply
  asks for clarification and stays exactly where it was.

## Terminal / rejection

- **INTENT_CONFIRMATION** without confirmation → `REJECTED`,
  reason `NO_CHANGE_INTENT`.
- **DATA_VALIDATION** region not covered → `REJECTED`, reason
  `OUT_OF_COVERAGE`.
- Customer explicitly asks for a human at any point → `HANDOFF` directly
  (bypasses the rest of qualification).
- `REQUEST_HUMAN_ONLY`, `NO_INTENT`, `INVALID_CUSTOMER`, `DUPLICATE_LEAD` are
  the remaining rejection reasons (duplicate detection happens at lead
  intake time, before/at conversation START — see `crm/lead_repository.py:
  find_duplicate`).

## DATA_VALIDATION rules

- EAN: must be exactly 18 numeric characters. **Invalid EAN is not a
  rejection** — it routes back to `COLLECT_EAN` asking for a correction.
- Email: must contain `@`.
- Phone: must match a Belgian format (e.g. `0488xxxxxx`).
- Region: must be one of `Wallonie`, `Flandre`, `Bruxelles` — otherwise
  `REJECTED` / `OUT_OF_COVERAGE` (this one *is* a rejection, since the
  service genuinely cannot be delivered).

## Golden rules for this layer (from the Master Prompt)

1. Business rules live in `conversation_engine/rules.py` and
   `business_rules/*.yaml` — never inside an LLM prompt.
2. The LLM never sets `Lead.status`, `Lead.qualification_score`, or
   `Conversation.current_state` directly. It only produces the *extracted
   entities* that this engine consumes as input, and later (Phase 3) turns
   this engine's *decision* into natural language.
3. Every state transition must be covered by a test (see
   `tests/test_state_machine.py`, `tests/test_conversation_engine.py`).
