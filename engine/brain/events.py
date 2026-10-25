"""Portable behavioral-event schema, without runtime storage imports."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class QuerySessionEvent(BaseModel):
    """Telemetry and interaction event for query session intelligence."""
    session_id: str
    event_type: str  # 'query_submitted', 'result_clicked', 'autocomplete_shown', 'autocomplete_selected', 'related_search_selected', 'paa_opened', 'paa_source_clicked', 'reformulated'
    query: Optional[str] = None
    effective_query: Optional[str] = None
    previous_query: Optional[str] = None
    target_slug: Optional[str] = None
    rank_position: Optional[int] = None
    prefix: Optional[str] = None
    suggestions_shown: Optional[List[str]] = None
    selected_suggestion: Optional[str] = None
    selection_position: Optional[int] = None
    paa_question: Optional[str] = None
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
