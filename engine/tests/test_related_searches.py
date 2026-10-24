"""
Unit tests for PESE Related Searches Engine.
Verifies topic coherence, link neighborhood extraction,
scoring traces, and empty-state safety.
"""

import pytest
from engine.indexing.store import DocumentStore
from engine.link_graph.graph import LinkGraph
from engine.discovery.related_searches import RelatedSearchEngine
from engine.discovery.history import LocalHistoryStore
from engine.discovery.sessions import SessionManager
from engine.discovery.families import QueryFamilyRegistry


@pytest.fixture
def related_fixture(tmp_path, public_discovery_store):
    store = public_discovery_store
    docs = store.list_documents(status="published")
    graph = LinkGraph()
    graph.build_from_documents(docs)

    events_file = tmp_path / "test_events.jsonl"
    hist_store = LocalHistoryStore(events_path=events_file, settings_path=tmp_path / "settings.json")
    sess_mgr = SessionManager(hist_store)
    registry = QueryFamilyRegistry()

    engine = RelatedSearchEngine(
        store=store,
        graph=graph,
        history_store=hist_store,
        session_manager=sess_mgr,
        family_registry=registry,
    )
    return engine


def test_topical_related_searches(related_fixture):
    res = related_fixture.get_related_searches(
        "japanese roadmap",
        top_slugs=["japanese-beginner-roadmap", "hiragana-notes"],
        limit=5,
        debug=True,
    )
    assert len(res.related_searches) >= 2
    # Verify related queries belong to Japanese learning
    texts = [r.query.lower() for r in res.related_searches]
    assert any("hiragana" in t or "vocabulary" in t or "kanji" in t for t in texts)
    # Verify debug trace is populated
    assert "topic_overlap_score" in res.related_searches[0].debug_trace


def test_empty_state_nonsense_query(related_fixture):
    # Nonsense query with no evidence MUST return 0 related searches
    res = related_fixture.get_related_searches(
        "flimflamglurp xyz",
        top_slugs=[],
        limit=5,
    )
    assert len(res.related_searches) == 0


def test_no_identical_query_surfaced(related_fixture):
    query = "japanese beginner roadmap"
    res = related_fixture.get_related_searches(
        query,
        top_slugs=["japanese-beginner-roadmap"],
        limit=5,
    )
    for item in res.related_searches:
        assert item.query.lower() != query.lower()
