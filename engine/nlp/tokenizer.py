"""
PESE NLP: Tokenizer
Field-aware tokenization, phrase extraction, n-gram generation, and query representation.
"""

import re
from typing import List, Dict, Tuple, Set
from .normalizer import normalize_text
from .stopwords import filter_stopwords, is_stopword
from .stemmer import stem_word


# Pattern matching alphanumeric words, compound terms (e.g., next.js), and numbers (2024)
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[\.\-_][a-z0-9]+)*", re.IGNORECASE)

# Pattern matching quoted phrases: "exact phrase"
QUOTED_PHRASE_PATTERN = re.compile(r'"([^"]+)"')


def extract_quoted_phrases(query: str) -> Tuple[str, List[str]]:
    """
    Extract quoted phrases from a search query.
    Returns (query_without_quotes, list_of_phrases).
    """
    phrases = []
    for match in QUOTED_PHRASE_PATTERN.finditer(query):
        phrase = match.group(1).strip()
        if phrase:
            phrases.append(normalize_text(phrase))

    cleaned_query = QUOTED_PHRASE_PATTERN.sub(" ", query)
    return clean_text(cleaned_query), phrases


def clean_text(text: str) -> str:
    """Basic clean of multiple spaces."""
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> List[str]:
    """
    Tokenize raw text into lowercase tokens.
    Handles alphanumeric tokens, numbers, and tech terms (e.g. next.js).
    """
    if not text:
        return []
    normalized = normalize_text(text)
    return TOKEN_PATTERN.findall(normalized)


def generate_ngrams(tokens: List[str], n: int = 2) -> List[str]:
    """Generate n-grams from a list of tokens."""
    if len(tokens) < n:
        return []
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def extract_phrases_from_tokens(tokens: List[str], min_len: int = 2, max_len: int = 3) -> List[str]:
    """Extract consecutive non-stopword bigrams and trigrams as phrase candidates."""
    phrases = []
    for n in range(min_len, min(max_len + 1, len(tokens) + 1)):
        for i in range(len(tokens) - n + 1):
            window = tokens[i:i + n]
            # Avoid phrases that start or end with stopwords
            if not is_stopword(window[0]) and not is_stopword(window[-1]):
                phrases.append(" ".join(window))
    return phrases


class QueryRepresentation:
    """
    Structured representation of a processed search query.
    Provides tokens, stems, extracted phrases, and term frequency weights.
    """

    def __init__(self, raw_query: str, content_terms: List[str] = None):
        self.raw_query: str = raw_query
        # 1. Extract explicit quotes
        cleaned_query, self.quoted_phrases = extract_quoted_phrases(raw_query)

        # 2. Normalize and tokenize
        self.normalized_query: str = normalize_text(cleaned_query)
        self.raw_tokens: List[str] = tokenize(self.normalized_query)

        # 3. Stopword handling (preserving intent question words like 'when', 'how')
        self.filtered_tokens: List[str] = filter_stopwords(self.raw_tokens, preserve_intent=True)

        # Fallback: if all tokens were stopwords (e.g. query was "who to be"), keep raw tokens
        if not self.filtered_tokens and self.raw_tokens:
            self.filtered_tokens = self.raw_tokens
        if content_terms is not None:
            # Intent drives extraction, not document relevance. Main search
            # supplies analyzed content terms rather than ranking on 'what/when'.
            self.filtered_tokens = list(content_terms)

        # 4. Stemming
        self.stems: List[str] = [stem_word(t) for t in self.filtered_tokens]

        # 5. Term frequencies
        self.term_frequencies: Dict[str, int] = {}
        for t in self.filtered_tokens:
            self.term_frequencies[t] = self.term_frequencies.get(t, 0) + 1

        self.stem_frequencies: Dict[str, int] = {}
        for s in self.stems:
            self.stem_frequencies[s] = self.stem_frequencies.get(s, 0) + 1

        # 6. Phrase detection (bigrams / trigrams + explicit quotes)
        phrase_set: Set[str] = set(self.quoted_phrases)
        if len(self.filtered_tokens) >= 2:
            phrase_set.update(extract_phrases_from_tokens(self.filtered_tokens, 2, 3))
        self.phrases: List[str] = list(phrase_set)

    def __repr__(self) -> str:
        return (f"<QueryRepresentation raw='{self.raw_query}' "
                f"tokens={self.filtered_tokens} stems={self.stems} phrases={self.phrases}>")
