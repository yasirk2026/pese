"""
PESE Unit Tests: Phase 2D.1 Runtime Performance, Latency Surgery & Evidence Arbitration
Validates exact date extraction (1941 vs 000 vs 1910), multi-date arbitration,
typo recovery preservation, heading-aware passage ranking, LRU cache behavior, and skip_qa gating.
"""

import pytest
import time
import torch
from engine.indexing.store import DocumentStore
from engine.indexing.inverted_index import InvertedIndex
from engine.passages.extractor import PassageExtractor
from engine.link_graph.graph import LinkGraph
from engine.link_graph.authority import LinkAuthorityCalculator
from engine.semantic.index import VectorIndex
from engine.ranking.scorer import RankingEngine
from engine.neural.inference.qa_reader import QACache, QAResult, _is_exact_temporal_span


@pytest.fixture(scope="module")
def initialized_engine(tmp_path_factory):
    torch.set_num_threads(2)
    from engine.indexing.document import Document
    root = tmp_path_factory.mktemp("runtime-public")
    store = DocumentStore(storage_path=root / "docs.json")
    docs = [Document(id="japan",slug="japan",title="Japan",status="published",content=
        "## History\nThe Meiji Constitution was promulgated in 1889. Japan annexed Taiwan in 1895. "
        "Japan annexed Korea in 1910. Japan invaded China in 1937. Japan entered World War II in 1941. "
        "Japan surrendered in World War II in 1945. The Allied occupation of Japan ended in 1952.\n\n"
        "## Meiji period\nThe Meiji period began in 1868 and ended in 1912."),
        Document(id="meiji",slug="meiji",title="Meiji period",status="published",content=
        "The Meiji period began in 1868 and ended in 1912. The Meiji Constitution was promulgated in 1889."),
        Document(id="bicycle",slug="bicycle",title="Bicycle",status="published",content="A bicycle is a vehicle with two wheels. Bicycle riders use pedals to move a bicycle.")]
    for doc in docs:
        store.save_document(doc)

    index = InvertedIndex()
    extractor = PassageExtractor()
    passages_by_doc = {}
    for d in docs:
        passages = extractor.extract_passages(d)
        passages_by_doc[d.id] = passages
        index.index_document(d, passages)

    vector_index = VectorIndex(index_dir=root / "vectors")
    vector_index.build_index(docs, passages_by_doc)

    graph = LinkGraph()
    graph.build_from_documents(docs)
    auth = LinkAuthorityCalculator(graph)
    auth.compute_scores()

    engine = RankingEngine(index, auth, vector_index=vector_index, doc_store=store)

    # Prewarm
    if vector_index and hasattr(vector_index, "provider"):
        vector_index.provider.embed_query("warmup")
    reader = engine._get_qa_reader()
    if reader:
        reader.read_passage("warmup", "warmup text")

    return engine


def test_ww2_entry_date_arbitration(initialized_engine):
    """Verify 'when did japan enter ww2' extracts 1941 (not 1910 and not 000)."""
    res = initialized_engine.search("when did japan enter ww2")
    assert len(res) > 0
    top = res[0]
    assert top.slug == "japan"
    assert top.is_featured is True
    assert top.featured_answer == "1941"
    assert top.featured_answer != "000"
    assert top.featured_answer != "1910"

    # Neural Shadow mode verification
    if initialized_engine._qa_reader is None:
        assert res.qa_trace is None
        return
    assert res.qa_trace is not None
    assert res.qa_trace["agreement"] == ("YES" if res.qa_trace["shadow_answer"] == "1941" else "NO")
    # An experimental disagreement cannot overwrite the grounded production answer.
    assert top.featured_answer == "1941"


def test_temporal_span_validation():
    """Verify _is_exact_temporal_span rejects subwords and comma-separated numbers like 000."""
    assert _is_exact_temporal_span("1941") is True
    assert _is_exact_temporal_span("1889") is True
    assert _is_exact_temporal_span("17 March 2024") is True
    assert _is_exact_temporal_span("October 2026") is True

    # Reject subwords and invalid dates
    assert _is_exact_temporal_span("000") is False
    assert _is_exact_temporal_span("6,000") is False
    assert _is_exact_temporal_span("14,000") is False
    assert _is_exact_temporal_span("0") is False
    assert _is_exact_temporal_span("") is False


