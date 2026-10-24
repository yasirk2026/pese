"""
Unit tests for PESE 'You Might Also Ask' (PAA) Engine.
Verifies the Answerability Gate, deterministic candidate generation,
duplicate prevention, and non-hallucination on unsupported queries.
"""

import pytest
from engine.indexing.store import DocumentStore
from engine.indexing.inverted_index import InvertedIndex
from engine.passages.extractor import PassageExtractor
from engine.link_graph.graph import LinkGraph
from engine.link_graph.authority import LinkAuthorityCalculator
from engine.ranking.scorer import RankingEngine
from engine.discovery.questions import PAAQuestionEngine, canonical_question_key
from engine.discovery.families import QueryFamilyRegistry


@pytest.fixture
def questions_fixture(public_discovery_store):
    store = public_discovery_store
    docs = store.list_documents(status="published")

    extractor = PassageExtractor()
    index = InvertedIndex()
    for doc in docs:
        passages = extractor.extract_passages(doc)
        index.index_document(doc, passages)

    graph = LinkGraph()
    graph.build_from_documents(docs)
    auth = LinkAuthorityCalculator(graph)
    auth.compute_scores()

    ranking_engine = RankingEngine(index, auth)
    registry = QueryFamilyRegistry()

    engine = PAAQuestionEngine(
        store=store,
        ranking_engine=ranking_engine,
        family_registry=registry,
    )
    return engine


def test_paa_grounded_answerability(questions_fixture):
    res = questions_fixture.get_questions_for_query(
        "what is PESE",
        top_slugs=["what-is-pese", "what-is-pese-developed-with"],
        limit=3,
        debug=True,
    )
    assert len(res.questions) > 0
    # Every question must have passed the Answerability Gate with an answer
    for q_item in res.questions:
        assert q_item.answerability_status == "PASS"
        assert len(q_item.answer.strip()) > 3
        assert q_item.source_slug != ""
        assert "gate_passed" in q_item.debug_trace


def test_paa_suppression_on_unsupported_query(questions_fixture):
    # Nonsense query with no evidence must return ZERO questions
    res = questions_fixture.get_questions_for_query(
        "what is flimflamglurp",
        top_slugs=[],
        limit=5,
    )
    assert len(res.questions) == 0


def test_canonical_question_key():
    k1 = canonical_question_key("Who developed PESE?")
    k2 = canonical_question_key("Who created PESE?")
    k3 = canonical_question_key("Who built PESE?")
    assert k1 == k2 == k3
