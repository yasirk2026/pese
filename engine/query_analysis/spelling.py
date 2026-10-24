"""
PESE Query Analysis: Spelling & Typo Recovery
Corpus-aware, deterministic typo correction using Damerau-Levenshtein distance
with transposition support and conservative confidence scoring.
Zero LLMs, zero external dependencies.
"""

import math
from functools import lru_cache
from ..nlp.stemmer import stem_word
from typing import Dict, List, Tuple, Optional, Set, Any
from pydantic import BaseModel


def damerau_levenshtein_distance(s1: str, s2: str) -> Tuple[int, str]:
    """
    Compute Damerau-Levenshtein distance between s1 and s2,
    supporting insertions, deletions, substitutions, and adjacent transpositions.
    Returns (distance, primary_edit_type).
    """
    len1, len2 = len(s1), len(s2)
    if s1 == s2:
        return 0, "exact"
    if len1 == 0:
        return len2, "insertion"
    if len2 == 0:
        return len1, "deletion"

    # 2D table
    d = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    for i in range(len1 + 1):
        d[i][0] = i
    for j in range(len2 + 1):
        d[0][j] = j

    transposition_detected = False

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            d[i][j] = min(
                d[i - 1][j] + 1,       # deletion
                d[i][j - 1] + 1,       # insertion
                d[i - 1][j - 1] + cost  # substitution
            )

            # Check transposition
            if i > 1 and j > 1 and s1[i - 1] == s2[j - 2] and s1[i - 2] == s2[j - 1]:
                if d[i - 2][j - 2] + cost < d[i][j]:
                    d[i][j] = d[i - 2][j - 2] + cost
                    transposition_detected = True

    dist = d[len1][len2]

    # Determine primary edit type
    if dist == 1:
        if transposition_detected and len1 == len2:
            edit_type = "transposition"
        elif len1 > len2:
            edit_type = "deletion"
        elif len1 < len2:
            edit_type = "insertion"
        else:
            edit_type = "substitution"
    elif dist == 2:
        edit_type = "transposition" if transposition_detected else "multi_edit"
    else:
        edit_type = "multi_edit"

    return dist, edit_type


class TypoCorrection(BaseModel):
    original_token: str
    corrected_token: str
    edit_distance: int
    edit_type: str
    confidence: float
    corpus_frequency: int


