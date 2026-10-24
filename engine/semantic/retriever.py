"""
PESE Semantic: Semantic Retriever
Retrieves dense semantic candidates from the vector index, aggregates passage and document
similarities, evaluates drift guards, and ranks semantic candidates.
"""

from typing import List, Dict, Optional, Tuple, Any
import numpy as np

from .models import SemanticCandidate
from .index import VectorIndex
from .drift import SemanticDriftDetector
from ..indexing.store import DocumentStore


class SemanticRetriever:
    """Retrieves document candidates based on dense passage and document embeddings."""

    def __init__(
        self,
        vector_index: VectorIndex,
        doc_store: Optional[DocumentStore] = None,
        drift_detector: Optional[SemanticDriftDetector] = None,
        document_metadata: Optional[Dict[str, Any]] = None,
    ):
        self.index = vector_index
        self.doc_store = doc_store
        self.document_metadata = document_metadata
        self.drift_detector = drift_detector or SemanticDriftDetector()

    def retrieve_candidates(
        self,
        query: str,
        query_terms: Optional[List[str]] = None,
        max_candidates: int = 50,
        min_similarity: float = 0.30,
    ) -> List[SemanticCandidate]:
        """
        Embed the query and retrieve top semantic candidates by combining
        passage-level and document-level dense similarities.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        query_terms = query_terms or cleaned_query.lower().split()
        query_vec = self.index.provider.embed_query(cleaned_query)

        # 1. Search passages (top 60)
        passage_hits = self.index.search_passages(query_vec, top_k=60)

        # 2. Search documents (top 30)
        doc_hits = self.index.search_documents(query_vec, top_k=30)

        # Map document level similarities
        doc_sim_map: Dict[str, float] = {
            m.doc_id: sim for m, sim in doc_hits
        }

        # Aggregate passage hits by doc_id
        doc_passage_map: Dict[str, Tuple[str, str, str, float]] = {}  # doc_id -> (slug, title, text, best_score, passage_id)
        for p_meta, score in passage_hits:
            doc_id = p_meta.doc_id
            if doc_id not in doc_passage_map or score > doc_passage_map[doc_id][3]:
                doc_passage_map[doc_id] = (p_meta.slug, p_meta.title, p_meta.text, score, p_meta.passage_id)

        # Union of candidate doc_ids
        candidate_ids = set(doc_passage_map.keys()).union(set(doc_sim_map.keys()))
        candidates: List[SemanticCandidate] = []

        for doc_id in candidate_ids:
            p_info = doc_passage_map.get(doc_id)
            doc_sim = doc_sim_map.get(doc_id, 0.0)

            if p_info:
                slug, title, best_text, p_score, p_id = p_info
            else:
                # Find title/slug from doc metadata in index
                d_meta = next((d for d in self.index.doc_meta if d.doc_id == doc_id), None)
                slug = d_meta.slug if d_meta else doc_id
                title = d_meta.title if d_meta else doc_id
                best_text = ""
                p_score = 0.0
                p_id = None

            # Combined semantic similarity:
            # Passages are granular and specific (70% weight), doc level provides context (30% weight)
            if p_score > 0.0 and doc_sim > 0.0:
                raw_score = (0.70 * p_score) + (0.30 * doc_sim)
            elif p_score > 0.0:
                raw_score = p_score
            else:
                raw_score = doc_sim

            if raw_score < min_similarity:
                continue

            # Check semantic drift
            drift_penalty = 0.0
            drift_reason = None

            if self.document_metadata is not None:
                meta = self.document_metadata.get(doc_id, {})
                drift_penalty, drift_reason = self.drift_detector.evaluate_drift(
                    query=cleaned_query, query_terms=query_terms, doc_title=meta.get("title", ""),
                    doc_content=meta.get("content", ""), doc_keywords=meta.get("keywords", []), semantic_score=raw_score)
            elif self.doc_store:
                doc_obj = self.doc_store.get_document(doc_id)
                if doc_obj:
                    drift_penalty, drift_reason = self.drift_detector.evaluate_drift(
                        query=cleaned_query,
                        query_terms=query_terms,
                        doc_title=doc_obj.title,
                        doc_content=doc_obj.content,
                        doc_keywords=doc_obj.keywords,
                        semantic_score=raw_score,
                    )

            effective_score = max(0.0, raw_score * (1.0 - drift_penalty))

            candidates.append(
                SemanticCandidate(
                    doc_id=doc_id,
                    slug=slug,
                    title=title,
                    semantic_score=round(effective_score, 4),
                    best_passage_id=p_id,
                    best_passage_text=best_text,
                    best_passage_score=round(p_score, 4),
                    doc_similarity=round(doc_sim, 4),
                    semantic_rank=0,
                    is_semantic_rescue=False,
                    drift_penalty_applied=round(drift_penalty, 4),
                    drift_reason=drift_reason,
                )
            )

        # Sort descending by effective semantic score
        candidates.sort(key=lambda c: c.semantic_score, reverse=True)

        # Assign ranks
        for rank, cand in enumerate(candidates, start=1):
            cand.semantic_rank = rank

        return candidates[:max_candidates]
