"""Shared lexical evidence helpers. These are rules, not learned semantics.

Acronyms are equivalences only: a regional conflict is not interchangeable
with an entire world war. Matching uses complete tokens, never stem prefixes.
"""
import re
from functools import lru_cache
from .stemmer import stem_word

ACRONYMS = {
    "ww2": ["ww2", "wwii", "world war 2", "world war ii", "world war two"],
    "wwii": ["ww2", "wwii", "world war 2", "world war ii", "world war two"],
    "ai": ["ai", "artificial intelligence"],
    "ml": ["ml", "machine learning"],
    "ir": ["ir", "information retrieval"],
    "qa": ["qa", "question answering"],
    "nlp": ["nlp", "natural language processing"],
    "os": ["os", "operating system"],
    "cpu": ["cpu", "central processing unit"],
    "gpu": ["gpu", "graphics processing unit"],
    "usa": ["usa", "united states", "u.s."],
    "uk": ["uk", "united kingdom"],
}


@lru_cache(maxsize=2048)
def _stem_spans(text):
    result = {}
    for match in re.finditer(r"\w+",text.lower()):
        result.setdefault(stem_word(match.group()),[]).append(match.span())
    return result


def term_spans(term, text):
    term = term.lower()
    spans = set()
    for alias in ACRONYMS.get(term, [term]):
        spans.update(m.span() for m in re.finditer(rf"(?<!\w){re.escape(alias)}(?!\w)", text.lower()))
    # Equal Porter stems, not prefix matching ('open' must not match 'reopened').
    spans.update(_stem_spans(text).get(stem_word(term),[]))
    return sorted(spans)


def term_matches(term, text):
    return bool(term_spans(term, text))


@lru_cache(maxsize=2048)
def sentences(text):
    """Protect abbreviation offsets by equal-length replacement."""
    protected = re.sub(r"\b(?:[A-Za-z]\.){2,}|\b(?:Mr|Mrs|Dr|Prof|e\.g|i\.e)\.",
                       lambda m: m.group().replace('.', '\u2024'), text)
    return [s.replace('\u2024','.').strip() for s in re.split(r'(?<=[.!?])\s+|\n+',protected) if s.strip()]
