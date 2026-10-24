"""
PESE Semantic: Candidate Fusion
Performs Reciprocal Rank Fusion (RRF) between lexical BM25F and dense semantic candidates,
identifies semantic rescues, and integrates hybrid relevance signals.
"""

from typing import List, Dict, Any, Optional, Set
from .models import SemanticCandidate, FusedCandidate


DEFAULT_RRF_K = 60
DEFAULT_LEXICAL_WEIGHT = 1.0
DEFAULT_SEMANTIC_WEIGHT = 0.85
SEMANTIC_RESCUE_THRESHOLD = 0.58


class HybridCandidateFuser:
    """
    Combines lexical candidates from BM25F and semantic candidates from VectorIndex
    using Reciprocal Rank Fusion (RRF) and identifies semantic rescues.
    """

    def __init__(
        self,
        rrf_k: int = DEFAULT_RRF_K,
        lexical_weight: float = DEFAULT_LEXICAL_WEIGHT,
        semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
        rescue_threshold: float = SEMANTIC_RESCUE_THRESHOLD,
    ):
        self.rrf_k = rrf_k
        self.lexical_weight = lexical_weight
        self.semantic_weight = semantic_weight
        self.rescue_threshold = rescue_threshold

    def fuse(
        self,
        lexical_candidates: List[Dict[str, Any]],
        semantic_candidates: List[SemanticCandidate],
        max_fused: int = 50,
    ) -> List[FusedCandidate]:
        """
        Merge lexical and semantic candidates.
        Returns a sorted list of FusedCandidate objects.
        """
        # Map lexical candidates by doc_id
        lex_map: Dict[str, Tuple[int, Dict[str, Any]]] = {}
        for rank, cand in enumerate(lexical_candidates, start=1):
            lex_map[cand["doc_id"]] = (rank, cand)

        # Map semantic candidates by doc_id
        sem_map: Dict[str, SemanticCandidate] = {
            c.doc_id: c for c in semantic_candidates
        }

        all_doc_ids: Set[str] = set(lex_map.keys()).union(set(sem_map.keys()))
        fused_list: List[FusedCandidate] = []

        for doc_id in all_doc_ids:
            lex_info = lex_map.get(doc_id)
            sem_cand = sem_map.get(doc_id)

            lex_rank = lex_info[0] if lex_info else None
            lex_data = lex_info[1] if lex_info else None

            sem_rank = sem_cand.semantic_rank if sem_cand else None
            sem_score = sem_cand.semantic_score if sem_cand else 0.0

            # Compute RRF score
            rrf_score = 0.0
            if lex_rank is not None:
                rrf_score += self.lexical_weight / (self.rrf_k + lex_rank)
            if sem_rank is not None:
                rrf_score += self.semantic_weight / (self.rrf_k + sem_rank)

            # Determine title & slug
            if lex_data:
                slug = lex_data.get("slug", "")
                title = lex_data.get("title", "")
                doc_meta = lex_data.get("doc_meta", {})
                bm25f_data = lex_data.get("bm25f_data", {})
                bm25_score = lex_data.get("preliminary_score", 0.0)
            elif sem_cand:
                slug = sem_cand.slug
                title = sem_cand.title
                doc_meta = {}
                bm25f_data = {
                    "bm25f_total": 0.0,
                    "title_score": 0.0,
                    "headings_score": 0.0,
                    "keywords_score": 0.0,
                    "meta_score": 0.0,
                    "body_score": 0.0,
                    "matched_terms": 0,
                    "total_query_terms": 1,
                }
                bm25_score = 0.0
            else:
                continue

            # Semantic Rescue Detection:
            # Candidate has no lexical presence (or rank is poor/score is 0),
            # but semantic score meets rescue threshold without drift penalty.
            is_rescue = False
            if lex_rank is None or bm25_score <= 1e-4:
                if sem_cand and sem_cand.semantic_score >= self.rescue_threshold and sem_cand.drift_penalty_applied == 0.0:
                    is_rescue = True

            fused = FusedCandidate(
                doc_id=doc_id,
                slug=slug,
                title=title,
                bm25_rank=lex_rank,
                semantic_rank=sem_rank,
                bm25_score=round(bm25_score, 4),
                semantic_score=round(sem_score, 4),
                rrf_score=round(rrf_score, 6),
                is_semantic_rescue=is_rescue,
                best_passage_id=sem_cand.best_passage_id if sem_cand else None,
                best_passage_text=sem_cand.best_passage_text if sem_cand else None,
                best_passage_score=sem_cand.best_passage_score if sem_cand else 0.0,
                drift_penalty=sem_cand.drift_penalty_applied if sem_cand else 0.0,
                drift_reason=sem_cand.drift_reason if sem_cand else None,
                doc_meta=doc_meta,
                bm25f_data=bm25f_data,
            )
            fused_list.append(fused)

        # Sort descending by RRF score
        fused_list.sort(key=lambda f: f.rrf_score, reverse=True)
        return fused_list[:max_fused]
