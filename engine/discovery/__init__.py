"""
PESE Discovery Layer
Provides Autocomplete, Related Searches, 'You Might Also Ask',
and Query Session Intelligence for the Personal Evil Search Engine.
"""

from .models import (
    AutocompleteSuggestion,
    RelatedSearchItem,
    PAAQuestionItem,
    QuerySessionEvent,
    QueryFamily,
)
from .history import SearchHistoryStore, LocalHistoryStore
from .sessions import SessionManager, QuerySession
from .autocomplete import AutocompleteEngine
from .related_searches import RelatedSearchEngine
from .questions import PAAQuestionEngine

__all__ = [
    "AutocompleteSuggestion",
    "RelatedSearchItem",
    "PAAQuestionItem",
    "QuerySessionEvent",
    "QueryFamily",
    "SearchHistoryStore",
    "LocalHistoryStore",
    "SessionManager",
    "QuerySession",
    "AutocompleteEngine",
    "RelatedSearchEngine",
    "PAAQuestionEngine",
]
