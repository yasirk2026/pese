"""
PESE Discovery: Synthetic Behavioural History Fixture
Generates deterministic synthetic query sessions, clicks, and reformulation chains
for evaluation and warm-state testing without exposing real user data.
"""

from typing import List
from ..discovery.models import QuerySessionEvent
from ..discovery.history import SearchHistoryStore


SYNTHETIC_EVENTS: List[dict] = [
    # Session 1: Japanese Learning Intent & Repeated Success
    {
        "session_id": "synth-sess-jp-01",
        "event_type": "query_submitted",
        "query": "what should I learn next in japanese",
        "effective_query": "what should I learn next in japanese",
        "timestamp": "2026-10-20T10:00:00Z",
    },
    {
        "session_id": "synth-sess-jp-01",
        "event_type": "result_clicked",
        "query": "what should I learn next in japanese",
        "target_slug": "what-i-should-learn-next-in-japanese",
        "rank_position": 1,
        "timestamp": "2026-10-20T10:00:15Z",
    },
    {
        "session_id": "synth-sess-jp-02",
        "event_type": "query_submitted",
        "query": "what should I learn next in japanese",
        "effective_query": "what should I learn next in japanese",
        "timestamp": "2026-10-20T14:30:00Z",
    },
    {
        "session_id": "synth-sess-jp-02",
        "event_type": "result_clicked",
        "query": "what should I learn next in japanese",
        "target_slug": "what-i-should-learn-next-in-japanese",
        "rank_position": 1,
        "timestamp": "2026-10-20T14:30:20Z",
    },
    {
        "session_id": "synth-sess-jp-03",
        "event_type": "query_submitted",
        "query": "what should I learn next in japanese",
        "effective_query": "what should I learn next in japanese",
        "timestamp": "2026-10-21T09:15:00Z",
    },
    {
        "session_id": "synth-sess-jp-03",
        "event_type": "result_clicked",
        "query": "what should I learn next in japanese",
        "target_slug": "what-i-should-learn-next-in-japanese",
        "rank_position": 1,
        "timestamp": "2026-10-21T09:15:30Z",
    },

    # Session 2: Hydration Reformulation Chain
    {
        "session_id": "synth-sess-hydr-01",
        "event_type": "query_submitted",
        "query": "what is hydration",
        "effective_query": "what is hydration",
        "timestamp": "2026-10-21T11:00:00Z",
    },
    {
        "session_id": "synth-sess-hydr-01",
        "event_type": "query_submitted",
        "query": "why hydration errors happen",
        "effective_query": "why hydration errors happen",
        "previous_query": "what is hydration",
        "timestamp": "2026-10-21T11:02:00Z",
    },
    {
        "session_id": "synth-sess-hydr-01",
        "event_type": "query_submitted",
        "query": "how to fix hydration mismatch",
        "effective_query": "how to fix hydration mismatch",
        "previous_query": "why hydration errors happen",
        "timestamp": "2026-10-21T11:05:00Z",
    },
    {
        "session_id": "synth-sess-hydr-01",
        "event_type": "result_clicked",
        "query": "how to fix hydration mismatch",
        "target_slug": "hydration-bugs-i-faced",
        "rank_position": 1,
        "timestamp": "2026-10-21T11:05:40Z",
    },

    # Session 3: Bicycle Purchase Searches
    {
        "session_id": "synth-sess-bike-01",
        "event_type": "query_submitted",
        "query": "when did I buy my bicycle",
        "effective_query": "when did I buy my bicycle",
        "timestamp": "2026-10-21T16:00:00Z",
    },
    {
        "session_id": "synth-sess-bike-01",
        "event_type": "result_clicked",
        "query": "when did I buy my bicycle",
        "target_slug": "my-bicycle-story",
        "rank_position": 1,
        "timestamp": "2026-10-21T16:00:18Z",
    },

    # Session 4: PESE Queries
    {
        "session_id": "synth-sess-pese-01",
        "event_type": "query_submitted",
        "query": "what is PESE",
        "effective_query": "what is PESE",
        "timestamp": "2026-10-21T18:00:00Z",
    },
    {
        "session_id": "synth-sess-pese-01",
        "event_type": "result_clicked",
        "query": "what is PESE",
        "target_slug": "what-is-pese",
        "rank_position": 1,
        "timestamp": "2026-10-21T18:00:25Z",
    },
]


def load_synthetic_history(history_store: SearchHistoryStore) -> int:
    """Load synthetic behavioural history events into the provided store."""
    count = 0
    for item in SYNTHETIC_EVENTS:
        ev = QuerySessionEvent(**item)
        history_store.record_event(ev)
        count += 1
    return count
