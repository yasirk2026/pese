"""
Unit tests for PESE Search History Store Abstraction.
Verifies event persistence, recent searches extraction,
privacy toggle, and history clearing.
"""

import pytest
from engine.discovery.models import QuerySessionEvent
from engine.discovery.history import LocalHistoryStore


@pytest.fixture
def history_fixture(tmp_path):
    events_file = tmp_path / "test_hist_events.jsonl"
    settings_file = tmp_path / "test_privacy_settings.json"
    store = LocalHistoryStore(events_path=events_file, settings_path=settings_file)
    # Persistence tests explicitly opt in; demo runtime defaults remain private.
    store.set_history_enabled(True)
    return store


def test_record_and_retrieve_searches(history_fixture):
    ev1 = QuerySessionEvent(
        session_id="s1",
        event_type="query_submitted",
        query="first query",
    )
    ev2 = QuerySessionEvent(
        session_id="s1",
        event_type="query_submitted",
        query="second query",
    )
    history_fixture.record_event(ev1)
    history_fixture.record_event(ev2)

    recent = history_fixture.get_recent_searches(limit=5)
    assert len(recent) == 2
    # Reverse chronological: 'second query' first
    assert recent[0]["query"] == "second query"
    assert recent[1]["query"] == "first query"


def test_clear_history(history_fixture):
    history_fixture.record_event(QuerySessionEvent(
        session_id="s1",
        event_type="query_submitted",
        query="test query",
    ))
    assert len(history_fixture.get_recent_searches(limit=5)) == 1

    history_fixture.clear_history()
    assert len(history_fixture.get_recent_searches(limit=5)) == 0


def test_privacy_disabled_toggle(history_fixture):
    assert history_fixture.is_history_enabled() is True
    history_fixture.set_history_enabled(False)
    assert history_fixture.is_history_enabled() is False

    # Event recording should be ignored when disabled
    history_fixture.record_event(QuerySessionEvent(
        session_id="s1",
        event_type="query_submitted",
        query="private search",
    ))
    assert len(history_fixture.get_recent_searches(limit=5)) == 0
