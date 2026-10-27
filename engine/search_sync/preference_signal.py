"""
PESE Search Sync: Preference Signal Calculator
Phase N3-A: Bounded Ranking Preference Adjustments

Translates active user feedback into bounded score adjustments for MAAE candidate ranking:
- DISLIKE: Bounded penalty (-4.0)
- LIKE: Bounded bonus (+2.0)
- NO FEEDBACK: 0.0 adjustment (100% identical to pre-N3-A baseline)

Enforces strict boundedness: preference adjustment ∈ [-6.0, +3.0].
"""

import re
from typing import Dict, List, Optional, Tuple, Any

from .contracts import (
    FeedbackType,
    TargetType,
    FeedbackEvent,
    SearchSyncPreferenceAdjustment,
)
from .feedback_store import SearchSyncFeedbackStore, feedback_store as global_store
from ..nlp.normalizer import normalize_text


# Bounded preference constants
DEFAULT_DISLIKE_PENALTY = -4.0000
DEFAULT_LIKE_BONUS = +2.0000
MIN_ADJUSTMENT_BOUND = -6.0000
MAX_ADJUSTMENT_BOUND = +3.0000


def normalize_sync_query(query: str) -> str:
    """
    Standard query normalization for Search Sync preference keys:
    1. Reuses PESE standard NLP normalization (unicode fold, lowercase, contraction expansion).
    2. Strips trailing question marks and sentence punctuation.
    3. Collapses multiple whitespace.
    """
    if not query:
        return ""
    norm = normalize_text(query, expand=True)
    norm = re.sub(r"[?!.,;:]+$", "", norm).strip()
    return norm


class SearchSyncPreferenceSignal:
    """
    Computes bounded preference adjustments from stored user feedback.
    Isolated from direct database writes; reads active preferences efficiently.
    """

    def __init__(
        self,
        store: Optional[SearchSyncFeedbackStore] = None,
        dislike_penalty: float = DEFAULT_DISLIKE_PENALTY,
        like_bonus: float = DEFAULT_LIKE_BONUS,
    ):
        self.store = store or global_store
        self.dislike_penalty = max(MIN_ADJUSTMENT_BOUND, min(0.0, dislike_penalty))
        self.like_bonus = min(MAX_ADJUSTMENT_BOUND, max(0.0, like_bonus))

    def normalize_query(self, query: str) -> str:
        """Returns the canonical normalized query key."""
        return normalize_sync_query(query)

    def get_query_active_preferences(
        self,
        normalized_query: str,
        target_type: Optional[TargetType] = TargetType.SERP_RESULT,
    ) -> Dict[str, FeedbackEvent]:
        """Fetches all active preferences for this normalized query in one batch."""
        if not self.learning_enabled():
            return {}
        return self.store.get_active_preferences_for_query(normalized_query, target_type=target_type)

    def learning_enabled(self):
        from ..intelligence.settings import SettingsStore
        return SettingsStore(self.store.db_path.parent).read().learn_from_feedback

    def calculate_adjustment(
        self,
        feedback_event: Optional[FeedbackEvent]
    ) -> Tuple[float, Optional[str]]:
        """
        Calculates bounded numerical adjustment from feedback event.
        Returns: (adjustment_score, feedback_str)
        """
        if feedback_event is None:
            return 0.0, None

        if feedback_event.feedback == FeedbackType.DISLIKE:
            adj = self.dislike_penalty
            # Clamp strictly to bounds
            adj = max(MIN_ADJUSTMENT_BOUND, min(0.0, adj))
            return adj, FeedbackType.DISLIKE.value

        if feedback_event.feedback == FeedbackType.LIKE:
            adj = self.like_bonus
            adj = min(MAX_ADJUSTMENT_BOUND, max(0.0, adj))
            return adj, FeedbackType.LIKE.value

        return 0.0, None

    def get_preference_adjustment(
        self,
        normalized_query: str,
        target_id: str,
        target_slug: Optional[str] = None,
        active_map: Optional[Dict[str, FeedbackEvent]] = None,
        target_type: TargetType = TargetType.SERP_RESULT,
    ) -> SearchSyncPreferenceAdjustment:
        """
        Retrieves preference adjustment for a specific query-target pair.
        Supports optional pre-fetched active_map for batch efficiency.
        """
        if active_map is None:
            if not self.learning_enabled():
                return SearchSyncPreferenceAdjustment(normalized_query=normalized_query, target_id=target_id,
                                                      target_type=target_type)
            active_map = self.store.get_active_preferences_for_query(normalized_query, target_type=target_type)

        # Look up by target_id or target_slug
        event = active_map.get(target_id)
        if not event and target_slug:
            event = active_map.get(target_slug)

        if event and event.target_type != target_type:
            event = None

        adj, fb_str = self.calculate_adjustment(event)

        return SearchSyncPreferenceAdjustment(
            normalized_query=normalized_query,
            target_id=target_id,
            target_type=target_type,
            feedback=FeedbackType(fb_str) if fb_str else None,
            adjustment=round(adj, 4),
            reason=event.reason if event else None,
            applied=bool(event is not None and adj != 0.0),
        )

    def check_featured_answer_suppression(
        self,
        normalized_query: str,
        doc_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[FeedbackEvent]]:
        """
        Checks if the Featured Answer should be suppressed for this query.
        Returns (is_suppressed, feedback_event).
        """
        if not self.learning_enabled():
            return False, None
        event = self.store.get_featured_answer_preference(normalized_query, target_id=doc_id)
        if event and event.feedback == FeedbackType.DISLIKE:
            return True, event
        return False, None


# Global preference signal instance
preference_signal = SearchSyncPreferenceSignal()
