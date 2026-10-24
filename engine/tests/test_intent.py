"""
Unit tests for PESE Intent Classification.
Tests classification of queries into WHEN, WHAT, WHY, HOW, WHO, WHERE, and GENERAL.
"""

import pytest
from engine.query_analysis.intent import classify_query_intent, QueryIntent
from engine.nlp.tokenizer import tokenize


def test_when_intent():
    tokens = tokenize("when did I buy my bicycle")
    intent, reason = classify_query_intent(tokens, "when did I buy my bicycle")
    assert intent == QueryIntent.WHEN

    tokens2 = tokenize("when buy bycycle")
    intent2, _ = classify_query_intent(tokens2, "when buy bycycle")
    assert intent2 == QueryIntent.WHEN


def test_what_intent():
    tokens = tokenize("what search cannot rank")
    intent, reason = classify_query_intent(tokens, "what search cannot rank")
    assert intent == QueryIntent.WHAT

    tokens2 = tokenize("what is hydration")
    intent2, _ = classify_query_intent(tokens2, "what is hydration")
    assert intent2 == QueryIntent.WHAT


def test_why_intent():
    tokens = tokenize("why hydration bug happen")
    intent, reason = classify_query_intent(tokens, "why hydration bug happen")
    assert intent == QueryIntent.WHY

    tokens2 = tokenize("why do ranking algorithms penalize keyword stuffing")
    intent2, _ = classify_query_intent(tokens2, "why do ranking algorithms penalize keyword stuffing")
    assert intent2 == QueryIntent.WHY


def test_how_intent():
    tokens = tokenize("how to clean and oil bicycle chain")
    intent, reason = classify_query_intent(tokens, "how to clean and oil bicycle chain")
    assert intent == QueryIntent.HOW

    tokens2 = tokenize("how do inverted indexes store posting lists")
    intent2, _ = classify_query_intent(tokens2, "how do inverted indexes store posting lists")
    assert intent2 == QueryIntent.HOW


def test_general_intent():
    tokens = tokenize("cycle")
    intent, _ = classify_query_intent(tokens, "cycle")
    assert intent == QueryIntent.GENERAL

    tokens2 = tokenize("BM25 scoring formula")
    intent2, _ = classify_query_intent(tokens2, "BM25 scoring formula")
    assert intent2 == QueryIntent.GENERAL
