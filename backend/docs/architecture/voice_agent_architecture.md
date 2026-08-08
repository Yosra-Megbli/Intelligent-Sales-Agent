# Phase 4E — Voice Agent Architecture (Design Only)

Status: DESIGN SPECIFICATION. No production code exists yet. This document
is the official specification the Voice channel will be implemented against
(Voice A–E, see §20), the same discipline used for
`docs/architecture/phase2_review.md` before `conversation_engine/` was
written.

**Implementation status:** Voice A (`channels/voice/providers/interface.py`'s
`SpeechToTextProvider` + `channels/voice/providers/twilio_stt.py`'s Tier A
implementation) and Voice B (the same `interface.py`'s
`TextToSpeechProvider` + `channels/voice/providers/twilio_tts.py`'s Tier A
implementation) are done, tested (33 tests), and match this specification's
sections 4/5/13 exactly. **Voice C (`channels/voice/session_manager.py`'s
`VoiceSessionManager`) is also done** - Tier A turn-taking, Silence Policy
(§7), low-confidence recovery (§10), and a scoped Confirmation Policy (§9,
EAN only for this iteration) - see `docs/architecture/
voice_c_responsibilities.md` for its exact scope and the explicit,
documented decision to defer real-time Interruption Policy (§8) entirely to
a future Tier B/streaming build, since Tier A cannot detect barge-in at all.
38 new tests (unit tests against a fake `ConversationService`, plus a few
real end-to-end integration tests including a full EAN confirm-then-forward
round trip). 377 tests total, all passing, zero regressions. Voice D
(streaming) and the inbound-facing half of Voice E (a `VoiceChannel`
adapter parsing Twilio's `<Gather>` webhook shape and driving turns through
`VoiceSessionManager`) remain design-only below.

**Voice E, outbound dial-out half - architecture complete, not connected to
a real Twilio account:** `channels/voice/providers/telephony_interface.py`'s
`TelephonyProvider` (mirrors §4/§5's STT/TTS abstraction shape - one
abstract `initiate_call()` method, a dedicated exception hierarchy),
`channels/voice/providers/twilio_telephony.py`'s `TwilioTelephonyProvider`
(a real Twilio `Calls` REST API request builder, same "not exercised by any
test in this sandbox, wire this in only in a real deployment" posture as
`TelegramBotAPISender`/`TwilioWhatsAppSender`), `outbound/voice_sender.py`'s
`OutboundVoiceSender` (places the call + records the same CRM bookkeeping
`outbound/sender.py` does for text channels), and
`POST /api/voice/outbound-calls` (via `application/
voice_outbound_service.py`'s `VoiceOutboundService`, guarded by
`require_api_key`, returns 503 when Twilio Voice credentials aren't
configured). `POST /api/voice/twiml` exists only as a fixed-response stub
(a graceful `<Say>` + `<Hangup/>`), guarded by the same
`verify_twilio_signature` + `enforce_rate_limit` pair the WhatsApp webhook
uses, so a real Twilio call has somewhere valid (and authenticated) to
land - it does not yet run `VoiceSessionManager`. Scoped this way
deliberately: dialing a phone is architecturally a new, self-contained
capability (unlike Telegram/WhatsApp outbound, which just reuses an
already-existing inbound transport), so it ships as its own complete
abstraction + route without also building the remaining inbound-facing
Voice E piece described below in the same pass.

## 0. Non-negotiable constraint

Every other channel (`channels/web.py`, `channels/telegram.py`,
`channels/whatsapp.py`) is a thin adapter over `ConversationService`. None
of them contain business logic, qualification rules, or dialogue-state
decisions - all of that lives in `conversation_engine/` and is reused
verbatim by every channel. Voice **must** follow the exact same rule:

```
Web      ──┐
Telegram ──┤
WhatsApp ──┼──▶ ConversationService ──▶ ConversationEngine ──▶ Business Rules
Voice    ──┘
```

If at any point a Voice-specific decision starts influencing qualification
order, validation, or `ConversationState` transitions, that is an
architecture violation - it belongs in `conversation_engine/rules.py` or
`state_machine.py`, reachable and testable the same way for every channel,
not hidden inside a Voice-only code path.

