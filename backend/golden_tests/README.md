# Golden Tests

Answers one question before anything else in the roadmap (Dashboard,
Alembic, ...) is touched: **does Sophie actually behave like a correct
sales agent when a real French customer talks to her?**

This is deliberately separate from `tests/` (which already covers each
module in isolation with synthetic payloads) and from `business_rules/*`
(which covers the rules themselves). This suite is about *end-to-end
behavior on realistic French conversations* - intents, entities, state
transitions, qualification, objections, FAQ, handoff, and the ambiguous/
edge cases that tend to hide behind a passing unit-test suite.

## Two completely separate layers

| | `test_golden_messages.py` / `test_golden_conversations.py` | `run_real_llm_eval.py` |
|---|---|---|
| Runs via | `pytest` | standalone script |
| Provider | `ScriptedProvider` (fake, scripted to the golden label) | real `GroqProvider` |
| Network / cost | none | real LLM calls |
| Determinism | 100% | not guaranteed run to run |
| What it proves | the engine (state machine, rules, dialogue policy, entity normalization) does the right thing **given correct extraction** | whether the **actual model** reads a French message correctly |
| Gate? | yes - CI, always green | no - a report, not a pass/fail gate |

This split exists on purpose (see the audit): a pytest suite that calls a
real LLM either becomes flaky/slow/costly, or gets quietly skipped. Keeping
regression tests fake-provider-only means they can run on every commit;
keeping the real-LLM check as its own script means someone actually looks
at its output instead of it silently going green or red in CI noise.

## Running the deterministic suite (always safe, no network)

```bash
cd backend
pytest golden_tests/ -v
```

- `test_golden_messages.py`: dataset sanity checks + confirms Extractor's
  own JSON parsing/entity normalization doesn't mangle a correct LLM
  output.
- `test_golden_conversations.py`: replays every scenario in
  `scenarios/conversations.yaml` through the real `ConversationEngine`,
  turn by turn, asserting the resulting `ConversationState` (and, where
  specified, `required_action`) after each turn - not just the final one.

## Running the real-LLM evaluation (costs tokens, non-deterministic)

```bash
cd backend
export GROQ_API_KEY=...
python golden_tests/run_real_llm_eval.py
python golden_tests/run_real_llm_eval.py --category price_question_vs_objection
python golden_tests/run_real_llm_eval.py --save-report golden_tests/reports/$(date +%Y%m%d).json
```

Prints per-category accuracy and every mismatch (input, expected vs actual
event_type/entities). **Read the failures before changing any code** - the
rule from the audit applies here specifically: only fix what a failure
actually demonstrates (e.g. if `"Combien coûte votre offre ?"` comes back
as `OBJECTION`, that's an extractor-prompt fix; it is not a reason to
rewrite the agent, the state machine, or the architecture).

Currently covers `scenarios/messages.yaml` only (single-message intent +
entity extraction, including the `IntentClassifier` second-pass for
`current_state`-tagged scenarios) - this is where the audit's flagged risk
(`prix`/`cher` ambiguity, informal French, etc.) actually lives. Extending
it to replay `scenarios/conversations.yaml` turn-by-turn against the real
model is a natural next step once message-level accuracy looks solid, but
wasn't built yet - state-machine-level real-LLM eval needs a live
`db_session`, not just a provider, and mismatches would need
allow-listing for cases where two different `event_type`s are behaviorally
equivalent (e.g. `PROVIDE_INFORMATION` vs `CUSTOMER_MESSAGE` inside
`DISCOVERY`, which the state machine treats identically).

## What's in `scenarios/`

- **`messages.yaml`** (39 scenarios): one customer message each, with the
  `event_type`/`entities` Sophie's Extractor + IntentClassifier should
  produce. Organized by risk category: price question vs. objection,
  switching vs. cancelling, eligibility/region, EAN handling, refusals,
  human handoff requests, change-of-mind (incl. bare "oui"/"non"),
  incomplete information, repeated questions, informal/misspelled French,
  small talk, and multi-entity messages.
- **`conversations.yaml`** (9 scenarios, ~70 turns total): full multi-turn
  conversations - happy path to qualification, FAQ/objection detours that
  must resume correctly, out-of-coverage rejection, change-of-mind
  rejection, mid-qualification human handoff, invalid-EAN correction loop,
  excessive-detours escalation, and duplicate-lead rejection.

Some scenario notes flag things this pass already found just from tracing
the code against realistic conversations (documented in-line rather than
"fixed" silently, per the audit's own rule to only act on a demonstrated
failure):

- `conv_excessive_detours_escalate_to_human`, turn 2: two `QUESTION`/
  `OBJECTION` events in a row (no real customer answer in between) never
  reach the FAQ/OBJECTION "resume" branch at all - the global override for
  `QUESTION`/`OBJECTION` fires first regardless of `current_state`, so
  `transition_state(remember_previous=True)` ends up recording the
  *detour* state as the thing to resume to, overwriting the real
  `previous_state`. The detour-count escalation still saves this specific
  scenario, but a customer who eventually stopped detouring would resume
  into `FAQ`/`OBJECTION` instead of their real interrupted step.
- `conv_full_happy_path` / any scenario reaching `DATA_VALIDATION`: unlike
  `QUALIFIED -> HANDOFF` (auto-chained via `QUALIFICATION_ADVANCE`,
  F-011 fix), reaching `DATA_VALIDATION` does **not** automatically run
  `decide_validation()` - it only runs on the next `process_turn()` call.
  In production that means Sophie doesn't proactively validate right after
  the EAN is given; she waits for one more customer message of any kind.
  Worth confirming with the product owner whether that's intended.

## Adding a scenario

Append to the relevant YAML file - no code changes needed. Both suites
load scenarios dynamically (`harness.py`), and `test_golden_messages.py`
enforces the dataset stays well-formed (valid `event_type`, valid entity
keys, ≥30 scenarios, ≥8 categories) as part of the regular pytest run.
