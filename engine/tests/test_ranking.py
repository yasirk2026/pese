"""
Unit tests for PESE Ranking V1: pipeline, trace audit, and explainability.
"""

from engine.indexing.document import Document
from engine.indexing.store import DocumentStore
from engine.indexing.inverted_index import InvertedIndex
from engine.passages.extractor import PassageExtractor
from engine.link_graph.graph import LinkGraph
from engine.link_graph.authority import LinkAuthorityCalculator
from engine.ranking.scorer import RankingEngine
from engine.ranking.explain import compare_traces


def test_ranking_trace_and_explainability():
    doc_clean = Document(
        id="clean",
        slug="clean-story",
        title="My Bicycle Story",
        content="I bought my first bicycle on 17 March 2024 from a local shop.",
    )
    doc_spam = Document(
        id="spam",
        slug="spam-store",
        title="Bicycle Store Bicycle Buy",
        content="bicycle " * 40 + "deals buy cheap",
    )

    index = InvertedIndex()
    extractor = PassageExtractor()
    index.index_document(doc_clean, extractor.extract_passages(doc_clean))
    index.index_document(doc_spam, extractor.extract_passages(doc_spam))

    graph = LinkGraph()
    graph.build_from_documents([doc_clean, doc_spam])
    auth = LinkAuthorityCalculator(graph)
    auth.compute_scores()

    engine = RankingEngine(index, auth)
    results = engine.search("when did I buy my bicycle")

    assert len(results) >= 2
    # Clean document must defeat spam document
    assert results[0].slug == "clean-story"
    assert results[0].final_score > results[1].final_score

    # Check trace audit
    trace_win = results[0].trace
    trace_lose = results[1].trace
    comparison = compare_traces(trace_win, trace_lose)

    assert comparison["winner_slug"] == "clean-story"
    assert comparison["score_difference"] > 0
    assert len(comparison["decisive_factors"]) > 0
