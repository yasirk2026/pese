"""
PESE Passages package: Passage extraction, passage scoring, snippet generation, and generalized answer extraction.
"""

from .extractor import PassageExtractor
from .scorer import PassageScorer
from .highlighter import SnippetGenerator, highlight_terms
from .answer_extractor import FeaturedAnswerExtractor, extract_best_temporal_answer

__all__ = [
    "PassageExtractor",
    "PassageScorer",
    "SnippetGenerator",
    "highlight_terms",
    "FeaturedAnswerExtractor",
    "extract_best_temporal_answer",
]
