"""
Unit tests for PESE Generalized Featured Answer Extractor.
Tests temporal specificity (preferring '17 March 2024' over '2024'),
definitional WHAT sentence extraction, and confidence gating.
"""

import pytest
from engine.passages.answer_extractor import (
    FeaturedAnswerExtractor,
    extract_best_temporal_answer,
)
from engine.query_analysis.analyzer import AnalyzedQuery
from engine.query_analysis.intent import QueryIntent


def test_temporal_specificity_ranking():
    # Text with both a year and a full specific date
    text = "In 2024 I started cycling. On 17 March 2024, I purchased my first commuter bicycle."
    best = extract_best_temporal_answer(text)
    assert best == "17 March 2024"

    # Text with only a month + year
    text2 = "I bought my bicycle in March 2024 after moving."
    best2 = extract_best_temporal_answer(text2)
    assert best2 == "March 2024"

    # Text with only a standalone year
    text3 = "The project was launched back in 2023."
    best3 = extract_best_temporal_answer(text3)
    assert best3 == "2023"


def test_when_intent_featured_answer():
    extractor = FeaturedAnswerExtractor()
    query = AnalyzedQuery(
        original_query="when did I buy my bicycle",
        normalized_query="when did I buy my bicycle",
        effective_query="when did I buy my bicycle",
        intent=QueryIntent.WHEN,
        intent_reason="Direct temporal query",
        raw_tokens=["when", "did", "i", "buy", "my", "bicycle"],
        content_terms=["buy", "bicycle"],
        intent_terms=["when"],
        grammatical_terms=["did", "i", "my"],
        effective_content_terms=["buy", "bicycle"],
    )

    passage = "On 17 March 2024, I walked into the local shop and bought my commuter bicycle."
    answer, reason = extractor.extract_answer(
        passage_text=passage,
        analyzed_query=query,
        passage_score=10.5,
        document_score=18.0,
    )
    assert answer == "17 March 2024"
    assert "specificity" in reason


def test_what_intent_declarative_answer():
    extractor = FeaturedAnswerExtractor()
    query = AnalyzedQuery(
        original_query="what search cannot rank",
        normalized_query="what search cannot rank",
        effective_query="what search cannot rank",
        intent=QueryIntent.WHAT,
        intent_reason="Definitional WHAT query",
        raw_tokens=["what", "search", "cannot", "rank"],
        content_terms=["search", "cannot", "rank"],
        intent_terms=["what"],
        grammatical_terms=[],
        effective_content_terms=["search", "cannot", "rank"],
    )

    passage = "Search engines cannot rank what they cannot discover, parse, and index cleanly. Technical crawlability is the fundamental prerequisite."
    answer, reason = extractor.extract_answer(
        passage_text=passage,
        analyzed_query=query,
        passage_score=12.0,
        document_score=20.0,
    )
    assert answer == "Search engines cannot rank what they cannot discover, parse, and index cleanly."


def test_answer_suppression_low_confidence():
    extractor = FeaturedAnswerExtractor()
    query = AnalyzedQuery(
        original_query="when did I buy my bicycle",
        normalized_query="when did I buy my bicycle",
        effective_query="when did I buy my bicycle",
        intent=QueryIntent.WHEN,
        intent_reason="Direct temporal query",
        raw_tokens=["when", "did", "i", "buy", "my", "bicycle"],
        content_terms=["buy", "bicycle"],
        intent_terms=["when"],
        grammatical_terms=["did", "i", "my"],
        effective_content_terms=["buy", "bicycle"],
    )

    passage = "On 17 March 2024, I bought my bicycle."
    # Scores below confidence thresholds (doc < 12.0 or passage < 6.0)
    answer, reason = extractor.extract_answer(
        passage_text=passage,
        analyzed_query=query,
        passage_score=3.0,
        document_score=8.0,
    )
    assert answer is None
    assert "Suppressed" in reason
