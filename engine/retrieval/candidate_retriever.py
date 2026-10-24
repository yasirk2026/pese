"""
PESE Retrieval: Candidate Retriever
Retrieves candidate documents matching query terms and performs preliminary BM25F scoring.
"""

from typing import List, Dict, Any, Set
from ..indexing.inverted_index import InvertedIndex
from ..nlp.tokenizer import QueryRepresentation
from .bm25 import BM25FScorer


class CandidateRetriever:
    """Retrieves document candidates from the inverted index."""

    def __init__(self, index: InvertedIndex):
        self.index = index
        self.scorer = BM25FScorer(index)

    def retrieve_candidates(
        self,
        query_rep: QueryRepresentation,
        max_candidates: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Identify all documents containing at least one query term/stem,
        compute their multi-field BM25F breakdown, and return sorted candidates.
        """
        candidate_ids: Set[str] = set()

        # Collect document IDs matching query terms and stems
        all_terms = query_rep.filtered_tokens + query_rep.stems
        for term in all_terms:
            postings = self.index.get_postings(term)
            for p in postings:
                candidate_ids.add(p.doc_id)

        candidates = []
        for doc_id in candidate_ids:
            score_data = self.scorer.score_document(doc_id, query_rep)
            doc_meta = self.index.documents.get(doc_id, {})

            candidates.append({
                "doc_id": doc_id,
                "slug": doc_meta.get("slug", ""),
                "title": doc_meta.get("title", ""),
                "bm25f_data": score_data,
                "preliminary_score": score_data["bm25f_total"],
                "doc_meta": doc_meta,
            })

        # Sort descending by preliminary score
        candidates.sort(key=lambda c: c["preliminary_score"], reverse=True)
        return candidates[:max_candidates]