---

## 1. Voice System Architecture

```
                    ┌─────────────────────┐
                    │   Phone Network      │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Voice Provider       │   (Twilio Voice, or another -
                    │  (telephony + media)  │    see §13, abstracted)
                    └──────────┬───────────┘
                               │  bidirectional audio stream
                    ┌──────────▼───────────┐
                    │  VoiceSessionManager  │   Voice C - owns ONE call's
                    │                        │   technical state (§2, §3)
                    └───┬───────────────┬────┘
                        │               │
              ┌─────────▼───┐   ┌───────▼─────────┐
              │  STT         │   │  TTS             │   Voice A / Voice B
              │  provider    │   │  provider        │   (§4, §5)
              └─────────┬───┘   └───────▲─────────┘
                        │ final          │ text to speak
                        │ transcript     │
                        ▼               │
              ┌─────────────────────────┴────┐
              │   ConversationService          │  ◀── UNCHANGED, same class
              │   (application/                │      every other channel
              │    conversation_service.py)    │      already uses
              └─────────────┬───────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  ConversationEngine           │  ◀── UNCHANGED
              │  (state_machine, rules,       │
              │   dialogue_policy, memory)     │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  ai/responder.py               │  ◀── UNCHANGED (talking
              │  (Response Generator)          │      points, prompts/)
              └─────────────────────────────┘
```

Everything from `ConversationService` down is **already built and already
shared** by Web/Telegram/WhatsApp. The only new code this phase adds sits
above that line: `VoiceSessionManager`, the STT/TTS provider abstractions,
and the Voice Provider adapter.

---

## 2. Voice Session Lifecycle

This is the **call's technical lifecycle** - not to be confused with
`ConversationState` (§3 explains why they're different).

```
CALL_STARTED
     │
     ▼
GREETING_PLAYING          (TTS speaking Sophie's opening line)
     │
     ▼
LISTENING ◀──────────────────────────────┐
     │                                     │
     ▼                                     │
PROCESSING (STT finalized, event          │
            being sent to                 │
            ConversationService)          │
     │                                     │
     ▼                                     │
RESPONSE_PLAYING (TTS speaking            │
                   Sophie's reply) ────────┘
     │
     │  (ConversationState reached QUALIFIED/REJECTED/HANDOFF/CLOSED)
     ▼
CALL_ENDING  (closing remark played)
     │
     ▼
CALL_ENDED
```

Side branches from `LISTENING`:
- silence timeout → §7
- customer interrupts during `RESPONSE_PLAYING` → §8 (jumps straight back
  to `LISTENING`)
- STT confidence too low / unintelligible → §10

## 3. Voice State Machine — and why it is NOT a new business state machine

**Decision: there is no second `ConversationState` for Voice.** The
existing state machine (`conversation_engine/state_machine.py`) is reused
unchanged - a qualified lead is qualified the same way whether they typed
or spoke.

What Voice *does* need is a second, orthogonal state machine for
**call mechanics** - is audio currently playing, is the mic open, how many
silences have we seen this turn. That is exactly §2's lifecycle. Two
independent state variables, same separation of concerns already
established for `LeadStatus` vs `ConversationState` in Phase 2:

| | Answers | Owned by |
|---|---|---|
| `ConversationState` | What is Sophie doing in the *sales conversation*? | `conversation_engine/` (unchanged) |
| Voice session state (§2) | What is happening on the *phone line right now*? | `VoiceSessionManager` (new) |

A call can be `LISTENING` (voice session state) while `ConversationState`
is `COLLECT_EAN` (business state) - two different questions, two different
owners, exactly like a Web conversation's `ConversationState` never needed
to know about HTTP request/response cycles.

---

## 4. Speech-to-Text (STT) abstraction

New interface, same shape as `ai/providers/interface.py`'s `LLMProvider`:

```
SpeechToTextProvider
├── start_stream(call_id) -> stream handle
├── feed_audio_chunk(stream_handle, audio_bytes) -> None
├── on_partial_transcript(callback)   # optional, for live captions/logs only
└── on_final_transcript(callback)     # THIS is what reaches VoiceSessionManager
```

Only a **final** transcript (the provider's own end-of-utterance /
endpointing decision, typically backed by silence detection - see §7)
produces an `Event` for `ConversationService`. Partial transcripts exist
for latency/UX polish later (e.g. showing "..." while the customer is
still talking) but never drive a business decision - mirrors the existing
rule that the Extractor only ever produces one `Event` per customer
message, never a stream of half-formed ones.

Candidate providers (concrete implementations, decided in Voice A):
Twilio's built-in speech recognition (simplest, same vendor as WhatsApp -
see §20 for why this is the recommended MVP path), or a dedicated
streaming STT vendor (Deepgram, Google STT) via Twilio Media Streams if
Twilio's built-in recognition proves too basic for French/Dutch accuracy.