class CorpusSpellingCorrector:
    """
    Corpus-aware spelling corrector built directly from the indexed document vocabulary.
    Strictly avoids aggressive false corrections for technical terms and unknown entities.
    """

    def __init__(self):
        # token -> total collection frequency
        self.vocab_frequencies: Dict[str, int] = {}
        # token -> document frequency
        self.vocab_df: Dict[str, int] = {}
        # protected tokens that should never be altered (acronyms, stop words, etc.)
        self.protected_tokens: Set[str] = set()
        self.known_stems: Set[str] = set()

    def build_vocabulary(
        self,
        index_terms: Dict[str, Any],
        raw_terms: Optional[Dict[str, int]] = None,
        protected_words: Set[str] = None,
    ):
        """
        Build spelling dictionary from inverted index.
        If raw_terms (unstemmed author tokens) is provided, prioritize natural vocabulary
        over stemmed index entries so user-facing corrections are real words.
        """
        self.vocab_frequencies.clear()
        self.correct_token.cache_clear()
        self.vocab_df.clear()
        self.protected_tokens = set(protected_words or [])

        if raw_terms:
            for term, cf in raw_terms.items():
                clean_term = term.lower().strip()
                if len(clean_term) < 2:
                    continue
                self.vocab_frequencies[clean_term] = cf
                self.vocab_df[clean_term] = max(1, len(index_terms.get(clean_term, {})))
        else:
            for term, postings in index_terms.items():
                clean_term = term.lower().strip()
                if len(clean_term) < 2:
                    continue

                df = len(postings)
                cf = sum(p.total_tf() if hasattr(p, "total_tf") else 1 for p in postings.values())

                self.vocab_df[clean_term] = max(self.vocab_df.get(clean_term, 0), df)
                self.vocab_frequencies[clean_term] = max(self.vocab_frequencies.get(clean_term, 0), cf)
        self.known_stems = {stem_word(word) for word in self.vocab_frequencies}

    def is_known_token(self, token: str) -> bool:
        """True if the token already exists in the corpus dictionary."""
        return token.lower() in self.vocab_frequencies

    @lru_cache(maxsize=4096)
    def correct_token(self, token: str) -> Optional[TypoCorrection]:
        """
        Attempt to correct an unknown token against the corpus vocabulary.
        Returns TypoCorrection if confident candidate found, else None.
        """
        token_lower = token.lower()

        # 1. Protection rules
        if self.is_known_token(token_lower):
            return None
        if stem_word(token_lower) in self.known_stems:
            # A legitimate inflection is not an out-of-vocabulary typo.
            return None
        if token_lower in self.protected_tokens:
            return None
        if len(token_lower) <= 3:
            # Do not correct very short tokens (too ambiguous)
            return None
        if any(c.isdigit() for c in token_lower):
            # Do not correct tokens with digits (e.g. 2024, v2)
            return None

        # 2. Candidate Search
        best_candidate: Optional[str] = None
        best_dist = 999
        best_edit_type = ""
        best_confidence = 0.0
        best_cf = 0

        # Maximum allowable edit distance depends on token length
        max_allowed_dist = 1 if len(token_lower) <= 6 else 2

        for vocab_word, cf in self.vocab_frequencies.items():
            # Quick length filter before expensive edit distance
            if abs(len(vocab_word) - len(token_lower)) > max_allowed_dist:
                continue

            # First letter filter (allow only if transposition could be at start or distance 1)
            dist, edit_type = damerau_levenshtein_distance(token_lower, vocab_word)
            if dist > max_allowed_dist:
                continue

            # Compute candidate confidence
            if dist == 1:
                if edit_type == "transposition":
                    base_sim = 0.95
                elif edit_type == "substitution":
                    # Check common phonetic / adjacent pairs like y <-> i
                    if ("y" in token_lower and "i" in vocab_word) or ("i" in token_lower and "y" in vocab_word):
                        base_sim = 0.94
                    else:
                        base_sim = 0.90
                else:
                    base_sim = 0.91
            elif dist == 2:
                if edit_type == "transposition":
                    base_sim = 0.84
                elif ("y" in token_lower and "i" in vocab_word) or ("i" in token_lower and "y" in vocab_word):
                    # Vowel inversion/confusion (e.g. bycicle <-> bicycle)
                    base_sim = 0.83
                else:
                    base_sim = 0.75
            else:
                continue

            # Frequency scaling: more frequent corpus words are more plausible targets
            freq_factor = min(1.0, 0.75 + 0.08 * math.log(1 + cf))
            # Length penalty: words shorter than 5 characters have higher false-positive risk
            len_factor = min(1.0, len(vocab_word) / 5.0)

            confidence = round(base_sim * freq_factor * len_factor, 4)

            # Strictly prioritize lower edit distance; use confidence to break ties
            is_better = False
            if confidence >= 0.78:
                if dist < best_dist:
                    is_better = True
                elif dist == best_dist and confidence > best_confidence:
                    is_better = True

            if is_better:
                best_confidence = confidence
                best_candidate = vocab_word
                best_dist = dist
                best_edit_type = edit_type
                best_cf = cf

        # 3. Minimum Confidence Gate for Typo Application
        # High threshold (0.78) ensures conservative correction
        if best_candidate and best_confidence >= 0.78:
            return TypoCorrection(
                original_token=token,
                corrected_token=best_candidate,
                edit_distance=best_dist,
                edit_type=best_edit_type,
                confidence=best_confidence,
                corpus_frequency=best_cf,
            )

        return None