def test_multidate_historical_arbitration(initialized_engine):
    """Verify multi-date arbitration across distinct historical events on Japan passage."""
    queries_and_expected = [
        ("when was the meiji constitution promulgated", "1889"),
        ("when did japan annex taiwan", "1895"),
        ("when did japan annex korea", "1910"),
        ("when did japan invade china", "1937"),
        ("when did japan enter ww2", "1941"),
        ("when did japan surrender in ww2", "1945"),
        ("when did allied occupation of japan end", "1952"),
    ]

    for q, expected_date in queries_and_expected:
        res = initialized_engine.search(q)
        assert len(res) > 0
        assert expected_date in (res[0].featured_answer or ""), f"Query '{q}' expected {expected_date} but got {res[0].featured_answer}"


def test_typo_recovery_preservation(initialized_engine):
    """Verify spelling recovery is preserved for japna -> japan and bycycle -> bicycle."""
    res_japna = initialized_engine.search("japna", skip_qa=True)
    assert res_japna.query_analysis.has_corrections is True
    assert res_japna.query_analysis.effective_query == "japan"
    assert len(res_japna) > 0
    assert "japan" in res_japna[0].title.lower()

    res_bycycle = initialized_engine.search("bycycle", skip_qa=True)
    assert res_bycycle.query_analysis.has_corrections is True
    assert res_bycycle.query_analysis.effective_query == "bicycle"
    assert len(res_bycycle) > 0


def test_heading_aware_passage_selection(initialized_engine):
    """A dedicated evidence page may outrank its broader country parent."""
    res = initialized_engine.search("meiji period", skip_qa=True)
    assert len(res) > 0
    top = res[0]
    assert top.slug in {"meiji", "japan"}
    passage = initialized_engine.passage_scorer.score_passages_for_doc(top.slug,
        __import__("engine.nlp.tokenizer",fromlist=["QueryRepresentation"]).QueryRepresentation("meiji period"))[0][0]
    assert "meiji period" in passage.text.lower()
    assert top.trace.passage_signal > 10.0


def test_lru_qa_cache():
    """Verify in-memory LRU cache stores and retrieves results sub-millisecond."""
    cache = QACache(maxsize=4)
    res = QAResult(
        answer="1941",
        answerable=True,
        answer_confidence=0.95,
        model="PESE-QA-0",
    )

    cache.set("PESE-QA-0", "when did japan enter ww2", "sample passage context", res)
    hit = cache.get("PESE-QA-0", "when did japan enter ww2", "sample passage context")
    assert hit is not None
    assert hit.answer == "1941"

    miss = cache.get("PESE-QA-0", "different question", "sample passage context")
    assert miss is None


def test_skip_qa_bypasses_neural_passes(initialized_engine):
    """Verify skip_qa=True completely bypasses neural reading comprehension."""
    res = initialized_engine.search("when did japan enter ww2", skip_qa=True)
    assert res.timing.get("qa_shadow_ms", 0.0) == 0.0
    assert res.qa_trace is None
    # Deterministic answer should still be present
    assert res[0].featured_answer == "1941"


def test_subsystem_timing_and_work_accounting(initialized_engine):
    """Verify fine-grained subsystem timings and work accounting are populated."""
    res = initialized_engine.search("when did japan enter ww2")
    timing = res.timing
    assert "query_analysis_ms" in timing
    assert "bm25f_retrieval_ms" in timing
    assert "dense_retrieval_ms" in timing
    assert "rrf_fusion_ms" in timing
    assert "evidence_gating_ms" in timing
    assert "ranking_scoring_ms" in timing
    assert "passage_scoring_ms" in timing
    assert "answer_extraction_ms" in timing
    assert "qa_shadow_ms" in timing
    assert "server_total_ms" in timing

    # Work accounting in qa_trace
    trace = res.qa_trace
    if initialized_engine._qa_reader is None:
        assert trace is None
        return
    assert trace is not None
    assert "qa_candidates" in trace
    assert "qa_passages_budgeted" in trace
    assert "qa_windows_created" in trace
    assert "qa_forward_passes" in trace
    assert "qa_early_exit" in trace
    assert "torch_threads" in trace
    assert "model_reused" in trace
    assert trace["model_reused"] is True