## 5. Text-to-Speech (TTS) abstraction

```
TextToSpeechProvider
├── synthesize(text, language, voice_id) -> audio stream/bytes
└── supports_streaming: bool   # can it start returning audio before the
                                 full sentence is synthesized?
```

Streaming synthesis (speaking the first words while the rest is still
being generated) matters for latency - the LLM Response Generator
(`ai/responder.py`) already produces a full sentence at once (never
token-streamed today), so end-to-end latency is: LLM full response +
TTS synthesis + first-audio-byte. Acceptable for an MVP; a future
optimization would stream the LLM's own output into a streaming TTS
provider sentence-by-sentence. Flagged in §20, not required for v1.

## 6. Streaming strategy

- Audio in (customer → STT): streamed continuously in small chunks over
  the provider's media-streaming channel (e.g. Twilio Media Streams over
  WebSocket) - never batched into one big file and sent after the call.
  Required for real-time turn-taking and interruption detection (§8).
- Audio out (TTS → customer): streamed if the TTS provider supports it
  (§5), otherwise the full synthesized clip is played in one piece - still
  acceptable, just slightly higher latency before the customer hears
  anything.
- The `VoiceSessionManager` is the only component that touches raw audio.
  Everything below it (`ConversationService` downward) still only ever
  sees text, exactly like every other channel - Voice does not leak audio
  concepts into the Business Engine.

## 7. Silence Policy

Two *different* silences, easily conflated - kept explicitly separate:

**A. Turn-ending silence (endpointing)** - how the STT provider decides
the customer finished a sentence. Typically ~700ms–1s of silence after
speech. This is STT-provider configuration, not a Sophie decision, and
happens many times per call without Sophie doing anything.

**B. No-response silence** - the customer said nothing at all after
Sophie asked a question. This *is* a Sophie decision, config-driven
(new `business_rules/voice_rules.yaml`, kept separate from
`followup_rules.yaml` - that file's `silence_threshold_hours: 24` is a
completely different timescale for a completely different problem: an
abandoned chat conversation, not a live phone call):

```yaml
# business_rules/voice_rules.yaml (illustrative - not yet created, Voice C)
no_response_prompt_after_seconds: 5      # "Êtes-vous toujours avec moi ?"
max_no_response_prompts: 2               # then end the call
```

Sequence: 5s silence → gentle check-in prompt (reuses the existing
`ASK_CLARIFICATION`-style pattern, phrased for voice per §12) → 5s more
silence → repeat once → still nothing → end the call gracefully and
schedule a **text-channel** follow-up (SMS/WhatsApp if a phone number is
on file) via the *existing* `followup/engine.py` - no new follow-up logic,
just a new trigger into the system that already exists.

## 8. Interruption Policy (barge-in)

**Decision: allow barge-in.** If the customer starts speaking while
`RESPONSE_PLAYING`, TTS playback stops immediately and the session moves
to `LISTENING`. Rationale: talking over a robot that won't stop talking is
the single most common complaint about voice bots; a natural phone
conversation requires it.

Safety property that makes this safe to allow: interrupting playback never
touches `ConversationState`. The `Action`/`required_action` that produced
the now-interrupted sentence was already decided *before* it started
speaking - abandoning the last few words of "Pouvez-vous me communiquer
votre code EAN..." changes nothing about the Business Engine's state. The
customer's next utterance is processed as a completely ordinary new turn.
No new state, no partial-message recovery logic needed.

