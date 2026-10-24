"""
PESE Search Sync: Test Suite for Neural Shadow Bridge
Phase N3-B: PESE-Rel-0 Real Search Observer Tests

Verifies that PESE-Rel-0 operates in pure shadow mode:
1. Zero authority over ranking, scores, or featured answers.
2. Identical SERP behavior with shadow ON vs OFF.
3. Strict fail-open guarantees on model or storage crashes.
4. Budget caps, batch identity correspondence, and feedback join.
5. Immutability of checkpoint and tokenizer artifacts.
"""

import hashlib
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from engine.neural.models.registry import registry, ModelStatus
from engine.search_sync.contracts import (
    FeedbackType,
    TargetType,
    FeedbackEvent,
    FeedbackReason,
    classify_diagnostic_alignment,
)
from engine.search_sync.feedback_store import SearchSyncFeedbackStore
from engine.search_sync.preference_signal import SearchSyncPreferenceSignal, normalize_sync_query
from engine.search_sync.neural_shadow import (
    PESERelationShadowAdapter,
    DEFAULT_CHECKPOINT_PATH,
    DEFAULT_TOKENIZER_PATH,
)
from engine.indexing.document import Document
from engine.indexing.inverted_index import InvertedIndex
from engine.indexing.snapshot import SnapshotStore
from engine.link_graph.graph import LinkGraph
from engine.link_graph.authority import LinkAuthorityCalculator
from engine.passages.extractor import PassageExtractor
from engine.ranking.scorer import RankingEngine
from engine.api.main import app

CHECKPOINT_EXPECTED_SHA256 = "1dd87075cfbf23c09fed5e90be948c6c7af005e9e909ab47e5df6c374b56ff70"
TOKENIZER_EXPECTED_SHA256 = "e2023f42797473452a4a702ddb0894b6540277b85f5bdcc7436ecd1587ea03ec"


@pytest.fixture
def temp_sync_store(tmp_path):
    """Provides an isolated SQLite feedback & observation store."""
    db_file = tmp_path / "test_shadow_sync.db"
    store = SearchSyncFeedbackStore(db_path=db_file)
    yield store
    store.clear_all()


@pytest.fixture
def synthetic_shadow_engine(temp_sync_store):
    """
    Constructs a controlled synthetic search engine with real passages
    and the real PESE-Rel-0 resident shadow adapter.
    """
    doc_nadia = Document(
        id="doc-station-clock",
        slug="station-clock-history",
        title="The Old Railway Station Clock",
        content="The station clock was built in 1910. Engineer Nadia repaired the station clock in 1998 after a storm.",
        keywords=["station", "clock", "repaired", "nadia", "engineer"],
        headings=["Restoration History"],
        published=True,
    )
    doc_storm = Document(
        id="doc-station-storm",
        slug="station-storm-archive",
        title="The Railway Station Storm of 1998",
        content="A severe winter storm struck the railway station in 1998. The station clock stopped during the storm.",
        keywords=["station", "clock", "stopped", "storm"],
        headings=["Meteorological Records"],
        published=True,
    )

    docs = [doc_nadia, doc_storm]
    extractor = PassageExtractor()
    index = InvertedIndex()
    for d in docs:
        psgs = extractor.extract_passages(d)
        index.index_document(d, psgs)

    graph = LinkGraph()
    graph.build_from_documents(docs)
    auth = LinkAuthorityCalculator(graph)
    auth.compute_scores()

    doc_store = SnapshotStore(docs)
    pref_signal = SearchSyncPreferenceSignal(store=temp_sync_store)
    shadow_adapter = PESERelationShadowAdapter()

    engine = RankingEngine(
        index=index,
        link_authority=auth,
        vector_index=None,
        doc_store=doc_store,
        search_sync=pref_signal,
        shadow_adapter=shadow_adapter,
    )
    return engine, temp_sync_store, doc_nadia, doc_storm, shadow_adapter


# ==================== 1. INVARIANT TESTS ====================

def test_checkpoint_and_tokenizer_hash_invariants():
    """Section 38 & 54: Checkpoint and tokenizer files must remain byte-for-byte frozen."""
    assert DEFAULT_CHECKPOINT_PATH.exists()
    assert DEFAULT_TOKENIZER_PATH.exists()

    ckpt_hash = hashlib.sha256(DEFAULT_CHECKPOINT_PATH.read_bytes()).hexdigest()
    tok_hash = hashlib.sha256(DEFAULT_TOKENIZER_PATH.read_bytes()).hexdigest()

    assert ckpt_hash == CHECKPOINT_EXPECTED_SHA256, "Checkpoint SHA-256 mutation detected!"
    assert tok_hash == TOKENIZER_EXPECTED_SHA256, "Tokenizer SHA-256 mutation detected!"


