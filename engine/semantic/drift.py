"""
PESE Semantic: Semantic Drift & Polysemy Safeguards
Detects topical drift, domain clashes, and polysemous collisions (e.g. 'python snake' vs 'python code',
'Japanese car' vs 'Japanese language notes') to prevent semantic hallucinations from outranking exact text.
"""

import re
from typing import List, Dict, Set, Tuple, Optional
from ..indexing.document import Document


# Domain anchor lexicons for detecting severe polysemy and topical drift
DOMAIN_DISCRIMINATORS: Dict[str, Dict[str, Set[str]]] = {
    "reptile_vs_programming": {
        "query_anchors": {"snake", "reptile", "serpent", "venom", "boa", "lizard", "animal", "wildlife", "scales"},
        "incompatible_corpus_tokens": {"pip", "virtualenv", "interpreter", "syntax", "functions", "library", "import", "code", "runtime", "package", "wheel", "python3"},
    },
    "automotive_vs_linguistics": {
        "query_anchors": {"car", "automobile", "engine", "vehicle", "sedan", "toyota", "honda", "transmission", "mileage"},
        "incompatible_corpus_tokens": {"kanji", "hiragana", "katakana", "grammar", "vocabulary", "jlpt", "anki", "particles", "language"},
    },
    "culinary_vs_hardware": {
        "query_anchors": {"recipe", "cooking", "dessert", "ingredient", "dish", "bake", "chef"},
        "incompatible_corpus_tokens": {"motherboard", "processor", "ram", "overclocking", "bios", "soldering"},
    },
}


class SemanticDriftDetector:
    """
    Evaluates whether a candidate document retrieved via dense semantic similarity
    suffers from domain drift or polysemy collision relative to the user query.
    """

    def __init__(self):
        self.weak_similarity_threshold = 0.50

    def evaluate_drift(
        self,
        query: str,
        query_terms: List[str],
        doc_title: str,
        doc_content: str,
        doc_keywords: List[str],
        semantic_score: float,
    ) -> Tuple[float, Optional[str]]:
        """
        Evaluate candidate for semantic drift.
        Returns:
            (drift_penalty: float in [0.0, 1.0], reason: Optional[str])
        """
        query_lower = query.lower()
        query_token_set = set(re.findall(r'\b[a-z0-9_]+\b', query_lower))

        doc_text_sample = f"{doc_title} {' '.join(doc_keywords)} {doc_content[:1500]}".lower()
        doc_token_set = set(re.findall(r'\b[a-z0-9_]+\b', doc_text_sample))

        # Check domain discriminators
        for domain_name, rules in DOMAIN_DISCRIMINATORS.items():
            query_anchors = rules["query_anchors"]
            incompatible_tokens = rules["incompatible_corpus_tokens"]

            matched_anchors = query_token_set.intersection(query_anchors)
            if matched_anchors:
                # The query contains an explicit domain anchor
                # Check if document has high density of incompatible tokens and zero anchor tokens
                anchor_in_doc = any(a in doc_token_set for a in matched_anchors)
                incompatible_in_doc = doc_token_set.intersection(incompatible_tokens)

                if not anchor_in_doc and len(incompatible_in_doc) >= 2:
                    anchors_str = ", ".join(sorted(matched_anchors))
                    incomp_str = ", ".join(sorted(list(incompatible_in_doc)[:4]))
                    penalty = 0.85  # Heavy 85% penalty against semantic drift
                    reason = (
                        f"Topical drift detected: query requires '{anchors_str}' domain, but document "
                        f"contains incompatible domain tokens ({incomp_str}) with 0 anchor mentions."
                    )
                    return penalty, reason

        # General guard: If query has >= 3 specific content terms, and doc contains NONE of them,
        # and semantic score is weak (< 0.50), apply mild drift penalty
        if len(query_terms) >= 3:
            overlap = query_token_set.intersection(doc_token_set)
            if len(overlap) == 0 and semantic_score < self.weak_similarity_threshold:
                return 0.35, f"Weak semantic alignment without lexical support: 0/{len(query_terms)} terms present."

        return 0.0, None