## 9. Confirmation Policy

Certain fields are read back and explicitly confirmed before being
accepted - not because the Business Engine changes (validation stays in
`conversation_engine/rules.py`, unchanged), but because voice input for
long alphanumeric strings (EAN, phone, email) is much more error-prone
than typed text, and a misheard EAN silently accepted is worse than one
extra confirmation turn.

This is a **Voice-layer interstitial step**, inserted between "STT
produced a final transcript" and "an `Event` reaches `ConversationService`"
- it never becomes a new `ConversationState`:

```
Customer says EAN digits
        │
        ▼
VoiceSessionManager: "Je vais vous relire votre code EAN : 5-4-1-2-3-4...
                       C'est bien correct ?"
        │
   ┌────┴────┐
  yes        no
   │          │
   ▼          ▼
Event(PROVIDE_INFORMATION,     Ask again (no Event sent yet,
 entities={"ean": "..."})       conversation_engine untouched)
   │
   ▼
ConversationService (exactly like every other channel)
```

Fields requiring confirmation (config-driven, not hardcoded): EAN, phone,
email. Name/city/supplier do not require it - the cost of a small error
there is low and re-confirming everything would make calls tedious.

## 10. Voice Error Recovery

| Failure | Handling |
|---|---|
| STT returns low confidence / empty | Map to `Event(EXTRACTION_FAILED)` - **exactly** the existing path text channels already use for an unparseable message. `ASK_CLARIFICATION`'s talking point gets a voice-appropriate fallback line (§12) - no new Business Engine behavior. |
| Background noise / STT repeatedly fails | After N consecutive `EXTRACTION_FAILED` in a row (config, `voice_rules.yaml`), offer human handoff proactively ("Je vous mets en relation avec un conseiller") rather than looping forever - reuses `REQUEST_HUMAN`/`HANDOFF`, doesn't invent a new terminal state. |
| Call drops mid-conversation | `Conversation` isn't closed - it's left exactly where it was (same principle as a WhatsApp customer going silent). If the customer calls back, §11's find-by-external_id resumes it. If not, the *existing* `followup/engine.py` silence detection eventually picks it up (its candidate-states list already covers every non-terminal `ConversationState` - no change needed). |
| Provider outage (STT/TTS/telephony down) | Fails loud, not silent: call cannot proceed, played (if TTS still reachable) or logged; this is an ops/monitoring concern (dashboard, Phase 7) rather than a Business Engine one. |

## 11. Voice Business Rules

**Decision: none exist, and none should.** `conversation_engine/rules.py`
(qualification field order, EAN/email/phone validation, coverage regions)
applies identically whether the customer typed or spoke. The only new
YAML is `voice_rules.yaml` (§7, §8, §10 configs) - and it deliberately
lives *outside* `business_rules/`'s existing sales-rule files, because it
configures **call mechanics**, not sales decisions. `rules.py` itself
never imports or reads it - preserving the purity guarantee already
enforced by `test_rules.py::test_rules_module_never_touches_the_database`
(and, by the same logic, never touching voice/audio concepts either).

## 12. Voice Prompt Strategy

New prompt variant needed - not a new Business Engine concept, purely a
phrasing constraint on `ai/responder.py`'s LLM call when
`conversation.channel == VOICE`:

- Short sentences (one idea per sentence - a customer can't re-read a
  sentence they half-heard).
- Never read a URL, a long reference number, or an email address as one
  unbroken string - EAN is chunked in groups when read back (§9); an
  email address is better handled by *not* asking for it verbally at all
  where avoidable (e.g., offer to text/WhatsApp a confirmation link
  instead - a genuinely Voice-specific UX call, still zero Business Engine
  changes).
- No filler paragraphs, no "as an AI..." - stays in character as Sophie,
  same as every other channel.

Mechanically: `prompts/responder/system.md` gets a Voice-specific sibling
(e.g. `prompts/responder/system_voice.md`), selected by
`ai/responder.py` based on `conversation.channel` - same
`ai/prompt_loader.py` mechanism already in place, no prompt text in
Python, following the standing rule from the Phase 2 review.

