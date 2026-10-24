"""
PESE NLP package: text normalization, tokenization, stemming, stopwords, and query processing.
"""

from .normalizer import normalize_text, expand_contractions
from .stopwords import filter_stopwords, is_stopword, DEFAULT_STOPWORDS, INTENT_WORDS
from .stemmer import stem_word, stem_words, PorterStemmer
from .tokenizer import (
    tokenize,
    generate_ngrams,
    extract_quoted_phrases,
    QueryRepresentation
)

__all__ = [
    "normalize_text",
    "expand_contractions",
    "filter_stopwords",
    "is_stopword",
    "DEFAULT_STOPWORDS",
    "INTENT_WORDS",
    "stem_word",
    "stem_words",
    "PorterStemmer",
    "tokenize",
    "generate_ngrams",
    "extract_quoted_phrases",
    "QueryRepresentation",
]
