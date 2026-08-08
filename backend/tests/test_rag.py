"""
Tests for the Phase 3E RAG module.

No LLM involved here - `Rag` is pure keyword-overlap retrieval against
`knowledge_base.yaml`. What's under test is the matching logic itself
(category filtering, multi-word phrase matching, empty/no-match handling)
and that every knowledge base entry is actually reachable and well-formed -
never the wording of the answers, which is business content, not code.
"""

from ai.rag import KnowledgeEntry, Rag, _ENTRIES


def make_rag(*entries: KnowledgeEntry) -> Rag:
    return Rag(entries=entries)


_FEE_ENTRY = KnowledgeEntry(
    id="switching_fees",
    category="faq",
    keywords=("gratuit", "cout", "frais"),
    answer="Le changement est gratuit.",
)
_CONTRACT_ENTRY = KnowledgeEntry(
    id="already_have_contract",
    category="objection",
    keywords=("deja", "contrat actuel"),
    answer="Comparer sans quitter le fournisseur actuel.",
)


# --- basic matching ------------------------------------------------------


def test_single_keyword_match_returns_the_answer():
    rag = make_rag(_FEE_ENTRY)
    result = rag.answer("Est-ce que c'est gratuit ?", category="faq")
    assert result == "Le changement est gratuit."


def test_no_keyword_overlap_returns_none():
    rag = make_rag(_FEE_ENTRY)
    result = rag.answer("Bonjour, comment allez-vous ?", category="faq")
    assert result is None


def test_wrong_category_is_never_matched():
    rag = make_rag(_FEE_ENTRY)
    # "gratuit" would match _FEE_ENTRY's keywords, but it's a faq entry and
    # we're asking for objection - must not leak across categories.
    result = rag.answer("Est-ce que c'est gratuit ?", category="objection")
    assert result is None


def test_multi_word_keyword_requires_the_exact_phrase_in_order():
    phrase_only_entry = KnowledgeEntry(
        id="already_have_contract",
        category="objection",
        keywords=("contrat actuel",),
        answer="Comparer sans quitter le fournisseur actuel.",
    )
    rag = make_rag(phrase_only_entry)

    matched = rag.answer("Je suis deja avec un contrat actuel ailleurs", category="objection")
    not_matched = rag.answer("Mon contrat est actuel mais je ne suis pas deja convaincu", category="objection")

    assert matched == "Comparer sans quitter le fournisseur actuel."
    # "actuel" and "contrat" both appear, but not as the phrase "contrat
    # actuel" - a bag-of-words match would wrongly fire here too.
    assert not_matched is None


def test_best_scoring_entry_wins_when_multiple_entries_could_match():
    weak_entry = KnowledgeEntry(id="weak", category="faq", keywords=("energie",), answer="weak answer")
    strong_entry = KnowledgeEntry(
        id="strong", category="faq", keywords=("energie", "verte", "renouvelable"), answer="strong answer"
    )
    rag = make_rag(weak_entry, strong_entry)

    result = rag.answer("Votre energie verte est-elle renouvelable ?", category="faq")

    assert result == "strong answer"


# --- empty / missing input ------------------------------------------------------


def test_none_raw_text_returns_none():
    rag = make_rag(_FEE_ENTRY)
    assert rag.answer(None, category="faq") is None


def test_blank_raw_text_returns_none():
    rag = make_rag(_FEE_ENTRY)
    assert rag.answer("   ", category="faq") is None


def test_message_with_no_recognizable_words_returns_none():
    rag = make_rag(_FEE_ENTRY)
    assert rag.answer("???!!!", category="faq") is None


# --- match_id ------------------------------------------------------


def test_match_id_returns_the_entry_id_not_the_answer_text():
    rag = make_rag(_FEE_ENTRY)
    assert rag.match_id("c'est gratuit ?", category="faq") == "switching_fees"


def test_match_id_returns_none_when_nothing_matches():
    rag = make_rag(_FEE_ENTRY)
    assert rag.match_id("bonjour", category="faq") is None


# --- the real knowledge base ------------------------------------------------------


def test_real_knowledge_base_loads_and_has_both_categories():
    categories = {entry.category for entry in _ENTRIES}
    assert categories == {"faq", "objection"}
    assert len(_ENTRIES) >= 10


def test_real_knowledge_base_entries_are_well_formed():
    seen_ids = set()
    for entry in _ENTRIES:
        assert entry.id not in seen_ids, f"duplicate entry id: {entry.id}"
        seen_ids.add(entry.id)
        assert entry.category in ("faq", "objection")
        assert entry.keywords, f"{entry.id} has no keywords"
        assert entry.answer.strip(), f"{entry.id} has an empty answer"


def test_real_knowledge_base_price_objection_is_reachable():
    rag = Rag()
    result = rag.answer("Je trouve ca vraiment trop cher comme tarif", category="objection")
    assert result is not None
    assert "consommation" in result or "tarif" in result


def test_real_knowledge_base_faq_about_documents_is_reachable():
    rag = Rag()
    result = rag.answer("De quels documents ai-je besoin pour changer ?", category="faq")
    assert result is not None
    assert "EAN" in result


# --- purity ------------------------------------------------------


def test_rag_module_never_touches_the_database_or_crm():
    """Golden rule, same technique as
    test_extractor_module_never_touches_the_database_or_crm and
    test_responder_module_never_touches_the_database_or_crm: rag.py reads
    text and returns a fact string, nothing else."""
    import ast
    import inspect

    from ai import rag as rag_module

    tree = ast.parse(inspect.getsource(rag_module))

    forbidden_call_names = {"flush", "commit", "add", "save"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = getattr(node, "module", None) or ""
            names = [alias.name for alias in node.names]
            assert "crm" not in module_name and not any("repository" in n.lower() for n in names), (
                f"ai/rag.py must not import repositories, found: {module_name or names}"
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_call_names, (
                f"ai/rag.py must stay pure, found a call to '.{node.func.attr}()'"
            )