def test_registry_authority_invariants():
    """Section 3, 39 & 55: PESE-Rel-0 must remain EXPERIMENT with zero authority."""
    card = registry.get("PESE-Rel-0")
    assert card is not None
    assert card.model_id == "PESE-Rel-0"
    assert card.status == ModelStatus.EXPERIMENT
    assert card.allowed_for_ranking is False
    assert card.allowed_for_answers is False


# ==================== 2. ZERO BEHAVIOR CHANGE TEST ====================

def test_zero_behavior_change_ranking_and_scores(synthetic_shadow_engine, monkeypatch):
    """
    Section 8, 9 & 46: Search behavior must be byte-for-byte identical
    whether neural shadow is ON or OFF.
    """
    engine, store, _, _, shadow_adapter = synthetic_shadow_engine
    query = "Who repaired the station clock?"

    # 1. Search with Shadow OFF
    monkeypatch.setenv("PESE_REL_SHADOW_ENABLED", "false")
    engine.invalidate_query_cache(query)
    res_off = engine.search(query, limit=10, skip_qa=False)

    # 2. Search with Shadow ON
    monkeypatch.setenv("PESE_REL_SHADOW_ENABLED", "true")
    engine.invalidate_query_cache(query)
    res_on = engine.search(query, limit=10, skip_qa=False)

    assert len(res_off) == len(res_on)
    for off_item, on_item in zip(res_off, res_on):
        # Document ranking order must be identical
        assert off_item.rank == on_item.rank
        assert off_item.doc_id == on_item.doc_id
        assert off_item.slug == on_item.slug

        # Base scores and final scores must match exactly
        assert off_item.base_score == pytest.approx(on_item.base_score, abs=1e-5)
        assert off_item.final_score == pytest.approx(on_item.final_score, abs=1e-5)
        assert off_item.search_sync_adjustment == pytest.approx(on_item.search_sync_adjustment, abs=1e-5)

        # Featured Answer selection must be identical
        assert off_item.is_featured == on_item.is_featured
        assert off_item.featured_answer == on_item.featured_answer
        assert off_item.snippet_text == on_item.snippet_text

    # Neural metadata only exists when ON
    assert res_off[0].neural_shadow is None or res_off[0].neural_shadow.get("status") == "DISABLED"
    assert res_on[0].neural_shadow is not None
    assert res_on[0].neural_shadow.get("authority") == "NONE"


# ==================== 3. OBSERVATION RECORDING TESTS ====================

def test_high_support_observation_persisted(synthetic_shadow_engine):
    """
    Section 47: Valid evidence candidates are scored and persisted to SQLite.
    """
    engine, store, doc_nadia, _, _ = synthetic_shadow_engine
    query = "Who repaired the station clock?"
    context_id = "sc_test_high_support"

    results = engine.search(query, limit=10, search_context_id=context_id, skip_qa=False)
    assert len(results) > 0

    top_result = results[0]
    assert top_result.neural_shadow is not None
    assert top_result.neural_shadow["authority"] == "NONE"
    assert 0.0 <= top_result.neural_shadow["answers_probability"] <= 1.0

    # Verify persisted in SQLite
    persisted_obs = store.get_neural_observations(context_id)
    assert len(persisted_obs) >= 1

    first_obs = persisted_obs[0]
    assert first_obs.model_id == "PESE-Rel-0"
    assert first_obs.authority == "NONE"
    assert first_obs.checkpoint_hash == CHECKPOINT_EXPECTED_SHA256
    assert first_obs.query == query


def test_distractor_observation_persisted(synthetic_shadow_engine):
    """
    Section 48: Topical distractors are observed and evaluated without crashing.
    """
    engine, store, _, doc_storm, _ = synthetic_shadow_engine
    query = "Who repaired the station clock?"
    context_id = "sc_test_distractor"

    results = engine.search(query, limit=10, search_context_id=context_id, skip_qa=False)
    storm_result = next((r for r in results if r.doc_id == doc_storm.id), None)
    assert storm_result is not None

    assert storm_result.neural_shadow is not None
    assert storm_result.neural_shadow["authority"] == "NONE"
    assert isinstance(storm_result.neural_shadow["answers_probability"], float)


