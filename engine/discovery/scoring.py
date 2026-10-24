"""
PESE Discovery: Explainable Scoring Formulas
Implements transparent scoring mathematical models for Autocomplete,
Related Searches, and 'You Might Also Ask' ranking.
"""

import math
from typing import Dict, Any, Tuple


def calculate_autocomplete_score(
    prefix_match_type: str,     # 'exact_prefix', 'word_prefix', 'typo_recovered', 'containment'
    corpus_support: float,       # 0.0 to 3.0 (based on title/heading/tag matches)
    search_frequency: int,       # count of times searched in history
    recent_searches: int,        # count of searches in recent window
    successful_clicks: int,      # count of clicks on results from this query
    session_bonus: float,        # bounded session context bonus (0.0 to 2.5)
) -> Tuple[float, Dict[str, Any]]:
    """
    Compute explainable Autocomplete suggestion score.

    Formula:
        SuggestionScore = PrefixMatch + CorpusSupport + SearchFrequency
                        + SuccessfulInteractionBonus + RecencyBonus + SessionContextBonus
    """
    # 1. Prefix match quality component (range: 2.0 to 6.0)
    match_weights = {
        "exact_prefix": 6.0,
        "word_prefix": 4.5,
        "typo_recovered": 3.0,
        "containment": 2.0,
    }
    prefix_score = match_weights.get(prefix_match_type, 2.0)

    # 2. Corpus support (range: 0.0 to 3.0)
    corpus_score = round(max(0.0, min(3.0, corpus_support)), 2)

    # 3. Search frequency (logarithmic saturation, range: 0.0 to 3.5)
    freq_score = round(1.2 * math.log2(1.0 + search_frequency), 2)

    # 4. Successful interaction / click history (range: 0.0 to 4.0)
    interaction_score = round(1.5 * math.log2(1.0 + successful_clicks), 2)

    # 5. Recency bonus (range: 0.0 to 1.5)
    recency_score = round(min(1.5, 0.5 * recent_searches), 2)

    # 6. Session context bonus (range: 0.0 to 2.5)
    session_score = round(max(0.0, min(2.5, session_bonus)), 2)

    final_score = round(
        prefix_score
        + corpus_score
        + freq_score
        + interaction_score
        + recency_score
        + session_score,
        2
    )

    trace = {
        "prefix_match_score": prefix_score,
        "prefix_match_type": prefix_match_type,
        "corpus_support_score": corpus_score,
        "search_frequency_score": freq_score,
        "historical_frequency": search_frequency,
        "interaction_bonus": interaction_score,
        "successful_clicks": successful_clicks,
        "recency_bonus": recency_score,
        "recent_searches": recent_searches,
        "session_context_bonus": session_score,
        "final_suggestion_score": final_score,
    }

    return final_score, trace


def calculate_related_search_score(
    topic_overlap: float,        # 0.0 to 5.0 based on shared stems/terms
    link_affinity: float,        # 0.0 to 3.0 based on graph distance
    result_overlap: float,       # 0.0 to 3.0 based on shared top documents
    reformulation_freq: int,     # count of transitions in session history
) -> Tuple[float, Dict[str, Any]]:
    """
    Compute explainable Related Searches score.

    Formula:
        RelatedScore = TopicOverlap + LinkAffinity + ResultOverlap + ReformulationBonus
    """
    # 1. Topic overlap (range: 0.0 to 5.0)
    topic_score = round(max(0.0, min(5.0, topic_overlap)), 2)

    # 2. Graph link neighborhood affinity (range: 0.0 to 3.0)
    link_score = round(max(0.0, min(3.0, link_affinity)), 2)

    # 3. Destination / result-set overlap (range: 0.0 to 3.0)
    result_score = round(max(0.0, min(3.0, result_overlap)), 2)

    # 4. Historical query reformulation strength (range: 0.0 to 3.0)
    reform_score = round(min(3.0, 1.2 * math.log2(1.0 + reformulation_freq)), 2)

    final_score = round(topic_score + link_score + result_score + reform_score, 2)

    trace = {
        "topic_overlap_score": topic_score,
        "link_affinity_score": link_score,
        "result_overlap_score": result_score,
        "reformulation_score": reform_score,
        "reformulation_frequency": reformulation_freq,
        "final_related_score": final_score,
    }

    return final_score, trace


def calculate_paa_score(
    relatedness: float,           # 0.0 to 6.0 (query term & topic match)
    answer_confidence: float,     # 0.0 to 10.0 (from passage score & answer extractor)
    source_authority: float,      # 0.0 to 3.0 (from link authority / doc score)
) -> Tuple[float, Dict[str, Any]]:
    """
    Compute explainable 'You Might Also Ask' score.
    High answer confidence is heavily favored over speculative queries.
    """
    rel_score = round(max(0.0, min(6.0, relatedness)), 2)
    ans_score = round(max(0.0, min(10.0, answer_confidence)), 2)
    auth_score = round(max(0.0, min(3.0, source_authority)), 2)

    # Answer confidence has highest weighting
    final_score = round((1.2 * rel_score) + (1.8 * ans_score) + (0.5 * auth_score), 2)

    trace = {
        "relatedness_score": rel_score,
        "answer_confidence_score": ans_score,
        "source_authority_score": auth_score,
        "final_paa_score": final_score,
    }

    return final_score, trace
