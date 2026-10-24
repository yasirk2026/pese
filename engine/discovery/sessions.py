"""
PESE Discovery: Query Session Intelligence
Maintains search session continuity, detects query reformulations,
tracks user discovery events, and computes bounded session context signals.
"""

import time
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from .models import QuerySessionEvent
from .history import SearchHistoryStore, LocalHistoryStore


def extract_topic_tokens(query: str) -> Set[str]:
    """Extract informative lowercase unigrams from query, filtering small punctuation."""
    tokens = re.findall(r'[a-zA-Z0-9_\-]+', query.lower())
    stopwords = {
        "what", "is", "are", "the", "a", "an", "in", "of", "to", "for", "and",
        "on", "at", "by", "with", "how", "why", "when", "who", "where", "did",
        "i", "my", "me", "do", "does", "can", "should", "from"
    }
    return {t for t in tokens if len(t) > 2 and t not in stopwords}


class QuerySession:
    """Represents a coherent search session for a user."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.events: List[QuerySessionEvent] = []
        self.recent_queries: List[str] = []
        self.active_topic_keywords: Set[str] = set()
        self.last_active_time = time.time()

    def add_event(self, event: QuerySessionEvent) -> None:
        self.events.append(event)
        self.last_active_time = time.time()

        if event.event_type == "query_submitted" and event.query:
            clean_q = event.query.strip().lower()
            if not self.recent_queries or self.recent_queries[-1] != clean_q:
                self.recent_queries.append(clean_q)
                if len(self.recent_queries) > 10:
                    self.recent_queries.pop(0)

            # Update active topic keywords with recency weighting
            new_tokens = extract_topic_tokens(clean_q)
            self.active_topic_keywords.update(new_tokens)

    def get_last_query(self) -> Optional[str]:
        return self.recent_queries[-1] if self.recent_queries else None

    def get_session_context(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "recent_queries": list(self.recent_queries),
            "last_query": self.get_last_query(),
            "active_topic_keywords": list(self.active_topic_keywords),
        }


class SessionManager:
    """Manages active query sessions, coordinates with history store, and logs discovery."""

    def __init__(self, history_store: Optional[SearchHistoryStore] = None):
        self.history_store = history_store or LocalHistoryStore()
        self.sessions: Dict[str, QuerySession] = {}

    def get_or_create_session(self, session_id: Optional[str] = None) -> QuerySession:
        sid = (session_id or "").strip()
        if not sid:
            sid = f"pese-session-{int(time.time() * 1000)}"

        if sid not in self.sessions:
            self.sessions[sid] = QuerySession(sid)
        return self.sessions[sid]

    def record_session_event(self, event: QuerySessionEvent) -> None:
        """Route event to in-memory session and persistent history store."""
        session = self.get_or_create_session(event.session_id)

        # Detect reformulation if previous query is not specified
        if event.event_type == "query_submitted" and event.query:
            last_q = session.get_last_query()
            if last_q and last_q != event.query.strip().lower():
                event.previous_query = last_q

        session.add_event(event)
        self.history_store.record_event(event)

    def get_session_context(self, session_id: Optional[str]) -> Dict[str, Any]:
        if not session_id or session_id not in self.sessions:
            return {
                "session_id": session_id or "",
                "recent_queries": [],
                "last_query": None,
                "active_topic_keywords": [],
            }
        return self.sessions[session_id].get_session_context()

    def compute_session_context_bonus(
        self,
        candidate_text: str,
        session_id: Optional[str],
        max_bonus: float = 2.5,
    ) -> Tuple[float, str]:
        """
        Compute a bounded session context bonus if candidate matches active session topic keywords.
        Returns (bonus_score, explanation).
        """
        if not session_id or session_id not in self.sessions:
            return 0.0, "No active session context"

        session = self.sessions[session_id]
        if not session.active_topic_keywords:
            return 0.0, "No active topic keywords in session"

        candidate_tokens = extract_topic_tokens(candidate_text)
        overlap = session.active_topic_keywords.intersection(candidate_tokens)

        if not overlap:
            return 0.0, "No topic overlap with session history"

        # Bounded bonus: 1.0 for single overlap, capped at max_bonus
        bonus = min(max_bonus, round(1.0 + 0.5 * (len(overlap) - 1), 2))
        return bonus, f"Matched session topic keywords ({', '.join(sorted(overlap))})"
