"""Release invariants, independent of personal data and neural checkpoints."""
import pytest
from engine.evaluation.phase2f_support import build_engine, closure_documents, document
from engine.nlp.local_context import resolve_local_context


@pytest.fixture(scope="module")
def closure_engine(tmp_path_factory):
    return build_engine(closure_documents(), tmp_path_factory.mktemp("closure"), semantic=False)


def test_owned_property_beats_generic_and_seo(closure_engine):
    result = closure_engine.search("what are my camera specifications", skip_qa=True)
    assert result[0].slug == "owned"
    assert result[0].trace.ownership_factor > 1


def test_missing_attribute_abstains(closure_engine):
    assert all(not r.is_featured for r in closure_engine.search("what color is my camera", skip_qa=True))
    assert "530" in (closure_engine.search("what is my camera weight", skip_qa=True)[0].featured_answer or "")


def test_bounded_coreference(closure_engine):
    result = closure_engine.search("when did Mira envision NOVA", skip_qa=True)
    assert result[0].featured_answer == "2022"
    result = closure_engine.search("when did Cora launch project", skip_qa=True)
    assert not result[0].is_featured
    resolved, _ = resolve_local_context("He created it.", "Ali spoke to Hamza. He created it.")
    assert resolved == "He created it."


def test_passage_relation_over_date(closure_engine):
    result = closure_engine.search("when did Linden railway open", skip_qa=True)
    assert result[0].featured_answer == "1903"


def test_contradiction_is_not_randomly_promoted(tmp_path):
    docs = [d for d in closure_documents() if d.slug == "nearby"]
    eng = build_engine(docs, tmp_path, semantic=False)
    assert not eng.search("does Morrow offer installment payments", skip_qa=True)[0].is_featured


def test_explicit_current_policy_wins(tmp_path):
    docs = [d for d in closure_documents() if d.slug == "current"]
    eng = build_engine(docs, tmp_path, semantic=False)
    result = eng.search("does Citrine offer installment payments", skip_qa=True)
    assert "does not" in (result[0].featured_answer or "")


def test_relation_similarity_cannot_authorize_wrong_action(tmp_path):
    """Exposed holdout regression: topical evidence does not identify a repairer."""
    eng = build_engine([document("clock", "Nimber station clock",
        "Nimber station's platform clock stopped during the winter storm. "
        "The damaged mechanism was sent to Tessa Wren in the hill workshop. "
        "She repaired the escapement and returned the clock before the spring timetable began.")], tmp_path, semantic=False)
    class MisleadingSimilarity:
        threshold = 0.84
        def similarity(self, *args):
            return 0.99
    eng.relation_matcher = MisleadingSimilarity()
    result = eng.search("Who repaired Nimber station's platform clock after the winter storm?", skip_qa=True)
    assert not result[0].is_featured


@pytest.mark.parametrize("field", ["title", "headings", "content", "faqs", "metadata"])
def test_stuffing_and_short_exact_fact(tmp_path, field):
    good = document("good", "Kestrel creator", "Kestrel was created by Rowan Vale.")
    spam = document("spam", "Kestrel creator", "This page offers unrelated discount coupons and promotions.")
    if field == "title": spam.title = "Kestrel creator " * 18
    if field == "headings": spam.headings = ["Kestrel creator " * 18]
    if field == "content": spam.content = "Kestrel creator cheap deals " * 80
    if field == "faqs": spam.faqs = [{"id":str(i), "question":"Who created Kestrel?", "answer":"Kestrel creator cheap deals."} for i in range(20)]
    if field == "metadata": spam.meta_description = "Kestrel creator " * 20
    eng = build_engine([good, spam], tmp_path, semantic=False)
    result = eng.search("who created Kestrel", skip_qa=True)
    assert result[0].slug == "good"
    assert eng._spam["spam"]["spam_penalty"] >= 0.3


def test_link_and_freshness_secondary(tmp_path):
    good = document("good", "Prism mass", "The Prism instrument weighs 18 kg.", updated_at="2001-01-01T00:00:00Z")
    wrong = document("wrong", "Instrument newsletter", "This new newsletter discusses instruments and popular exhibitions.", updated_at="2026-10-22T00:00:00Z")
    hubs = [document(f"hub{i}", f"Newsletter index {i}", "Read the [instrument newsletter](/doc/wrong).", internal_links=["wrong"]) for i in range(15)]
    eng = build_engine([good, wrong]+hubs, tmp_path, semantic=False)
    assert eng.search("how much does Prism instrument weigh", skip_qa=True)[0].slug == "good"
