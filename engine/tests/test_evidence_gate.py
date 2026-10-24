"""
Unit tests for PESE Minimum Evidence Gate.
Tests evidence gating between candidate retrieval and ranking.
Ensures zero random document leakage on weak or adversarial queries.
"""

import pytest
from engine.indexing.inverted_index import InvertedIndex
from engine.indexing.document import Document
from engine.passages.extractor import PassageExtractor
from engine.ranking.evidence_gate import MinimumEvidenceGate
from engine.query_analysis.analyzer import QueryAnalyzer, AnalyzedQuery
from engine.query_analysis.spelling import CorpusSpellingCorrector


@pytest.fixture
def test_setup():
    # Setup miniature index with 2 documents
    doc1 = Document(
        id="bicycle-story",
        slug="bicycle-story",
        title="My Bicycle Story",
        meta_description="A story about buying a commuter bicycle in March.",
        content="I bought my commuter bicycle on 17 March 2024.",
        keywords=["bicycle", "cycling"],
    )
    doc2 = Document(
        id="japanese-guide",
        slug="japanese-guide",
        title="Japanese Kanji Guide",
        meta_description="Guide to kanji radicals and stroke orders.",
        content="Radicals are the semantic building blocks of written Japanese kanji.",
        keywords=["japanese", "kanji"],
    )

    index = InvertedIndex()
    extractor = PassageExtractor()
    index.index_document(doc1, extractor.extract_passages(doc1))
    index.index_document(doc2, extractor.extract_passages(doc2))

    corrector = CorpusSpellingCorrector()
    corrector.build_vocabulary(index.index, raw_terms=index.raw_terms)
    analyzer = QueryAnalyzer(corrector)
    gate = MinimumEvidenceGate(index)

    return index, analyzer, gate


def test_evidence_gate_passes_grounded_candidates(test_setup):
    index, analyzer, gate = test_setup
    analyzed = analyzer.analyze_query("when did I buy my bicycle")

    candidates = [
        {"doc_id": "bicycle-story", "slug": "bicycle-story", "title": "My Bicycle Story"},
    ]
    passed, decisions = gate.evaluate_candidates(candidates, analyzed)
    assert len(passed) == 1
    assert decisions[0].passed is True


def test_evidence_gate_rejects_zero_content_matches(test_setup):
    index, analyzer, gate = test_setup
    # Query has content term 'bicycle', but candidate is unrelated japanese guide
    analyzed = analyzer.analyze_query("bicycle")

    candidates = [
        {"doc_id": "japanese-guide", "slug": "japanese-guide", "title": "Japanese Kanji Guide"},
    ]
    passed, decisions = gate.evaluate_candidates(candidates, analyzed)
    assert len(passed) == 0
    assert decisions[0].passed is False
    assert "0/1" in decisions[0].reason


def test_evidence_gate_rejects_ungrounded_nonsense(test_setup):
    index, analyzer, gate = test_setup
    # 'zoobadongas' is ungrounded and unknown
    analyzed = analyzer.analyze_query("zoobadongas")

    candidates = [
        {"doc_id": "bicycle-story", "slug": "bicycle-story", "title": "My Bicycle Story"},
    ]
    passed, decisions = gate.evaluate_candidates(candidates, analyzed)
    assert len(passed) == 0
    assert decisions[0].passed is False


