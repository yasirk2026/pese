"""
PESE NLP: Stopwords
Configurable stopword handling for lexical retrieval.
Distinguishes between generic function words and intent/question words.
"""

from typing import Set, List


# Generic English stopwords that rarely carry discriminant topical information in unigram matching
GENERIC_STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't",
    "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't",
    "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "i", "i'd", "i'll", "i'm", "i've",
    "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more",
    "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only",
    "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't",
    "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than", "that",
    "that's", "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these",
    "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've",
    "were", "weren't", "while", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll",
    "you're", "you've", "your", "yours", "yourself", "yourselves"
}

# Question / intent words preserved for temporal/intent signals in passage extraction
INTENT_WORDS: Set[str] = {
    "when", "where", "why", "how", "what", "which", "who", "whom", "whose"
}

# Default retrieval stopwords: generic stopwords minus intent words
DEFAULT_STOPWORDS: Set[str] = GENERIC_STOPWORDS - INTENT_WORDS


def is_stopword(token: str, custom_stopwords: Set[str] = None) -> bool:
    """Check if a token is in the stopword list."""
    words = custom_stopwords if custom_stopwords is not None else DEFAULT_STOPWORDS
    return token.lower() in words


def filter_stopwords(tokens: List[str], preserve_intent: bool = True) -> List[str]:
    """
    Filter stop words from a list of tokens.
    If preserve_intent is True, intent words ('when', 'how', etc.) are preserved.
    """
    stopwords = DEFAULT_STOPWORDS if preserve_intent else GENERIC_STOPWORDS
    return [t for t in tokens if t.lower() not in stopwords]