# ==================== 4. FAIL-OPEN ISOLATION TESTS ====================

def test_model_failure_does_not_break_search(synthetic_shadow_engine):
    """
    Section 27 & 49: If PESE-Rel-0 forward pass throws an exception,
    search must succeed with status='SHADOW_ERROR' and ranking intact.
    """
    engine, store, _, _, shadow_adapter = synthetic_shadow_engine
    query = "Who repaired the station clock?"

    # Baseline search
    baseline = engine.search(query, limit=10, skip_qa=True)
    baseline_slugs = [r.slug for r in baseline]
    baseline_scores = [r.final_score for r in baseline]

    # Force model forward pass to fail
    with patch.object(shadow_adapter, "_load_model_and_tokenizer", side_effect=RuntimeError("Simulated PyTorch CUDA/OOM failure")):
        engine.invalidate_query_cache(query)
        failed_res = engine.search(query, limit=10, skip_qa=False)

        assert len(failed_res) == len(baseline)
        assert [r.slug for r in failed_res] == baseline_slugs
        assert [r.final_score for r in failed_res] == baseline_scores

        # Verify fallback diagnostic status
        for r in failed_res:
            assert r.neural_shadow is not None
            assert "SHADOW_ERROR" in r.neural_shadow["status"]
            assert r.neural_shadow["authority"] == "NONE"


def test_store_failure_does_not_break_search(synthetic_shadow_engine):
    """
    Section 27 & 50: If SQLite database fails during observation insert,
    search must succeed without interruption.
    """
    engine, store, _, _, _ = synthetic_shadow_engine
    query = "Who repaired the station clock?"

    with patch.object(store, "record_neural_observations", side_effect=sqlite3.OperationalError("Simulated SQLite lock")):
        engine.invalidate_query_cache(query)
        results = engine.search(query, limit=10, skip_qa=False)
        assert len(results) > 0
        assert results[0].doc_id is not None


# ==================== 5. BUDGETING & BATCHING TESTS ====================

def test_candidate_budget_cap_enforced():
    """
    Section 6 & 56: Massive candidate sets must be capped to max_candidate_budget.
    """
    adapter = PESERelationShadowAdapter(max_candidate_budget=4)
    many_candidates = [
        {
            "target_id": f"doc-{i}",
            "target_slug": f"doc-{i}",
            "target_type": "SERP_RESULT",
            "evidence_id": f"doc-{i}#p0",
            "evidence_text": f"Evidence text candidate number {i}",
        }
        for i in range(25)
    ]

    summaries, observations = adapter.observe_candidates(
        query="Test query",
        normalized_query="test query",
        search_context_id="sc_budget_test",
        candidate_items=many_candidates,
    )
    assert len(observations) <= 4


def test_batch_identity_correspondence():
    """
    Section 13 & 57: Candidate items maintain exact identity across batch inference.
    """
    adapter = PESERelationShadowAdapter()
    candidates = [
        {"target_id": "doc-a", "target_slug": "slug-a", "target_type": "SERP_RESULT", "evidence_id": "a#p1", "evidence_text": "First passage"},
        {"target_id": "doc-b", "target_slug": "slug-b", "target_type": "SERP_RESULT", "evidence_id": "b#p1", "evidence_text": "Second passage"},
    ]
    summaries, observations = adapter.observe_candidates(
        query="Test query",
        normalized_query="test query",
        search_context_id="sc_batch_test",
        candidate_items=candidates,
    )
    assert len(observations) == 2
    assert observations[0].target_id == "doc-a"
    assert observations[0].evidence_id == "a#p1"
    assert observations[1].target_id == "doc-b"
    assert observations[1].evidence_id == "b#p1"


# ==================== 6. FEEDBACK JOIN & RERANK INTEGRATION ====================

