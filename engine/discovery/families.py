"""
PESE Discovery: Query Families
Lightweight semantic clustering grouping queries, topics, and question patterns.
Acts as a bridge between lexical discovery and the future Phase 3 Knowledge Graph.
"""

from typing import List, Dict, Optional, Set
from .models import QueryFamily

# Families are derived from the published corpus. No corpus-specific seeds.
STANDARD_QUERY_FAMILIES: List[QueryFamily] = []


class QueryFamilyRegistry:
    """Manages query families, finds matching families for queries and documents."""

    def __init__(self, families: Optional[List[QueryFamily]] = None):
        self.families = list(families) if families is not None else []

    @classmethod
    def from_documents(cls, documents):
        from ..nlp.stopwords import GENERIC_STOPWORDS, INTENT_WORDS
        families = []
        for doc in documents:
            topic = set(re_tokens(doc.title + " " + " ".join(doc.keywords))) - GENERIC_STOPWORDS - INTENT_WORDS
            questions = [faq.get("question", "") for faq in doc.faqs if faq.get("question")]
            families.append(QueryFamily(family_id=doc.slug,topic_label=doc.title,
                canonical_slugs=[doc.slug],seed_questions=questions,
                related_queries=[doc.title],topic_keywords=sorted(topic)))
        return cls(families)

    def match_families_by_query(self, query: str) -> List[QueryFamily]:
        q_lower = query.lower()
        tokens = set(re_tokens(q_lower))
        matches = []
        for fam in self.families:
            # Check keywords
            overlap = tokens.intersection(set(fam.topic_keywords))
            if overlap:
                matches.append((len(overlap), fam))
        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches]

    def match_families_by_slug(self, slug: str) -> List[QueryFamily]:
        return [fam for fam in self.families if slug in fam.canonical_slugs]


def re_tokens(text: str) -> List[str]:
    import re
    return [t for t in re.findall(r'[a-zA-Z0-9_\-]+', text) if len(t) > 2]
