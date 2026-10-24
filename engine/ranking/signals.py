"""
PESE Ranking: Signals
Calculates individual explainable ranking signals for a candidate document against a query.
"""

from datetime import datetime, timezone
import math
from typing import Dict, Any, List
from ..indexing.document import Document
from ..nlp.tokenizer import QueryRepresentation, tokenize
from ..nlp.stemmer import stem_word


def calculate_freshness_signal(doc_meta: dict, now_dt: datetime = None) -> Dict[str, Any]:
    """
    Calculate bounded freshness signal based on updated_at or created_at timestamp.
    Signal value in [0.0, 0.8].
    """
    now = now_dt or datetime.now(timezone.utc)
    updated_str = doc_meta.get("updated_at") or doc_meta.get("created_at")

    if not updated_str:
        return {"freshness_score": 0.2, "days_old": 999, "explanation": "No timestamp found"}

    try:
        # Handle ISO format
        dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff_seconds = max(0.0, (now - dt).total_seconds())
        days_old = diff_seconds / 86400.0

        # Half-life of 180 days, bounded at max 0.80
        score = 0.80 / (1.0 + (days_old / 180.0))
        return {
            "freshness_score": round(score, 4),
            "days_old": round(days_old, 1),
            "explanation": f"Updated {round(days_old, 1)} days ago"
        }
    except Exception:
        return {"freshness_score": 0.2, "days_old": 999, "explanation": "Failed to parse date"}


def calculate_phrase_signal(doc_content: str, doc_title: str, query_rep: QueryRepresentation) -> Dict[str, Any]:
    """
    Check for exact matches of multi-word query phrases in title or content.
    """
    title_lower = doc_title.lower()
    content_lower = doc_content.lower()
    matched_phrases = []
    phrase_score = 0.0

    for phrase in query_rep.phrases:
        p_lower = phrase.lower()
        if p_lower in title_lower:
            matched_phrases.append(f"Title: '{phrase}'")
            phrase_score += 4.0
        elif p_lower in content_lower:
            matched_phrases.append(f"Body: '{phrase}'")
            phrase_score += 2.0

    return {
        "phrase_score": phrase_score,
        "matched_phrases": matched_phrases,
    }


def calculate_title_signal(doc_title: str, query_rep: QueryRepresentation) -> Dict[str, Any]:
    """Calculate explicit title token & stem alignment."""
    title_tokens = tokenize(doc_title)
    title_stems = [stem_word(t) for t in title_tokens]

    matched_title_terms = []
    for term in query_rep.filtered_tokens:
        stem = stem_word(term)
        if term in title_tokens or stem in title_stems:
            matched_title_terms.append(term)

    score = len(matched_title_terms) * 1.5
    return {
        "title_signal": score,
        "matched_title_terms": matched_title_terms,
    }


def calculate_heading_signal(headings: List[str], query_rep: QueryRepresentation) -> Dict[str, Any]:
    """Calculate query alignment across section headings."""
    heading_text = " ".join(headings)
    heading_tokens = tokenize(heading_text)
    heading_stems = [stem_word(t) for t in heading_tokens]

    matched = []
    for term in query_rep.filtered_tokens:
        stem = stem_word(term)
        if term in heading_tokens or stem in heading_stems:
            matched.append(term)

    score = len(matched) * 1.2
    return {
        "heading_signal": score,
        "matched_heading_terms": matched,
    }


def calculate_keyword_signal(keywords: List[str], query_rep: QueryRepresentation) -> Dict[str, Any]:
    """Calculate query alignment with authored tags/keywords."""
    kw_text = " ".join(keywords)
    kw_tokens = tokenize(kw_text)
    kw_stems = [stem_word(t) for t in kw_tokens]

    matched = []
    for term in query_rep.filtered_tokens:
        stem = stem_word(term)
        if term in kw_tokens or stem in kw_stems:
            matched.append(term)

    score = len(matched) * 1.5
    return {
        "keyword_signal": score,
        "matched_keywords": matched,
    }