def test_feedback_join(synthetic_shadow_engine):
    """
    Section 20-22 & 51: Reconstructs joined record:
    MAAE decision + PESE-Rel-0 observation + user feedback.
    """
    engine, store, doc_nadia, _, _ = synthetic_shadow_engine
    query = "Who repaired the station clock?"
    norm_q = normalize_sync_query(query)
    context_id = "sc_feedback_join_ctx"

    # 1. User searches
    results = engine.search(query, limit=10, search_context_id=context_id, skip_qa=False)
    top_doc = results[0]

    # 2. User clicks DISLIKE on top result
    dislike_event = FeedbackEvent(
        search_context_id=context_id,
        query=query,
        normalized_query=norm_q,
        target_type=TargetType.SERP_RESULT,
        target_id=top_doc.doc_id,
        target_slug=top_doc.slug,
        rank_position=1,
        feedback=FeedbackType.DISLIKE,
        reason=FeedbackReason.WRONG_RESULT.value,
        maae_base_score=top_doc.base_score,
    )
    store.record_feedback(dislike_event)

    # 3. Inspect joined feedback records
    joined = store.get_feedback_with_neural_observations(query=query)
    assert len(joined) >= 1

    match = next(item for item in joined if item["target_id"] == top_doc.doc_id)
    assert match["query"] == query
    assert match["human_feedback"] == "DISLIKE"
    assert match["neural_model"] == "PESE-Rel-0"
    assert match["answers_probability"] is not None
    assert match["neural_authority"] == "NONE"
    assert match["diagnostic_alignment"] is not None


def test_search_sync_rerank_still_works_with_shadow_active(synthetic_shadow_engine):
    """
    Section 52: Search Sync N3-A preference reranking continues to function
    with neural shadow active.
    """
    engine, store, doc_nadia, doc_storm, _ = synthetic_shadow_engine
    query = "Who repaired the station clock?"
    norm_q = normalize_sync_query(query)

    res_before = engine.search(query, limit=10, skip_qa=False)
    winner_before = res_before[0]
    runner_before = res_before[1]

    # Dislike #1
    store.record_feedback(
        FeedbackEvent(
            query=query,
            normalized_query=norm_q,
            target_type=TargetType.SERP_RESULT,
            target_id=winner_before.doc_id,
            target_slug=winner_before.slug,
            feedback=FeedbackType.DISLIKE,
        )
    )
    engine.invalidate_query_cache(query)

    res_after = engine.search(query, limit=10, skip_qa=False)
    item_winner = next(r for r in res_after if r.doc_id == winner_before.doc_id)
    assert item_winner.search_sync_adjustment == -4.0
    assert item_winner.search_sync_feedback == "DISLIKE"
    assert item_winner.neural_shadow is not None
    assert item_winner.neural_shadow["authority"] == "NONE"


def test_query_isolation_with_shadow_active(synthetic_shadow_engine):
    """
    Section 53: Preference signals stay isolated per query with shadow active.
    """
    engine, store, doc_nadia, _, _ = synthetic_shadow_engine
    q1 = "Who repaired the station clock?"
    q2 = "What was the weather during the 1998 storm?"

    # Dislike doc_nadia on q1
    store.record_feedback(
        FeedbackEvent(
            query=q1,
            normalized_query=normalize_sync_query(q1),
            target_type=TargetType.SERP_RESULT,
            target_id=doc_nadia.id,
            feedback=FeedbackType.DISLIKE,
        )
    )

    # Search q2
    res_q2 = engine.search(q2, limit=10, skip_qa=False)
    item = next((r for r in res_q2 if r.doc_id == doc_nadia.id), None)
    if item:
        assert item.search_sync_adjustment == 0.0
        assert item.search_sync_feedback is None


# ==================== 7. DEVELOPER VIEW & API TESTS ====================

def test_developer_view_trace_lines(synthetic_shadow_engine):
    """
    Section 31-32 & 58: Developer View RankingTrace includes neural shadow diagnostics
    with unmistakable 'Authority: NONE'.
    """
    engine, _, _, _, _ = synthetic_shadow_engine
    query = "Who repaired the station clock?"

    results = engine.search(query, limit=10, skip_qa=False)
    top_trace_lines = results[0].trace.summary_lines()

    assert any("NEURAL SHADOW (PESE-Rel-0)" in line for line in top_trace_lines)
    assert any("P(ANSWERS):" in line for line in top_trace_lines)
    assert any("Authority: NONE" in line for line in top_trace_lines)
    assert any("Final Ranking Score:" in line for line in top_trace_lines)


def test_neural_shadow_api_endpoints():
    """
    Section 14 & 64: API endpoints for inspecting shadow observations and stats.
    """
    client = TestClient(app)

    # 1. Stats endpoint
    stats_res = client.get("/api/search/neural-shadow/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "total_observations" in stats
    assert stats["model_authority"] == "NONE"

    # 2. Joined records endpoint
    rec_res = client.get("/api/search/neural-shadow")
    assert rec_res.status_code == 200
    records = rec_res.json()
    assert records["model_id"] == "PESE-Rel-0"
    assert records["authority"] == "NONE"
    assert isinstance(records["records"], list)