## 13. Voice Provider abstraction

```
VoiceProvider (interface)
├── answer_call(call_id) -> None
├── play_audio(call_id, audio) -> None
├── start_media_stream(call_id) -> stream handle   (for STT, §4/§6)
├── transfer_call(call_id, destination) -> None    (human handoff, §14)
└── end_call(call_id) -> None
```

First concrete implementation: Twilio Voice (`TwilioVoiceProvider`) -
same vendor already integrated for WhatsApp (`TwilioWhatsAppSender`), so
account setup/billing is already in place; Twilio Media Streams gives
bidirectional audio over WebSocket, which §6's streaming strategy needs.
Abstracted so a second provider (Vonage, Amazon Connect, etc.) could be
added later without touching `VoiceSessionManager`.

## 14. Human Handoff during calls

`"Passez-moi un conseiller"` → STT → Extractor recognizes
`REQUEST_HUMAN` (already-existing `EventType`, zero changes) →
`ConversationEngine` returns `HANDOFF` (already-existing transition) →
**new** Voice-specific side effect: `VoiceProvider.transfer_call()` to a
human agent's number/queue, instead of (or in addition to) the text
channels' "NOTIFY_HUMAN" message. This is exactly the same pattern as
`outbound/sender.py` reacting to an engine decision with a channel-specific
action - the *decision* to hand off is the Business Engine's; *how* a
phone call physically transfers is Voice's own concern.

