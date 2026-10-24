"""
Unit tests for PESE Retrieval: BM25F and Candidate Retrieval.
"""

from engine.indexing.document import Document
from engine.indexing.inverted_index import InvertedIndex
from engine.passages.extractor import PassageExtractor
from engine.nlp.tokenizer import QueryRepresentation
from engine.retrieval.bm25 import compute_idf, BM25FScorer
from engine.retrieval.candidate_retriever import CandidateRetriever


def test_idf_computation():
    # Frequent term should have lower IDF than rare term
    idf_rare = compute_idf(doc_freq=1, total_docs=20)
    idf_common = compute_idf(doc_freq=15, total_docs=20)
    assert idf_rare > idf_common
    assert idf_rare > 0.0
    assert idf_common > 0.0


def test_bm25f_field_weights():
    doc1 = Document(
        id="d1",
        slug="doc-one",
        title="Bicycle Maintenance Guide",
        content="This is general content about gears and spokes.",
        keywords=["bicycle", "maintenance"],
    )
    doc2 = Document(
        id="d2",
        slug="doc-two",
        title="Random Story",
        content="Yesterday I rode a bicycle down the hill.",
        keywords=["journal"],
    )

    index = InvertedIndex()
    extractor = PassageExtractor()
    index.index_document(doc1, extractor.extract_passages(doc1))
    index.index_document(doc2, extractor.extract_passages(doc2))

    scorer = BM25FScorer(index)
    q_rep = QueryRepresentation("bicycle maintenance")

    score1 = scorer.score_document("d1", q_rep)
    score2 = scorer.score_document("d2", q_rep)

    # doc1 has "bicycle maintenance" in Title and Keywords (higher weighted fields)
    assert score1["bm25f_total"] > score2["bm25f_total"]
    assert score1["title_score"] > 0
    assert score1["keywords_score"] > 0


def test_candidate_retrieval():
    doc = Document(
        id="d1",
        slug="japanese-kanji",
        title="Kanji Radicals Guide",
        content="Radicals are building blocks of kanji.",
        keywords=["kanji", "radicals"],
    )
    index = InvertedIndex()
    extractor = PassageExtractor()
    index.index_document(doc, extractor.extract_passages(doc))

    retriever = CandidateRetriever(index)
    candidates = retriever.retrieve_candidates(QueryRepresentation("kanji radicals"))

    assert len(candidates) == 1
    assert candidates[0]["slug"] == "japanese-kanji"
