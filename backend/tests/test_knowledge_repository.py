from crm.knowledge_repository import KnowledgeRepository


def _create(repo, **overrides):
    defaults = dict(
        category="faq",
        question="Comment changer de fournisseur ?",
        keywords=["changer", "comment"],
        answer_fr="Le changement se fait en ligne.",
    )
    defaults.update(overrides)
    return repo.create(**defaults)


def test_create_and_get_round_trips_keywords(db_session):
    repo = KnowledgeRepository(db_session)
    entry = _create(repo, keywords=["a", "b", "c"])

    fetched = repo.get_by_id(entry.id)

    assert fetched.get_keywords() == ["a", "b", "c"]


def test_list_active_excludes_inactive_entries(db_session):
    repo = KnowledgeRepository(db_session)
    _create(repo, question="Active one", active=True)
    _create(repo, question="Inactive one", active=False)

    active = repo.list_active()

    assert len(active) == 1
    assert active[0].question == "Active one"


def test_update_fields_replaces_keywords(db_session):
    repo = KnowledgeRepository(db_session)
    entry = _create(repo, keywords=["old"])

    repo.update_fields(entry, keywords=["new", "words"])

    assert entry.get_keywords() == ["new", "words"]


def test_delete_removes_the_row(db_session):
    repo = KnowledgeRepository(db_session)
    entry = _create(repo)
    entry_id = entry.id

    repo.delete(entry)

    assert repo.get_by_id(entry_id) is None


def test_answer_for_language_falls_back_to_french(db_session):
    repo = KnowledgeRepository(db_session)
    entry = _create(repo, answer_fr="Reponse FR", answer_nl=None, answer_en="EN answer")

    assert entry.answer_for_language("fr") == "Reponse FR"
    assert entry.answer_for_language("nl") == "Reponse FR"  # no NL answer set
    assert entry.answer_for_language("en") == "EN answer"
