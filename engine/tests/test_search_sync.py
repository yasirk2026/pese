"""
PESE Search Sync: Test Suite for User-to-Search Feedback Loop Genesis
Phase N3-A: Acceptance, Invariant & Regression Tests

Validates:
1. Dislike changes ranking for the same query (Before / After).
2. Query isolation (Other queries for the same document remain unaffected).
3. Like provides bounded positive adjustment (+2.0).
4. Vote toggle / change replaces prior preference cleanly (no compounding).
5. Duplicate clicks are idempotent.
6. Persistence across restart (SQLite disk storage).
7. Zero feedback preserves exact baseline ranking scores.
8. Featured Answer feedback records distinctly and suppresses on dislike.
9. Query normalization handles casing, punctuation, and whitespace equivalence.
10. Feedback API endpoint validation and security invariants.
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from engine.search_sync.contracts import (
    FeedbackType,
    TargetType,
    FeedbackReason,
    FeedbackEvent,
    FeedbackSubmission,
)
from engine.search_sync.feedback_store import SearchSyncFeedbackStore
from engine.search_sync.preference_signal import (
    SearchSyncPreferenceSignal,
    normalize_sync_query,
    DEFAULT_DISLIKE_PENALTY,
    DEFAULT_LIKE_BONUS,
)
from engine.indexing.document import Document
from engine.indexing.inverted_index import InvertedIndex
from engine.indexing.snapshot import SnapshotStore
from engine.link_graph.graph import LinkGraph
from engine.link_graph.authority import LinkAuthorityCalculator
from engine.passages.extractor import PassageExtractor
from engine.ranking.scorer import RankingEngine
from engine.api.main import app


@pytest.fixture
def temp_feedback_store(tmp_path):
    """Provides an isolated SQLite feedback store per test."""
    db_file = tmp_path / "test_feedback.db"
    store = SearchSyncFeedbackStore(db_path=db_file)
    yield store
    store.clear_all()


@pytest.fixture
def synthetic_search_engine(temp_feedback_store):
    """
    Builds a minimal controlled two-document search engine where
    Document A slightly outranks Document B for query 'who develops gta'.
    """
    doc_a = Document(
        id="doc-gta-5",
        slug="gta-5-development",
        title="Grand Theft Auto VI: Studio Development History",
        content="Rockstar North develops Grand Theft Auto VI and Grand Theft Auto V games. Studio development release history details.",
        keywords=["gta", "develops", "rockstar", "studio", "v", "vi"],
        headings=["Studio History"],
        published=True,
    )
    doc_b = Document(
        id="doc-gta-6",
        slug="gta-6-development",
        title="Grand Theft Auto VI: Studio Development Report",
        content="Rockstar Games develops Grand Theft Auto VI and Grand Theft Auto V games. Release history details.",
        keywords=["gta", "develops", "rockstar", "studio", "v", "vi"],
        headings=["Studio History"],
        published=True,
    )

    docs = [doc_a, doc_b]
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
    pref_signal = SearchSyncPreferenceSignal(store=temp_feedback_store)

    engine = RankingEngine(
        index=index,
        link_authority=auth,
        vector_index=None,
        doc_store=doc_store,
        search_sync=pref_signal,
    )
    return engine, temp_feedback_store, doc_a, doc_b


def test_query_normalization_equivalence():
    """Verify that casing, punctuation, and whitespace normalize identically."""
    q1 = "Who develops GTA VI?"
    q2 = "who develops gta vi"
    q3 = "WHO DEVELOPS GTA VI"
    q4 = "  who develops   gta vi...  "

    n1 = normalize_sync_query(q1)
    n2 = normalize_sync_query(q2)
    n3 = normalize_sync_query(q3)
    n4 = normalize_sync_query(q4)

    assert n1 == "who develops gta vi"
    assert n1 == n2 == n3 == n4


def test_dislike_changes_same_query_ranking(synthetic_search_engine):
    """
    Section 54 & 77: Before / After demo.
    Disliking the top result on query Q applies a bounded penalty (-4.0)
    and allows the second result to take the #1 rank on the next search.
    """
    engine, store, doc_a, doc_b = synthetic_search_engine
    query = "Who develops GTA VI?"

    # 1. Search BEFORE feedback
    results_before = engine.search(query, limit=10)
    assert len(results_before) == 2
    top_before = results_before[0]
    second_before = results_before[1]

    initial_winner_slug = top_before.slug
    initial_runner_slug = second_before.slug
    initial_top_score = top_before.final_score
    initial_runner_score = second_before.final_score

    print("BEFORE: #1", top_before.slug, top_before.final_score, "#2", second_before.slug, second_before.final_score)
    print("TOP TRACE:", top_before.trace.summary_lines())
    print("SECOND TRACE:", second_before.trace.summary_lines())

    assert top_before.search_sync_adjustment == 0.0
    assert top_before.search_sync_feedback is None

    # 2. User dislikes result #1
    norm_q = normalize_sync_query(query)
    dislike_event = FeedbackEvent(
        query=query,
        normalized_query=norm_q,
        target_type=TargetType.SERP_RESULT,
        target_id=top_before.doc_id,
        target_slug=top_before.slug,
        rank_position=1,
        feedback=FeedbackType.DISLIKE,
        reason=FeedbackReason.WRONG_RESULT.value,
        maae_base_score=initial_top_score,
    )
    store.record_feedback(dislike_event)
    engine.invalidate_query_cache(query)

    # 3. Search AFTER feedback
    results_after = engine.search(query, limit=10)
    assert len(results_after) == 2
    top_after = results_after[0]
    second_after = results_after[1]

    print("AFTER: #1", top_after.slug, top_after.final_score, "adj:", top_after.search_sync_adjustment, "#2", second_after.slug, second_after.final_score, "adj:", second_after.search_sync_adjustment)

    # Verify ranking changed: the previous runner-up is now #1!
    assert top_after.slug == initial_runner_slug
    assert second_after.slug == initial_winner_slug

    # Verify score inspectability
    assert second_after.base_score == pytest.approx(initial_top_score, abs=0.001)
    assert second_after.search_sync_adjustment == pytest.approx(-4.0, abs=0.001)
    assert second_after.search_sync_feedback == "DISLIKE"
    assert second_after.final_score == pytest.approx(initial_top_score - 4.0, abs=0.001)

    # Verify trace inspectability
    trace_lines = second_after.trace.summary_lines()
    assert any("MAAE Base Score:" in line for line in trace_lines)
    assert any("Search Sync Preference: DISLIKE (-4.0000)" in line for line in trace_lines)


def test_other_query_unaffected_contextual_isolation(synthetic_search_engine):
    """
    Section 55 & 78: Query isolation demo.
    Disliking document D for query Q1 must NOT penalize document D for query Q2.
    """
    engine, store, doc_a, doc_b = synthetic_search_engine
    query_1 = "Who develops GTA VI?"
    query_2 = "When was GTA V released?"

    # Dislike doc_a on query_1
    norm_q1 = normalize_sync_query(query_1)
    store.record_feedback(
        FeedbackEvent(
            query=query_1,
            normalized_query=norm_q1,
            target_type=TargetType.SERP_RESULT,
            target_id=doc_a.id,
            target_slug=doc_a.slug,
            feedback=FeedbackType.DISLIKE,
        )
    )

    # Search query_2
    results_q2 = engine.search(query_2, limit=10)
    # Find doc_a in results
    doc_a_item = next((r for r in results_q2 if r.doc_id == doc_a.id), None)
    assert doc_a_item is not None

    # On query_2, doc_a must have ZERO Search Sync penalty!
    assert doc_a_item.search_sync_adjustment == 0.0
    assert doc_a_item.search_sync_feedback is None
    assert doc_a_item.final_score == doc_a_item.base_score


def test_like_provides_bounded_positive_signal(synthetic_search_engine):
    """
    Section 56: Liking a result provides a bounded positive preference bonus (+2.0).
    """
    engine, store, doc_a, doc_b = synthetic_search_engine
    query = "Who develops GTA VI?"

    results_before = engine.search(query, limit=10)
    second_before = results_before[1]
    initial_score = second_before.final_score

    # Like the second result
    norm_q = normalize_sync_query(query)
    store.record_feedback(
        FeedbackEvent(
            query=query,
            normalized_query=norm_q,
            target_type=TargetType.SERP_RESULT,
            target_id=second_before.doc_id,
            target_slug=second_before.slug,
            feedback=FeedbackType.LIKE,
        )
    )
    engine.invalidate_query_cache(query)

    results_after = engine.search(query, limit=10)
    liked_item = next(r for r in results_after if r.doc_id == second_before.doc_id)

    assert liked_item.search_sync_adjustment == pytest.approx(2.0, abs=0.001)
    assert liked_item.search_sync_feedback == "LIKE"
    assert liked_item.final_score == pytest.approx(initial_score + 2.0, abs=0.001)


def test_change_vote_toggle_cleanly_replaces_preference(synthetic_search_engine):
    """
    Section 57: Changing vote (LIKE -> DISLIKE) cleanly supersedes prior state
    without compounding weights.
    """
    engine, store, doc_a, doc_b = synthetic_search_engine
    query = "Who develops GTA VI?"
    norm_q = normalize_sync_query(query)

    # Vote 1: LIKE (+2.0)
    store.record_feedback(
        FeedbackEvent(
            query=query,
            normalized_query=norm_q,
            target_type=TargetType.SERP_RESULT,
            target_id=doc_b.id,
            feedback=FeedbackType.LIKE,
        )
    )
    engine.invalidate_query_cache(query)
    res_1 = engine.search(query, limit=10)
    item_1 = next(r for r in res_1 if r.doc_id == doc_b.id)
    assert item_1.search_sync_adjustment == 2.0
    assert item_1.search_sync_feedback == "LIKE"

    # Vote 2: User changes to DISLIKE (-4.0)
    store.record_feedback(
        FeedbackEvent(
            query=query,
            normalized_query=norm_q,
            target_type=TargetType.SERP_RESULT,
            target_id=doc_b.id,
            feedback=FeedbackType.DISLIKE,
            reason=FeedbackReason.OUTDATED.value,
        )
    )
    engine.invalidate_query_cache(query)
    res_2 = engine.search(query, limit=10)
    item_2 = next(r for r in res_2 if r.doc_id == doc_b.id)
    assert item_2.search_sync_adjustment == -4.0
    assert item_2.search_sync_feedback == "DISLIKE"


def test_duplicate_click_idempotency(synthetic_search_engine):
    """
    Section 58: Repeated clicks on the same feedback button do not multiply adjustment.
    """
    engine, store, doc_a, doc_b = synthetic_search_engine
    query = "Who develops GTA VI?"
    norm_q = normalize_sync_query(query)

    for _ in range(5):
        store.record_feedback(
            FeedbackEvent(
                query=query,
                normalized_query=norm_q,
                target_type=TargetType.SERP_RESULT,
                target_id=doc_a.id,
                feedback=FeedbackType.DISLIKE,
            )
        )

    active_map = store.get_active_preferences_for_query(norm_q)
    assert len(active_map) == 1 or len(active_map) == 2  # keyed by id and/or slug
    event = active_map[doc_a.id]
    assert event.feedback == FeedbackType.DISLIKE

    engine.invalidate_query_cache(query)
    results = engine.search(query, limit=10)
    item = next(r for r in results if r.doc_id == doc_a.id)
    # Must still be -4.0, never -20.0
    assert item.search_sync_adjustment == -4.0


def test_persistence_across_restart(tmp_path):
    """
    Section 59 & 79: Persistence demo.
    Saved feedback persists to SQLite file and loads in a new engine instance.
    """
    db_file = tmp_path / "persistent_sync.db"
    store_1 = SearchSyncFeedbackStore(db_path=db_file)

    query = "Who develops GTA VI?"
    norm_q = normalize_sync_query(query)

    store_1.record_feedback(
        FeedbackEvent(
            query=query,
            normalized_query=norm_q,
            target_type=TargetType.SERP_RESULT,
            target_id="doc-gta-6",
            feedback=FeedbackType.LIKE,
            reason=None,
        )
    )

    # Simulate full engine restart: create brand-new store from the same disk file
    store_2 = SearchSyncFeedbackStore(db_path=db_file)
    active = store_2.get_active_preferences_for_query(norm_q)

    assert "doc-gta-6" in active
    assert active["doc-gta-6"].feedback == FeedbackType.LIKE
    assert active["doc-gta-6"].query == query


def test_no_feedback_preserves_baseline_scores(synthetic_search_engine):
    """
    Section 60: Queries with zero feedback produce identical baseline behavior.
    """
    engine, store, _, _ = synthetic_search_engine
    query = "Who develops GTA VI?"

    results = engine.search(query, limit=10)
    for r in results:
        assert r.search_sync_adjustment == 0.0
        assert r.search_sync_feedback is None
        assert r.base_score == r.final_score


def test_featured_answer_suppression(synthetic_search_engine):
    """
    Section 61: Disliking a Featured Answer on Query Q suppresses it for Query Q
    while keeping other queries intact.
    """
    engine, store, doc_a, doc_b = synthetic_search_engine
    query = "Who develops GTA VI?"
    norm_q = normalize_sync_query(query)

    res_before = engine.search(query, limit=10)
    top_doc = res_before[0]

    # Dislike Featured Answer for query on the top result
    store.record_feedback(
        FeedbackEvent(
            query=query,
            normalized_query=norm_q,
            target_type=TargetType.FEATURED_ANSWER,
            target_id=top_doc.doc_id,
            feedback=FeedbackType.DISLIKE,
            reason=FeedbackReason.WRONG_RESULT.value,
        )
    )
    engine.invalidate_query_cache(query)

    results = engine.search(query, limit=10)
    # Top item must not have is_featured == True
    assert results[0].is_featured is False
    assert results[0].featured_answer is None
    assert "Suppressed by Search Sync" in (results[0].featured_justification or "")


def test_feedback_api_endpoints():
    """
    Section 47-50: Test API endpoints for submitting, querying, and clearing feedback.
    """
    client = TestClient(app)

    # 1. Clear any existing feedback
    del_res = client.delete("/api/search/feedback")
    assert del_res.status_code == 200

    # 2. Submit valid feedback
    payload = {
        "search_context_id": "test-ctx-123",
        "query": "Who develops GTA VI?",
        "target_type": "SERP_RESULT",
        "target_id": "kc-gta-five",
        "target_slug": "kc-gta-five",
        "rank_position": 1,
        "feedback": "DISLIKE",
        "reason": "Wrong result",
    }
    post_res = client.post("/api/search/feedback", json=payload)
    assert post_res.status_code == 200
    data = post_res.json()
    assert data["status"] == "success"
    assert data["normalized_query"] == "who develops gta vi"
    assert data["search_sync_adjustment"] == -4.0

    # 3. Query feedback
    get_res = client.get("/api/search/feedback?q=Who develops GTA VI?")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert "kc-gta-five" in get_data["preferences"]
    assert get_data["preferences"]["kc-gta-five"]["feedback"] == "DISLIKE"

    # 4. Reject invalid submissions
    bad_payload = {
        "query": "",  # Empty query
        "target_type": "SERP_RESULT",
        "target_id": "doc-1",
        "feedback": "DISLIKE",
    }
    bad_res = client.post("/api/search/feedback", json=bad_payload)
    assert bad_res.status_code == 422 or bad_res.status_code == 400

    # 5. Reset feedback
    reset_res = client.delete("/api/search/feedback")
    assert reset_res.status_code == 200
    check_empty = client.get("/api/search/feedback")
    assert check_empty.json()["total_active_preferences"] == 0
