"""
PESE Quality: Quality Signals
Computes positive document quality signals based on structural completeness.
"""

from typing import Dict, Any
from ..indexing.document import Document
from ..nlp.tokenizer import tokenize


class QualitySignalScorer:
    """Computes document quality score in [0.0, 1.0]."""

    def compute_quality(self, doc: Document) -> Dict[str, Any]:
        score = 0.0
        factors = []

        tokens = tokenize(doc.content)
        faq_tokens = []
        for faq in (doc.faqs or []):
            faq_tokens.extend(tokenize(f"{faq.get('question', '')} {faq.get('answer', '')}"))
        word_count = len(tokens) + len(faq_tokens)

        # 1. Document length sweet spot (100 to 1200 words)
        if 80 <= word_count <= 1500:
            score += 0.4
            factors.append("Substantial content depth")
        elif word_count > 30:
            score += 0.2
            factors.append("Moderate content depth")

        # 2. Informative meta description
        if doc.meta_description and 30 <= len(doc.meta_description) <= 300:
            score += 0.2
            factors.append("Well-formed meta description")

        # 3. Structural headings
        headings = doc.get_all_headings()
        if len(headings) >= 2:
            score += 0.25
            factors.append(f"Structured with {len(headings)} clear headings")
        elif len(headings) == 1:
            score += 0.15
            factors.append("Structured with heading")

        # 4. Internal linking presence
        links = doc.get_all_internal_links()
        if len(links) >= 1:
            score += 0.15
            factors.append(f"Connected to knowledge graph ({len(links)} links)")

        # 5. Native FAQ schema presence
        if doc.faqs and len(doc.faqs) >= 1:
            score += 0.2
            factors.append(f"Structured with {len(doc.faqs)} native FAQ entries")

        final_score = min(1.0, round(score, 3))
        return {
            "quality_score": final_score,
            "factors": factors,
        }
