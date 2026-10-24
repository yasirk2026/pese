"""
PESE Search Sync: Contracts & Schemas
Phase N3-A: User-to-Search Feedback Loop Genesis

Defines the core data contracts for capturing user preference evidence (LIKE / DISLIKE)
on organic SERP results and Featured Answers.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
    """Core binary user preference signal."""
    LIKE = "LIKE"
    DISLIKE = "DISLIKE"


class TargetType(str, Enum):
    """Classification of the SERP component receiving feedback."""
    SERP_RESULT = "SERP_RESULT"
    FEATURED_ANSWER = "FEATURED_ANSWER"


class FeedbackReason(str, Enum):
    """Optional non-blocking diagnostic reason for negative feedback."""
    WRONG_RESULT = "Wrong result"
    IRRELEVANT = "Irrelevant"
    OUTDATED = "Outdated"
    WRONG_SOURCE = "Wrong source"
    DIDNT_ANSWER = "Didn't answer my query"
    OTHER = "Other"


class FeedbackSubmission(BaseModel):
    """Incoming API payload for POST /api/search/feedback."""
    search_context_id: Optional[str] = Field(default=None, description="Request search_id that generated the SERP")
    query: str = Field(..., min_length=1, max_length=500, description="Raw query string as entered by the user")
    target_type: TargetType = Field(..., description="Target SERP component (SERP_RESULT or FEATURED_ANSWER)")
    target_id: str = Field(..., min_length=1, max_length=200, description="Canonical stable target identifier (doc_id, slug, or answer_id)")
    target_slug: Optional[str] = Field(default=None, description="Optional document slug if target_id is doc_id")
    rank_position: Optional[int] = Field(default=None, ge=1, le=100, description="Original 1-based rank position on the SERP")
    feedback: FeedbackType = Field(..., description="Binary user preference: LIKE or DISLIKE")
    reason: Optional[str] = Field(default=None, max_length=200, description="Optional qualitative reason for negative preference")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional client context metadata")


class FeedbackEvent(BaseModel):
    """Auditable, immutable feedback event record stored in Search Sync."""
    event_id: str = Field(default_factory=lambda: uuid4().hex, description="Globally unique feedback event identifier")
    query: str = Field(..., description="Original raw query text")
    normalized_query: str = Field(..., description="Canonically normalized query key")
    target_type: TargetType = Field(..., description="Target type")
    target_id: str = Field(..., description="Target stable identifier")
    target_slug: Optional[str] = Field(default=None, description="Target document slug")
    rank_position: Optional[int] = Field(default=None, description="1-based rank position on SERP")
    feedback: FeedbackType = Field(..., description="LIKE or DISLIKE")
    reason: Optional[str] = Field(default=None, description="Optional reason")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of feedback submission"
    )
    search_context_id: Optional[str] = Field(default=None, description="Search request UUID")
    maae_base_score: Optional[float] = Field(default=None, description="Original MAAE ranking score")
    search_sync_adjustment: Optional[float] = Field(default=None, description="Preference score adjustment applied")
    model_versions: Dict[str, str] = Field(default_factory=dict, description="Snapshot index and model versions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extension metadata")


class SearchSyncPreferenceAdjustment(BaseModel):
    """Computed preference signal returned by SearchSyncPreferenceSignal."""
    normalized_query: str
    target_id: str
    target_type: TargetType
    feedback: Optional[FeedbackType] = None
    adjustment: float = 0.0
    reason: Optional[str] = None
    applied: bool = False


# ==================== PHASE N3-B: NEURAL SHADOW BRIDGE CONTRACTS ====================

class NeuralShadowObservation(BaseModel):
    """
    Immutable observation record from PESE-Rel-0 watching real search candidates.
    Carries strictly ZERO ranking authority.
    """
    observation_id: str = Field(default_factory=lambda: uuid4().hex, description="Globally unique observation ID")
    search_context_id: str = Field(..., description="Request search_id that generated the SERP")
    model_id: str = Field(default="PESE-Rel-0", description="Registered model identifier")
    checkpoint_hash: str = Field(..., description="SHA-256 hash of the frozen checkpoint weights")
    query: str = Field(..., description="Original raw query")
    normalized_query: str = Field(..., description="Normalized query key")
    target_type: str = Field(default="SERP_RESULT", description="'SERP_RESULT' or 'FEATURED_ANSWER'")
    target_id: str = Field(..., description="Document ID or Featured Answer target ID")
    target_slug: Optional[str] = Field(default=None, description="Document slug")
    evidence_id: str = Field(..., description="Passage or sentence identifier (e.g. slug#p0)")
    evidence_summary: str = Field(default="", description="Snippet/summary of the evaluated evidence text")
    answers_probability: float = Field(..., description="Raw continuous P(ANSWERS) from relation cross-encoder")
    does_not_answer_probability: float = Field(..., description="Raw continuous P(DOES_NOT_ANSWER)")
    predicted_label: str = Field(..., description="'ANSWERS' or 'DOES_NOT_ANSWER' (diagnostic only)")
    threshold_used: float = Field(default=0.85, description="Diagnostic classification threshold (authority: NONE)")
    authority: str = Field(default="NONE", description="Explicit guarantee: strictly NONE")
    latency_ms: float = Field(default=0.0, description="Inference latency in milliseconds")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of observation"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic metadata")


class SearchResultNeuralSummary(BaseModel):
    """
    Consolidated neural shadow summary attached to a SearchResult for developer inspection.
    """
    answers_probability: Optional[float] = None
    does_not_answer_probability: Optional[float] = None
    predicted_label: Optional[str] = None
    best_evidence_id: Optional[str] = None
    evidence_count: int = 0
    authority: str = "NONE"
    status: str = "OK"  # "OK", "SHADOW_ERROR", "DISABLED", "SKIPPED"
    alignment: Optional[str] = None
    observations: List[NeuralShadowObservation] = Field(default_factory=list)


def classify_diagnostic_alignment(
    answers_prob: Optional[float],
    feedback: Optional[FeedbackType],
    diagnostic_threshold: float = 0.85,
) -> Optional[str]:
    """
    Classifies the diagnostic alignment between PESE-Rel-0 prediction and human preference.
    Neither signal is ground truth; this is strictly for developer inspection.
    """
    if answers_prob is None or feedback is None:
        return None

    if feedback == FeedbackType.DISLIKE:
        if answers_prob >= diagnostic_threshold:
            return "NEURAL HIGH / HUMAN DISLIKE"
        else:
            return "NEURAL LOW / HUMAN DISLIKE"
    elif feedback == FeedbackType.LIKE:
        if answers_prob >= 0.50:
            return "NEURAL HIGH / HUMAN LIKE"
        else:
            return "NEURAL LOW / HUMAN LIKE"

    return None
