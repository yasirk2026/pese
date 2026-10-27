"""
PESE Search Sync: Subsystem Package
Phase N3-A: User-to-Search Feedback Loop Genesis
"""

from .contracts import (
    FeedbackType,
    TargetType,
    FeedbackReason,
    FeedbackSubmission,
    FeedbackEvent,
    SearchSyncPreferenceAdjustment,
    NeuralShadowObservation,
    SearchResultNeuralSummary,
    classify_diagnostic_alignment,
)
import os as _os
# Inference workers must never initialize a feedback store or resolve a Brain.
# The desktop/research public API retains its existing imports and behavior.
if _os.getenv("PESE_REL_SHADOW_WORKER") != "1":
    from .feedback_store import SearchSyncFeedbackStore, feedback_store
    from .preference_signal import (
        SearchSyncPreferenceSignal,
        preference_signal,
        normalize_sync_query,
        DEFAULT_DISLIKE_PENALTY,
        DEFAULT_LIKE_BONUS,
    )
    from .neural_shadow import PESERelationShadowAdapter, shadow_adapter

__all__ = [
    "FeedbackType",
    "TargetType",
    "FeedbackReason",
    "FeedbackSubmission",
    "FeedbackEvent",
    "SearchSyncPreferenceAdjustment",
    "NeuralShadowObservation",
    "SearchResultNeuralSummary",
    "classify_diagnostic_alignment",
    "SearchSyncFeedbackStore",
    "feedback_store",
    "SearchSyncPreferenceSignal",
    "preference_signal",
    "normalize_sync_query",
    "DEFAULT_DISLIKE_PENALTY",
    "DEFAULT_LIKE_BONUS",
    "PESERelationShadowAdapter",
    "shadow_adapter",
]
