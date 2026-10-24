"""
PESE Ranking package: Multi-signal scoring, RankingTrace, explainability audit, and search orchestration.
"""

from .scorer import RankingEngine, RankingTrace, SearchResult
from .explain import compare_traces
from .signals import (
    calculate_freshness_signal,
    calculate_phrase_signal,
    calculate_title_signal,
    calculate_heading_signal,
    calculate_keyword_signal,
)

__all__ = [
    "RankingEngine",
    "RankingTrace",
    "SearchResult",
    "compare_traces",
    "calculate_freshness_signal",
    "calculate_phrase_signal",
    "calculate_title_signal",
    "calculate_heading_signal",
    "calculate_keyword_signal",
]
