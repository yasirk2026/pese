"""
PESE Query Analysis: Master Analyzer
Integrates normalization, lexical role classification (content vs intent vs grammatical),
corpus-aware spelling correction, and effective query generation.
"""

from typing import List, Dict, Optional, Set, Any
from pydantic import BaseModel, Field
from .intent import QueryIntent, classify_query_intent
from .spelling import CorpusSpellingCorrector, TypoCorrection
from ..nlp.normalizer import normalize_text
from ..nlp.tokenizer import tokenize, extract_quoted_phrases
from ..nlp.stopwords import INTENT_WORDS, GENERIC_STOPWORDS
from ..nlp.stemmer import stem_word


class AnalyzedQuery(BaseModel):
    """Rich, auditable query representation produced by the Query Analysis layer."""
    original_query: str
    normalized_query: str
    effective_query: str
    intent: QueryIntent
    intent_reason: str

    # Lexical term classification
    raw_tokens: List[str]
    content_terms: List[str]       # High-information topical tokens
    intent_terms: List[str]        # Question intent words (when, what, why, etc.)
    grammatical_terms: List[str]   # Stopwords and syntactic glue

    # Typo correction
    corrections: List[TypoCorrection] = Field(default_factory=list)
    has_corrections: bool = False
    correction_confidence: str = "NONE"  # "NONE" | "HIGH" | "MEDIUM" | "LOW"

    # Effective retrieval tokens & stems
    effective_content_terms: List[str] = Field(default_factory=list)
    effective_stems: List[str] = Field(default_factory=list)
    quoted_phrases: List[str] = Field(default_factory=list)

    def summary_lines(self) -> List[str]:
        lines = [
            f"Original query: {self.original_query}",
            f"Normalized query: {self.normalized_query}",
            f"Detected intent: {self.intent.value} ({self.intent_reason})",
            f"Content terms: {', '.join(self.content_terms) if self.content_terms else '[None]'}",
            f"Intent terms: {', '.join(self.intent_terms) if self.intent_terms else '[None]'}",
        ]
        if self.corrections:
            corr_strs = [f"{c.original_token} -> {c.corrected_token} ({c.confidence:.2f}, {c.edit_type})" for c in self.corrections]
            lines.append(f"Corrections: {'; '.join(corr_strs)}")
            lines.append(f"Effective query: {self.effective_query}")
            lines.append(f"Correction confidence: {self.correction_confidence}")
        else:
            lines.append("Corrections: None (all tokens recognized or conservative)")
            lines.append(f"Effective query: {self.effective_query}")
        return lines


class QueryAnalyzer:
    """Performs end-to-end query analysis prior to candidate retrieval."""

    def __init__(self, spelling_corrector: CorpusSpellingCorrector):
        self.spelling_corrector = spelling_corrector

    def analyze_query(self, raw_query: str, force_raw: bool = False) -> AnalyzedQuery:
        """
        Analyze and classify query into content, intent, and grammatical tokens.
        Applies corpus-aware typo correction to content terms unless force_raw is True.
        """
        # 1. Quoted phrases & normalization
        cleaned_raw, quoted_phrases = extract_quoted_phrases(raw_query)
        normalized = normalize_text(cleaned_raw)
        raw_tokens = tokenize(normalized)

        # 2. Intent classification
        intent, intent_reason = classify_query_intent(raw_tokens, raw_query)

        # 3. Lexical role classification
        content_terms: List[str] = []
        intent_terms: List[str] = []
        grammatical_terms: List[str] = []

        for tok in raw_tokens:
            tok_lower = tok.lower()
            if tok_lower in INTENT_WORDS:
                intent_terms.append(tok_lower)
            elif tok_lower in GENERIC_STOPWORDS:
                grammatical_terms.append(tok_lower)
            else:
                content_terms.append(tok_lower)

        # 4. Typo detection & correction (unless user forced raw query)
        corrections: List[TypoCorrection] = []
        effective_tokens = list(raw_tokens)
        effective_content_terms: List[str] = []

        if not force_raw:
            for idx, tok in enumerate(raw_tokens):
                tok_lower = tok.lower()
                # Only attempt correction on content terms (not on intent words or stopwords)
                if tok_lower in content_terms:
                    correction = self.spelling_corrector.correct_token(tok_lower)
                    if correction:
                        corrections.append(correction)
                        effective_tokens[idx] = correction.corrected_token
                        effective_content_terms.append(correction.corrected_token)
                    else:
                        effective_content_terms.append(tok_lower)
                elif tok_lower in intent_terms:
                    pass
                else:
                    pass
        else:
            effective_content_terms = list(content_terms)

        # 5. Effective Query string
        if corrections:
            effective_query = " ".join(effective_tokens)
            has_corrections = True
            # Compute confidence
            min_conf = min(c.confidence for c in corrections)
            if min_conf >= 0.88:
                correction_confidence = "HIGH"
            elif min_conf >= 0.78:
                correction_confidence = "MEDIUM"
            else:
                correction_confidence = "LOW"
        else:
            effective_query = raw_query.strip()
            has_corrections = False
            correction_confidence = "NONE"

        # 6. Effective Stems for retrieval
        effective_stems = [stem_word(t) for t in effective_content_terms]

        return AnalyzedQuery(
            original_query=raw_query,
            normalized_query=normalized,
            effective_query=effective_query,
            intent=intent,
            intent_reason=intent_reason,
            raw_tokens=raw_tokens,
            content_terms=content_terms,
            intent_terms=intent_terms,
            grammatical_terms=grammatical_terms,
            corrections=corrections,
            has_corrections=has_corrections,
            correction_confidence=correction_confidence,
            effective_content_terms=effective_content_terms,
            effective_stems=effective_stems,
            quoted_phrases=quoted_phrases,
        )
