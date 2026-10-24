"""
PESE NLP: Normalizer
Text normalization module for search engine processing.
Handles unicode normalization, lowercase folding, whitespace cleaning, and safe punctuation handling.
"""

import re
import unicodedata


# Common contractions mapping for query/document alignment
CONTRACTIONS = {
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "won't": "will not",
    "wouldn't": "would not",
    "can't": "cannot",
    "couldn't": "could not",
    "shouldn't": "should not",
    "it's": "it is",
    "i'm": "i am",
    "i've": "i have",
    "i'll": "i will",
    "they're": "they are",
    "we're": "we are",
    "you're": "you are",
    "that's": "that is",
    "what's": "what is",
    "where's": "where is",
    "when's": "when is",
}


def expand_contractions(text: str) -> str:
    """Expand common English contractions to their normalized forms."""
    pattern = re.compile(r'\b(' + '|'.join(re.escape(k) for k in CONTRACTIONS.keys()) + r')\b', re.IGNORECASE)

    def replace(match):
        matched = match.group(0).lower()
        return CONTRACTIONS.get(matched, match.group(0))

    return pattern.sub(replace, text)


def normalize_unicode(text: str) -> str:
    """Normalize unicode and strip combining diacritics/accents (e.g. café -> cafe)."""
    if not text:
        return ""
    nfkc = unicodedata.normalize("NFKC", text)
    decomposed = unicodedata.normalize("NFD", nfkc)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def clean_whitespace(text: str) -> str:
    """Collapse consecutive whitespace characters and trim edges."""
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text: str, expand: bool = True) -> str:
    """
    Standard normalization pipeline:
    1. Unicode normalization (NFKC)
    2. Lowercase folding
    3. Optional contraction expansion
    4. Collapse whitespace
    """
    if not text:
        return ""

    text = normalize_unicode(text)
    text = text.lower()
    if expand:
        text = expand_contractions(text)
    text = clean_whitespace(text)
    return text
