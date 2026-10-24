"""
Unit tests for PESE Query Session Intelligence.
Verifies session state, topic token extraction, reformulation tracking,
and bounded context scoring.
"""

import pytest
from engine.discovery.models import QuerySessionEvent
from engine.discovery.sessions import SessionManager, QuerySession, extract_topic_tokens
from engine.discovery.history import LocalHistoryStore


@pytest.fixture
def session_fixture(tmp_path):
    events_file = tmp_path / "test_session_events.jsonl"
    store = LocalHistoryStore(events_path=events_file)
    manager = SessionManager(store)
    return manager


def test_topic_tokens_extraction():
    tokens = extract_topic_tokens("what is the best Japanese beginner roadmap")
    assert "japanese" in tokens
    assert "beginner" in tokens
    assert "roadmap" in tokens
    assert "what" not in tokens
    assert "the" not in tokens


def test_session_continuity_and_reformulation(session_fixture):
    sid = "sess-test-123"
    ev1 = QuerySessionEvent(
        session_id=sid,
        event_type="query_submitted",
        query="what is hydration",
    )
    session_fixture.record_session_event(ev1)

    ev2 = QuerySessionEvent(
        session_id=sid,
        event_type="query_submitted",
        query="why hydration errors happen",
    )
    session_fixture.record_session_event(ev2)

    # ev2 should automatically record previous_query as 'what is hydration'
    assert ev2.previous_query == "what is hydration"

    ctx = session_fixture.get_session_context(sid)
    assert ctx["last_query"] == "why hydration errors happen"
    assert "hydration" in ctx["active_topic_keywords"]


def test_session_context_bonus(session_fixture):
    sid = "sess-test-jp"
    session_fixture.record_session_event(QuerySessionEvent(
        session_id=sid,
        event_type="query_submitted",
        query="what is japanese",
    ))

    # Candidate related to Japanese should receive bonus
    bonus, reason = session_fixture.compute_session_context_bonus(
        "Japanese Beginner Roadmap",
        session_id=sid,
    )
    assert bonus > 0.0
    assert "japanese" in reason.lower()

    # Candidate completely unrelated should receive 0 bonus
    bonus_unrelated, _ = session_fixture.compute_session_context_bonus(
        "Bicycle Maintenance Notes",
        session_id=sid,
    )
    assert bonus_unrelated == 0.0
