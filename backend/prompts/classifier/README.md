# prompts/classifier/

Empty on purpose. `conversation_engine/intent_classifier.py` is currently a
normalization seam, not an LLM call (see its own docstring) - Phase 3C
("Intent Classifier LLM/NLP réel" per the reordered Phase 3 plan) will add a
real prompt here, in the same Markdown format as `prompts/extractor/system.md`,
without touching how `state_machine.py` consumes its output.
