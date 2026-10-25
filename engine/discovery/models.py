"""
PESE Discovery: Data Models
Defines Pydantic models for autocomplete suggestions, related searches,
'You Might Also Ask' (PAA) questions, sessions, and telemetry events.
"""

from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from ..brain.events import QuerySessionEvent


class AutocompleteSuggestion(BaseModel):
    """A ranked query suggestion surfaced as the user types."""
    text: str
    source: str = "corpus"  # 'corpus_title', 'corpus_heading', 'corpus_phrase', 'query_history', 'query_family'
    score: float
    match_type: str = "prefix"  # 'exact_prefix', 'word_prefix', 'typo_recovered', 'containment'
    corpus_support: float = 0.0
    historical_searches: int = 0
    recent_searches: int = 0
    successful_clicks: int = 0
    session_context_bonus: float = 0.0
    highlight_ranges: List[Tuple[int, int]] = Field(default_factory=list)
    debug_trace: Dict[str, Any] = Field(default_factory=dict)


class SuggestResponse(BaseModel):
    """Response payload for /api/suggest endpoint."""
    query: str
    effective_prefix: str
    has_typo_correction: bool = False
    corrected_prefix: Optional[str] = None
    suggestions: List[AutocompleteSuggestion]
    took_ms: float = 0.0


class RelatedSearchItem(BaseModel):
    """A topically related query surfaced on the SERP."""
    query: str
    score: float
    source: str = "topic_overlap"  # 'link_neighborhood', 'heading', 'topic_overlap', 'reformulation', 'query_family'
    co_occurrence_score: float = 0.0
    result_overlap_score: float = 0.0
    link_affinity_score: float = 0.0
    debug_trace: Dict[str, Any] = Field(default_factory=dict)


class RelatedSearchesResponse(BaseModel):
    """Response payload for /api/related endpoint."""
    query: str
    related_searches: List[RelatedSearchItem]
    took_ms: float = 0.0


class PAAQuestionItem(BaseModel):
    """A grounded 'You Might Also Ask' question item with its extracted answer."""
    question: str
    answer: str
    justification: str
    source_slug: str
    source_title: str
    confidence_score: float
    passage_score: float = 0.0
    answerability_status: str = "PASS"  # 'PASS' or 'SUPPRESSED'
    intent: str = "WHAT"
    debug_trace: Dict[str, Any] = Field(default_factory=dict)


class QuestionsResponse(BaseModel):
    """Response payload for /api/questions endpoint."""
    query: str
    questions: List[PAAQuestionItem]
    total_candidates_evaluated: int = 0
    total_passed_gate: int = 0
    took_ms: float = 0.0




class QueryFamily(BaseModel):
    """A cohesive conceptual topic family grouping seed queries and questions."""
    family_id: str
    topic_label: str
    canonical_slugs: List[str] = Field(default_factory=list)
    seed_questions: List[str] = Field(default_factory=list)
    related_queries: List[str] = Field(default_factory=list)
    topic_keywords: List[str] = Field(default_factory=list)
