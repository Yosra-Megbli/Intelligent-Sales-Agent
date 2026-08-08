# Voice C — VoiceSessionManager Responsibilities

**Scope note (Tier A only, per the adopted MVP architecture):** no
WebSockets, no Media Streams, no real-time barge-in detection. Every turn
is a discrete HTTP request/response (`<Gather>` → webhook → `<Say>` +
`<Gather>` again). This document supersedes the full architecture spec's
§8 (Interruption Policy) for this implementation: **true barge-in is not
implementable on Tier A and is explicitly out of scope for Voice C.** If/when
Tier B (streaming) is built, interruption handling belongs there, not here.

## What VoiceSessionManager IS responsible for

1. **Turn-taking bookkeeping** — tracking, per call, across HTTP turns:
   what Sophie last asked (`last_required_action`), how many consecutive
   silences/low-confidence turns have happened, and whether a
   confirmation read-back is currently pending. This state is **not**
   PostgreSQL-persisted and **not** owned by `ConversationService` — it is
   passed in and returned by every call, so whatever wires this to a real
   Voice Provider (Voice E, not built yet) decides how to carry it between
   HTTP turns (e.g. a signed query string on the `<Gather>` action URL).
2. **Silence Policy** — no speech (or a blank transcript) → reprompt, up to
   a configured maximum attempts, then end the call gracefully.
3. **Low-confidence recovery** — a `TranscriptionResult` below a configured
   confidence threshold is treated the same as silence: reprompt, never
   silently forwarded to `ConversationService`.
4. **Confirmation Policy** — for a configured set of `required_action`
   values (starting with `ASK_EAN`/`ASK_EAN_CORRECTION` only, per this
   iteration's scope), reads the transcribed value back and requires an
   explicit yes/no before ever calling `ConversationService.handle_message()`
   with it. Detects yes/no via a small, fixed, voice-local word list — not
   the Business Engine's intent classifier.
5. **Deciding when to hang up** — after `ConversationResponse.state` lands
   in a terminal state (`CLOSED`/`HANDOFF`/`REJECTED`), after silence gives
   up, or after confirmation retries are exhausted.
6. **Composing what to say each turn** — either a Sophie-generated
   `response_text` (passed through unchanged), or one of a small, fixed set
   of voice-mechanics prompts (reprompt, confirmation read-back, goodbye) —
   never inventing new business-facing wording of its own.

## What VoiceSessionManager must NEVER do

- **Never call `conversation_engine/*` or `ai/*` directly.** Its only
  integration point is `ConversationService` — exactly like every other
  channel. Enforced by an architecture-boundary test, same as
  `channels/web.py`/`telegram.py`/`whatsapp.py`.
- **Never decide a business outcome.** It doesn't validate an EAN, doesn't
  decide qualification, doesn't reject a lead, doesn't decide coverage —
  all of that is `rules.py`'s job, reached only via `handle_message()`.
  Confirming a *transcript* is correct is not the same as validating that
  the *business data* is correct — the Engine still runs its own
  validation afterward, unchanged.
- **Never persist anything itself.** No repository calls, no
  `db.flush()`/`.commit()` — every persisted side effect (messages, Lead/
  Conversation state) happens inside `ConversationService`, which Voice C
  calls exactly once per real customer answer.
- **Never invent what Sophie says.** Every business-facing sentence
  (greetings, questions, rejections, FAQ answers) comes from
  `ConversationResponse.response_text`, produced by `ai/responder.py`.
  VoiceSessionManager only adds the small, fixed set of voice-mechanics
  prompts listed above (reprompt/confirmation/goodbye), which are
  channel-communication text, not business content.
- **Never attempt real-time interruption handling in this iteration** — see
  the scope note above.

## Architectural gap check (before implementation)

Reviewed against the existing codebase and the full architecture
specification:

- `ConversationService.start_and_greet()`, `.handle_message()`,
  `.get_conversation()`, `.get_conversation_by_external_id()` already
  provide every entry point Voice C needs — **no new method required on
  ConversationService.**
- `ConversationResponse.required_action` is already public and sufficient
  to know what Sophie just asked, without VoiceSessionManager needing to
  read `ConversationMemory`/`conversation_engine` directly — confirms the
  "only talk to ConversationService" rule is achievable with zero new
  surface area.
- No PostgreSQL schema change is needed for Voice C itself — turn-taking
  state stays outside PostgreSQL by design (see point 1 above).
- One small, deliberate scope decision: the confirmation policy in this
  iteration covers `ASK_EAN`/`ASK_EAN_CORRECTION` only, not `ASK_CONTACT`
  (name+email+phone are collected as one bundled question in the text
  channels; splitting that into individually-confirmed voice sub-turns is
  a real UX design question left for a future iteration, not a gap in this
  one — `fields_requiring_confirmation` is a policy value, easily extended
  later without changing `VoiceSessionManager`'s logic).

**No blocking architectural gaps found. Proceeding to implementation.**
