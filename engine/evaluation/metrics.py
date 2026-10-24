"""
PESE Evaluation: Metrics
Information Retrieval performance metrics: MRR, Precision@K, Recall@K, Hit@K, and Passage accuracy.
"""

from typing import List, Set, Optional


def reciprocal_rank(ranked_slugs: List[str], relevant_slugs: List[str]) -> float:
    """
    Compute Reciprocal Rank (RR): 1 / (rank of first relevant document).
    Returns 0.0 if no relevant document is retrieved.
    """
    rel_set = set(relevant_slugs)
    for idx, slug in enumerate(ranked_slugs):
        if slug in rel_set:
            return 1.0 / (idx + 1)
    return 0.0


def precision_at_k(ranked_slugs: List[str], relevant_slugs: List[str], k: int) -> float:
    """Compute Precision@K: (number of relevant documents in top K) / K."""
    if k <= 0:
        return 0.0
    top_k = ranked_slugs[:k]
    rel_set = set(relevant_slugs)
    relevant_in_top_k = sum(1 for s in top_k if s in rel_set)
    return relevant_in_top_k / k


def recall_at_k(ranked_slugs: List[str], relevant_slugs: List[str], k: int) -> float:
    """Compute Recall@K: (number of relevant documents in top K) / (total relevant documents)."""
    if not relevant_slugs or k <= 0:
        return 0.0
    top_k = ranked_slugs[:k]
    rel_set = set(relevant_slugs)
    relevant_in_top_k = sum(1 for s in top_k if s in rel_set)
    return relevant_in_top_k / len(rel_set)


def hit_at_k(ranked_slugs: List[str], relevant_slugs: List[str], k: int) -> bool:
    """True if at least one relevant document appears in the top K."""
    top_k = set(ranked_slugs[:k])
    return bool(top_k.intersection(set(relevant_slugs)))


def passage_match_hit(snippet_text: str, expected_contains: Optional[str]) -> Optional[bool]:
    """Check if expected passage snippet substring is present in the snippet."""
    if not expected_contains:
        return None
    return expected_contains.lower() in snippet_text.lower()
