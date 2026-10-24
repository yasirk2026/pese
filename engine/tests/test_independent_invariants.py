"""Phase 2E integration regressions. Synthetic, inspected development data."""
import pytest
from engine.indexing.document import Document
from engine.indexing.inverted_index import InvertedIndex
from engine.passages.extractor import PassageExtractor
from engine.link_graph.graph import LinkGraph
from engine.link_graph.authority import LinkAuthorityCalculator
from engine.ranking.scorer import RankingEngine
from engine.passages.answer_extractor import FeaturedAnswerExtractor
from engine.passages.answer_relevance import AnswerRelevanceGate
from engine.nlp.tokenizer import QueryRepresentation


def make_engine(docs):
    index = InvertedIndex()
    for doc in docs:
        index.index_document(doc, PassageExtractor().extract_passages(doc))
    graph = LinkGraph()
    graph.build_from_documents(docs)
    auth = LinkAuthorityCalculator(graph)
    auth.compute_scores()
    return RankingEngine(index, auth)


def test_faq_is_not_unconditional_answer():
    doc = Document(id="clinic", slug="clinic", title="Cedar Clinic", content="Cedar Clinic provides online therapy across Nepal.",
        faqs=[{"question":"Who works for Cedar Clinic?", "answer":"Mina has worked with Cedar Clinic since April 2019."}])
    engine = make_engine([doc])
    res = engine.search("Does Cedar Clinic offer flexible payments?", skip_qa=True)
    assert res and res[0].slug == "clinic"
    assert not res[0].is_featured
    assert res[0].featured_answer is None
    assert res[0].trace.answer_relevance_verdict != "PASS"


def test_gate_exception_abstains_and_surfaces_error(monkeypatch):
    engine = make_engine([])
    analyzed = engine.query_analyzer.analyze_query("What is the server port?", force_raw=True)
    extractor = FeaturedAnswerExtractor()
    def broken(**kwargs):
        raise RuntimeError("injected validator outage")
    monkeypatch.setattr(extractor.relevance_gate, "evaluate", broken)
    answer, reason = extractor._apply_relevance_gate("The server port is 8000.", "candidate", "The server port is 8000.", analyzed)
    assert answer is None
    assert extractor.last_relevance_result.failure_class == "ANSWER_GATE_EXCEPTION"


@pytest.mark.parametrize("query,candidate,passage", [
    ("Does Cedar Clinic offer installment payments?", "Mina joined Cedar Clinic in 2019.", "Mina joined Cedar Clinic in 2019. Cedar Clinic offers installment payments."),
    ("When did Rhea join?", "2022", "Lio joined in 2022. Rhea joined in 2024."),
    ("When did Orion annex Kappa?", "1843", "Orion annexed Delta in 1843. Orion annexed Kappa in 1862."),
    ("Does Aster accept cryptocurrency?", "Boreal accepts cryptocurrency.", "Aster accepts cards. Boreal accepts cryptocurrency."),
])
def test_other_sentence_cannot_supply_missing_relation(query, candidate, passage):
    analyzed = make_engine([]).query_analyzer.analyze_query(query, force_raw=True)
    verdict = AnswerRelevanceGate().evaluate(query, candidate, passage, analyzed)
    assert verdict.decision != "PASS"


def test_skip_qa_does_not_even_load_model(monkeypatch):
    engine = make_engine([Document(id="x",slug="x",title="Quartz",content="Quartz launched in 2016.")])
    def forbidden():
        pytest.fail("skip_qa loaded neural model")
    monkeypatch.setattr(engine,"_get_qa_reader",forbidden)
    assert engine.search("When did Quartz launch?",skip_qa=True)


def test_spelling_preserves_unseen_inflection():
    from engine.query_analysis.spelling import CorpusSpellingCorrector
    corrector = CorpusSpellingCorrector()
    corrector.build_vocabulary({},raw_terms={"entering":2,"center":50,"launches":3,"lunch":50})
    assert corrector.correct_token("enter") is None
    assert corrector.correct_token("launched") is None


def test_repeating_question_is_not_answer():
    analyzed=make_engine([]).query_analyzer.analyze_query("What is thermal mass?",force_raw=True)
    verdict=AnswerRelevanceGate().evaluate("What is thermal mass?","What is thermal mass?","What is thermal mass?",analyzed)
    assert verdict.decision=="REJECT"
    assert verdict.failure_class=="QUESTION_WITHOUT_ANSWER"


def test_cached_ranking_isolated_and_limit_independent():
    engine=make_engine([Document(id=str(n),slug=str(n),title=f"Quartz {n}",content=f"Quartz instrument {n} launched in 2016.") for n in range(3)])
    first=engine.search("Quartz",limit=1,skip_qa=True)
    second=engine.search("Quartz",limit=3,skip_qa=True)
    assert len(first)==1 and len(second)==3
    assert second.timing["cache_hit"]==1
    second[0].title="injected change"
    assert engine.search("Quartz",skip_qa=True)[0].title!="injected change"


def test_nominal_topic_is_not_asserted_action():
    query="What does a CPU execute?"
    analyzed=make_engine([]).query_analyzer.analyze_query(query,force_raw=True)
    gate=AnswerRelevanceGate()
    irrelevant="The roadmap includes CPU-aware execution where available."
    assert gate.evaluate(query,irrelevant,irrelevant,analyzed).decision=="REJECT"
    evidence="The CPU executes instructions."
    assert gate.evaluate(query,evidence,evidence,analyzed).decision=="PASS"
