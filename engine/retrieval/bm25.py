"""
PESE Retrieval: BM25 / BM25F
Multi-field Okapi BM25 implementation.
Field weights belong strictly to the search engine.
"""

import math
from typing import Dict, List, Optional
from ..indexing.inverted_index import InvertedIndex, Posting
from ..nlp.tokenizer import QueryRepresentation


# Search engine internal field weights and length normalization parameters
FIELD_WEIGHTS: Dict[str, float] = {
    "title": 3.5,
    "headings": 2.5,
    "keywords": 2.8,
    "meta_description": 1.8,
    "body": 1.0,
}

FIELD_B_PARAMS: Dict[str, float] = {
    "title": 0.75,
    "headings": 0.75,
    "keywords": 0.5,
    "meta_description": 0.75,
    "body": 0.75,
}

K1_PARAM: float = 1.2


def compute_idf(doc_freq: int, total_docs: int) -> float:
    """
    Standard Robertson-Spärck Jones IDF with floor to ensure positive weights:
    IDF = ln( (N - n + 0.5) / (n + 0.5) + 1.0 )
    """
    if total_docs == 0:
        return 0.0
    numerator = total_docs - doc_freq + 0.5
    denominator = doc_freq + 0.5
    val = (numerator / denominator) + 1.0
    return math.log(max(1.0, val))


class BM25FScorer:
    """Scores documents against queries using multi-field BM25F."""

    def __init__(self, index: InvertedIndex, k1: float = K1_PARAM):
        self.index = index
        self.k1 = k1
        self.field_weights = FIELD_WEIGHTS
        self.field_b = FIELD_B_PARAMS

    def score_document(
        self,
        doc_id: str,
        query_rep: QueryRepresentation,
    ) -> Dict[str, float]:
        """
        Compute BM25F score and field breakdowns for a single document.
        Returns:
            {
                "bm25f_total": float,
                "title_score": float,
                "headings_score": float,
                "keywords_score": float,
                "meta_score": float,
                "body_score": float,
                "matched_terms": int,
                "total_query_terms": int
            }
        """
        doc_lengths = self.index.field_lengths.get(doc_id, {})
        avg_lengths = self.index.avg_field_lengths
        total_docs = max(1, self.index.total_docs)

        # Unique query terms to evaluate (tokens and stems)
        terms_to_check = set(query_rep.filtered_tokens + query_rep.stems)
        if not terms_to_check:
            return {
                "bm25f_total": 0.0,
                "title_score": 0.0,
                "headings_score": 0.0,
                "keywords_score": 0.0,
                "meta_score": 0.0,
                "body_score": 0.0,
                "matched_terms": 0,
                "total_query_terms": 0,
            }

        total_score = 0.0
        field_scores = {f: 0.0 for f in self.field_weights}
        matched_terms_count = 0

        # Group by stem / token to avoid double-counting identical semantic units
        evaluated_stems = set()

        for term in query_rep.filtered_tokens:
            stem = query_rep.stems[query_rep.filtered_tokens.index(term)] if term in query_rep.filtered_tokens else term
            if stem in evaluated_stems:
                continue
            evaluated_stems.add(stem)

            # Check postings for exact term or stem
            posting_exact = self.index.index.get(term, {}).get(doc_id)
            posting_stem = self.index.index.get(stem, {}).get(doc_id)

            posting = posting_exact or posting_stem
            if not posting:
                continue

            matched_terms_count += 1
            df = max(self.index.get_document_frequency(term), self.index.get_document_frequency(stem))
            idf = compute_idf(df, total_docs)

            # Compute normalized pseudo-frequency across fields
            weighted_tf_sum = 0.0
            term_field_contribs = {}

            for field, weight in self.field_weights.items():
                tf = posting.field_tfs.get(field, 0)
                if tf <= 0:
                    continue
                d_len = doc_lengths.get(field, 1)
                avg_len = avg_lengths.get(field, 1.0)
                b = self.field_b.get(field, 0.75)

                len_norm = 1.0 - b + b * (d_len / max(1.0, avg_len))
                norm_tf = tf / max(0.1, len_norm)
                weighted_norm_tf = weight * norm_tf

                weighted_tf_sum += weighted_norm_tf
                term_field_contribs[field] = weighted_norm_tf

            # BM25 saturation curve: (w_tf) / (k1 + w_tf)
            if weighted_tf_sum > 0:
                saturation = weighted_tf_sum / (self.k1 + weighted_tf_sum)
                term_score = idf * saturation
                total_score += term_score

                # Allocate field breakdown proportionally
                for field, wtf in term_field_contribs.items():
                    field_scores[field] += term_score * (wtf / weighted_tf_sum)

        return {
            "bm25f_total": total_score,
            "title_score": field_scores["title"],
            "headings_score": field_scores["headings"],
            "keywords_score": field_scores["keywords"],
            "meta_score": field_scores["meta_description"],
            "body_score": field_scores["body"],
            "matched_terms": matched_terms_count,
            "total_query_terms": len(evaluated_stems),
        }