class TestAnswerRelevanceGate:
    """Phase 2D.2: Answer Relevance & Evidence Entailment Gate tests."""

    @pytest.fixture
    def relevance_gate(self):
        from engine.passages.answer_relevance import AnswerRelevanceGate
        return AnswerRelevanceGate()

    @pytest.fixture
    def query_analyzer(self):
        corrector = CorpusSpellingCorrector()
        return QueryAnalyzer(corrector)

    def test_rejects_predicate_mismatch(self, relevance_gate, query_analyzer):
        """Case A failure: employment fact must be rejected for flexible payments query."""
        analyzed = query_analyzer.analyze_query("does healing lounge offer flexible payments")
        passage = "The Healing Lounge Pakistan offers therapy and psychiatry. Yasir K. has been working with The Healing Lounge since November 2024."
        candidate = "Yasir K. has been working with The Healing Lounge since November 2024."
        result = relevance_gate.evaluate(
            query="does healing lounge offer flexible payments",
            candidate=candidate,
            passage_text=passage,
            analyzed_query=analyzed,
        )
        assert result.decision == "REJECT"
        assert result.failure_class in ("PREDICATE_MISMATCH", "NO_ANSWER_EVIDENCE")

    def test_rejects_bicycle_generic_fact(self, relevance_gate, query_analyzer):
        """Case B failure: general bicycle definition must be rejected for bicycle spec query."""
        analyzed = query_analyzer.analyze_query("what is my bicycle specification")
        passage = "Bicycles are the principal means of transport in many regions of the world. They provide low-cost mobility."
        candidate = "Bicycles are the principal means of transport in many regions of the world."
        result = relevance_gate.evaluate(
            query="what is my bicycle specification",
            candidate=candidate,
            passage_text=passage,
            analyzed_query=analyzed,
        )
        assert result.decision == "REJECT"
        assert result.failure_class in ("PREDICATE_MISMATCH", "NO_ANSWER_EVIDENCE")

    def test_passes_temporal_answer(self, relevance_gate, query_analyzer):
        """Case C: Grounded temporal answer for WW2 query must pass."""
        analyzed = query_analyzer.analyze_query("when did japan enter ww2")
        passage = "Japan entered World War II in December 1941, following the attack on Pearl Harbor."
        candidate = "1941"
        result = relevance_gate.evaluate(
            query="when did japan enter ww2",
            candidate=candidate,
            passage_text=passage,
            analyzed_query=analyzed,
        )
        assert result.decision == "PASS"
        assert result.final_entailment >= 0.38

    def test_rejects_stripped_negation(self, relevance_gate, query_analyzer):
        """Negation conflict: stripping 'does not' from passage must be rejected."""
        analyzed = query_analyzer.analyze_query("does the healing lounge offer installment plans")
        passage = "The Healing Lounge does not currently offer installment payment plans."
        candidate = "offer installment payment plans"
        result = relevance_gate.evaluate(
            query="does the healing lounge offer installment plans",
            candidate=candidate,
            passage_text=passage,
            analyzed_query=analyzed,
        )
        assert result.decision == "REJECT"
        assert result.failure_class == "NEGATION_CONFLICT"

    def test_passes_semantic_paraphrase(self, relevance_gate, query_analyzer):
        """Semantic paraphrase: fee split into installments provides valid affirmative support."""
        analyzed = query_analyzer.analyze_query("does healing lounge offer flexible payments")
        # The previous fixture named no organization: it could not establish
        # Healing Lounge ownership. Keep paraphrase coverage with grounded identity.
        passage = "Healing Lounge clients may split the consultation fee into two installments upon request."
        candidate = passage
        result = relevance_gate.evaluate(
            query="does healing lounge offer flexible payments",
            candidate=candidate,
            passage_text=passage,
            analyzed_query=analyzed,
        )
        assert result.decision == "PASS"
        assert result.final_entailment >= 0.38

    def test_rejects_adversarial_topical_similarity(self, relevance_gate, query_analyzer):
        """Adversarial topical similarity: 'flexible' matches, but payment has 0 support -> must reject."""
        analyzed = query_analyzer.analyze_query("does healing lounge offer flexible payments")
        passage = "Healing Lounge offers flexible online appointment scheduling for all clients across Pakistan."
        candidate = "Healing Lounge offers flexible online appointment scheduling for all clients across Pakistan."
        result = relevance_gate.evaluate(
            query="does healing lounge offer flexible payments",
            candidate=candidate,
            passage_text=passage,
            analyzed_query=analyzed,
        )
        assert result.decision == "REJECT"
        assert result.failure_class in ("NO_ANSWER_EVIDENCE", "PREDICATE_MISMATCH")
