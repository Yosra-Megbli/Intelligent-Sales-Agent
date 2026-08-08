# ai/ — Phase 3

## Phase 3A — LLM Adapter (done)

`providers/interface.py` — `LLMProvider` abstract base class. One method,
`generate(messages, *, temperature, max_tokens, json_mode) -> LLMResponse`.
`json_mode=True` asks the vendor to constrain output to valid JSON where
supported (Phase 3B's extractor will use this); this layer never parses or
interprets `content` itself. Every provider raises `LLMError` (or a
subclass: `LLMTimeoutError`, `LLMRateLimitError`, `LLMAuthenticationError`)
on failure — never a vendor SDK exception — so callers stay decoupled from
which vendor is configured.

`providers/groq.py` — `GroqProvider`, the first concrete implementation.
Retries timeouts/connection errors/rate limits with exponential backoff
(configurable `max_retries`), never retries auth or bad-request errors, and
reads `GROQ_API_KEY` / `GROQ_MODEL` from the environment
(`.env.example`, default model `openai/gpt-oss-120b`). The `groq`
package is imported lazily so `ai/` can be imported and unit-tested without
it installed — tests inject a fake client via `GroqProvider(client=...)`.

13 new tests in `tests/test_llm_provider.py`, including an AST purity check
(same technique as `test_rules_module_never_touches_the_database`) proving
`providers/groq.py` never imports `crm`, a repository, or `domain` — it
sends messages and returns text, nothing else. 73 tests total, all passing.

## Phase 3B — Extractor (done)

`extractor.py` — `Extractor(provider).extract(raw_text, expected_field=...)`
makes one `LLMProvider.generate(..., json_mode=True)` call per customer
message and turns the JSON result into a Phase 2 `Event`
(`conversation_engine/transitions.py`). The prompt states only the fixed
`EventType`/entity *vocabulary* (rule 3: prompts never contain business
logic) — never coverage regions, validation formats, or field order, which
stay exclusively in `business_rules/*.yaml` and `conversation_engine/
rules.py`. Any hallucinated event type, unknown entity key, or malformed
JSON is discarded and the call falls back to `EventType.EXTRACTION_FAILED`
rather than trusting the model. `expected_field` is passed as context only
(e.g. "Sophie's last question was about: ean") — it never forces a value.

24 new tests in `tests/test_extractor.py` (happy paths per intent, entity
whitelisting/normalization, empty/whitespace/malformed-JSON/LLM-error
fallbacks, an "LLM cannot fabricate a system-only EventType" defense-in-depth
check, and the same AST purity check). 97 tests total, all passing.

## Phase 3C — Intent Classifier, real NLP (done)

`conversation_engine/intent_classifier.py` keeps its exact Phase 2 contract
(`classify(event) -> Event`, unrecognized types become `EXTRACTION_FAILED`)
and adds one thing: `IntentClassifier(provider)` now takes an optional
`LLMProvider` and an optional `current_state` kwarg. The Extractor (3B) is
deliberately single-message/context-light and falls back to
`EventType.CUSTOMER_MESSAGE` when unsure; this is the one layer with access
to conversation-level context (which dialogue step Sophie is on), so it's
the right place for a second, state-aware look - not the Extractor. This
only fires for that one fallback case (not every message), so a normal turn
still costs a single LLM call; any failure (no provider, malformed JSON,
LLM error, hallucinated type) falls back to the original event unchanged -
this layer never returns something worse than Phase 2 gave it.

16 new tests in `tests/test_intent_classifier.py` (Phase 2 contract intact,
"confident events never re-sent to the LLM", state-aware disambiguation,
every failure mode falling back gracefully, same purity check). 113 tests
total, all passing.

## Phase 3D — Response Generator (done)

`responder.py` — `Responder(provider).respond(required_action, conversation=...,
lead=None, rejection_reason=None, rag_answer=None)` turns the
`required_action` string produced by `state_machine.py` (surfaced to callers
via `conversation_engine/engine.py`'s `EngineResult`) into the sentence
Sophie sends. It never receives an `Action` directly - by the time Phase 3D
runs, `state_machine.py` has already translated the Business Rules Engine's
`Action` into a plain string, so the responder deals with exactly the same
vocabulary the engine already exposes.

Each `required_action` maps to a fixed talking point ("what to say", never
"whether/why") in `_TALKING_POINTS`; `SEND_REJECTION` additionally routes
through the `RejectionReason` the engine already decided, via
`_REJECTION_TALKING_POINTS`. The talking point is the only business content
the LLM call receives - coverage regions, EAN validation, rejection logic
etc. stay exclusively in `business_rules/*.yaml` and `conversation_engine/
rules.py`, same discipline as the extractor's prompt. `ANSWER_FAQ` /
`ANSWER_OBJECTION` are handled separately: they only ever repeat the
`rag_answer` string they're given (Phase 3E's job to supply), never their
own facts, and fall back to a generic "handing this to a colleague" line
when no `rag_answer` is provided yet.

Every `required_action` also has a fixed, hardcoded French fallback string.
If `provider` is `None`, the LLM call raises `LLMError`, or the response
comes back empty, `respond()` returns the fallback instead of raising -
Sophie must always have something to say, even in a fully degraded LLM
outage. `NONE` (and a missing `required_action`) return `None` without
calling the LLM at all, since not every engine turn produces a message.

37 new tests in `tests/test_responder.py` (every talking-point action
reaches the LLM correctly, language is threaded through, fallback on no
provider / LLM error / empty response, silent actions never call the LLM,
every `RejectionReason` is covered, FAQ/OBJECTION only ever speak the given
`rag_answer`, and the same AST purity check plus a cross-check against
`state_machine.py`'s literal `required_action` strings so a new one can't
silently fall through unnoticed). 148 tests total, all passing.

## Phase 3E — RAG (done)

`rag.py` + `knowledge_base.yaml` — `Rag().answer(raw_text, category="faq" |
"objection")` matches the customer's raw message against a small,
hand-curated knowledge base and returns the single fact Sophie is allowed
to state, or `None` if nothing matches well enough. Matching is plain
keyword overlap (single-word keywords via set intersection, multi-word
keywords like "contrat actuel" require the exact phrase in order) - no
embeddings, no vector store, no LLM call in this module at all. The
knowledge base is small and hand-curated, so a transparent, dependency-free
match is easier to test and reason about than a vector index would be at
this volume of content; swapping in a real retriever later only needs a new
implementation behind the same `Rag.answer()` contract.

`knowledge_base.yaml` holds the facts (fees, contract terms, regulator
names, common objections) as pure data, same shape as `business_rules/
*.yaml`. This is the one place in `ai/` where the YAML legitimately carries
business *content* - because answering questions is this module's entire
job - but never business *logic*: the matching algorithm and the phrasing
both stay in code (`rag.py` and `ai/responder.py` respectively).

`Rag` and `ai/responder.py`'s `Responder` are deliberately not wired
together inside `ai/` - `Rag().answer(event.raw_answer_text,
category="faq")` produces the fact, and that string is passed in as
`Responder.respond("ANSWER_FAQ", ..., rag_answer=...)`'s `rag_answer`
argument. Composing the two is the orchestration layer's job (Phase 4:
channels), same reasoning as why `engine.py` doesn't call the Extractor
itself.

15 new tests in `tests/test_rag.py` (keyword and phrase matching, category
isolation, best-score-wins on ties, empty/no-match input, every real
knowledge base entry is well-formed and reachable, same AST purity check).
163 tests total, all passing.

Phase 3 (LLM Adapter, Extractor, Intent Classifier, Response Generator,
RAG) is now complete.

## Still to come

- `providers/gemini.py`, `providers/openai.py` — more concrete providers
  behind the same `LLMProvider` interface, if/when needed.
- Wiring `ai/extractor.py`, `ai/rag.py` and `ai/responder.py` into
  `conversation_engine/engine.py` / the channel layer (Phase 4).

Golden rule (enforced by the purity test, not just this paragraph): nothing
in this package may write to `Lead.status`, `Lead.qualification_score`, or
`Conversation.current_state` directly.