If no human is available to take the transfer immediately, fall back to
the existing HANDOFF message (§ F-016's fix: stays `HANDOFF`, reassures
the customer, doesn't hang up) plus an outbound follow-up callback
scheduled through the existing `followup`/`outbound` machinery.

## 15–16. Diagrams and ConversationService integration

Sequence diagram, one voice turn:

```
Customer      VoiceSessionManager     STT          ConversationService      Responder      TTS
  │  speaks          │                  │                    │                   │           │
  │─────────────────▶│  feed_audio      │                    │                   │           │
  │                  │─────────────────▶│                    │                   │           │
  │                  │                  │ final transcript    │                   │           │
  │                  │◀─────────────────│                    │                   │           │
  │        (confirmation flow if EAN/phone/email - §9)         │                   │           │
  │                  │  handle_message(conversation_id, text) │                   │           │
  │                  │─────────────────────────────────────▶│                   │           │
  │                  │                  │      EngineResult   │                   │           │
  │                  │                  │◀─────────────────  │                   │           │
  │                  │                  │                    │  (already called  │           │
  │                  │                  │                    │   inside handle_message)       │
  │                  │◀─────────────────────────────────────│  response_text     │           │
  │                  │──────────────────────────────────────────────────────────▶│           │
  │                  │                  │                    │                   │  synthesize│
  │                  │◀─────────────────────────────────────────────────────────────────────│
  │◀─────────────────│  play_audio      │                    │                   │           │
```

Note this is **identical** in shape to `WhatsAppChannel.handle_update()`'s
call into `ConversationService.handle_message()` - the STT/TTS boxes are
the only genuinely new participants.

`ConversationService` integration: **zero changes required.** Voice calls
the exact same public methods every other channel already calls
(`start_conversation`/`start_and_greet`, `handle_message`,
`get_conversation_by_external_id`). `external_id` stores the caller's
phone number (E.164), same field, same find-or-create pattern WhatsApp
already established - a customer calling back resumes their conversation,
consistent with every other channel's behavior.

## 17. Integration with existing Business Rules

Already covered in full by §11. Summary: no integration work needed
because nothing changes - `conversation_engine/` doesn't know or care that
a `PROVIDE_INFORMATION` event came from a phone call.

## 18. Testing strategy

No real audio/telephony can be exercised in a sandbox without network
access to a Voice provider (same limitation already true of
`TelegramBotAPISender`/`TwilioWhatsAppSender`, which ship untested by
design, clearly labeled). Voice testing therefore splits into three tiers:

1. **`VoiceSessionManager` unit tests** - fake `SpeechToTextProvider`/
   `TextToSpeechProvider`/`VoiceProvider` (scripted, like
   `ScriptedProvider` already used for `LLMProvider` in the Telegram/
   WhatsApp tests), driving the state machine in §2/§3 directly: turn-taking,
   silence timeouts (§7), interruption handling (§8), confirmation flow (§9),
   error recovery (§10) - all fully testable without any audio.
2. **Integration tests through `ConversationService`** - feed pre-scripted
   "final transcripts" as if STT had produced them, assert the exact same
   engine/responder behavior as the text-channel tests already prove
   (state transitions, qualification, rejection) - proves Voice really does
   reuse the Business Engine unchanged, the single most important property
   this whole document argues for.
3. **Explicitly out of scope for automated testing**: STT transcription
   accuracy, TTS voice quality, real telephony call setup/teardown,
   network jitter/packet loss handling. These need a real provider account
   and manual/staging verification before production - flagged honestly
   rather than pretending a unit test can cover them.

## 19. Edge cases

- **Customer calls back after hanging up mid-qualification**: resumes via
  `external_id` lookup (§16), no new logic - identical to WhatsApp.
- **DTMF (keypad) as an alternative input** for EAN/phone specifically:
  worth strongly considering for v1 given STT's known weakness on long
  digit strings - "press the digits on your keypad instead" as a
  `VoiceProvider` capability (`collect_dtmf`), feeding the exact same
  `Event(PROVIDE_INFORMATION, entities={"ean": ...})` path as speech would.
  A UX decision, not a Business Engine one.
- **Overlapping/rapid interruptions** (customer keeps cutting Sophie off):
  covered by §8, but repeated barge-in without ever finishing a sentence
  is itself a signal - after N rapid interruptions (config), consider it
  equivalent to "customer is frustrated" and proactively offer human
  handoff (§14), same mechanism as the STT-failure escalation in §10.
- **Non-French/Dutch speaker**: STT/TTS language mismatch - detect low
  confidence + wrong-language patterns, offer to switch language if the
  provider supports it, otherwise hand off to human. Not solved by this
  document; flagged for Voice C's design.
- **Multiple people on the line / background conversation**: STT will
  produce garbage: treated as the "background noise" case in §10.

## 20. Production recommendations

- **Start with Twilio's synchronous `<Gather input="speech">`** for the
  MVP (Voice A/B/C, simplified) instead of full real-time bidirectional
  Media Streams: turn-based (record until silence, transcribe, respond,
  repeat) rather than continuously streamed - no interruption/barge-in
  support (§8 becomes "not available in v1"), but dramatically simpler to
  build, test, and reason about, and still exercises 90% of this
  document's design (§2, §3, §7's no-response case, §9, §10, §11, §14,
  §17). Upgrade to streaming Media Streams (full §6/§8) as a v2 once the
  turn-based version is validated with real calls.
- **Cost**: STT/TTS/telephony are billed per-minute (unlike the
  per-message cost of WhatsApp/Telegram) - a stuck or looping call is a
  cost incident, not just a UX one. §7's `max_no_response_prompts` and
  §10's escalate-after-N-failures aren't just UX niceties, they're cost
  controls; monitoring average call duration on the Phase 7 dashboard is
  recommended once Voice ships.
- **Latency budget**: aim for under ~2 seconds from the customer finishing
  a sentence to Sophie starting to respond (STT endpointing + LLM
  extraction + Business Engine + LLM responder + TTS start). This document
  doesn't set a hard number because it depends on the chosen providers -
  worth benchmarking in Voice A before committing to a provider.
- **Recommended implementation order** (Voice A–E, as proposed): A) STT
  interface + Twilio's built-in recognition, B) TTS interface + a Twilio
  or third-party TTS voice, C) `VoiceSessionManager` + `voice_rules.yaml`
  + `ConversationChannel.VOICE`/`LeadSource.PHONE` enum additions (the
  only `domain/enums.py` change this whole document implies), D) upgrade
  to streaming Media Streams once turn-based works end-to-end, E) full
  `VoiceProvider` abstraction if/when a second provider is evaluated.
