"""
PESE Discovery: Related Searches Engine
Surfaces topically coherent related search queries based on link neighborhoods,
query reformulation patterns, heading relationships, and result-set overlap.
"""

import time
import re
from typing import List, Dict, Any, Optional, Set
from ..indexing.store import DocumentStore
from ..indexing.document import Document
from ..link_graph.graph import LinkGraph
from .models import RelatedSearchItem, RelatedSearchesResponse
from .history import SearchHistoryStore, LocalHistoryStore
from .sessions import SessionManager
from .families import QueryFamilyRegistry
from .scoring import calculate_related_search_score


class RelatedSearchEngine:
    """
    Authoritative Related Searches engine.
    Derives candidate queries from link graph neighbors, document headings,
    historical reformulation chains, and query families.
    """

    def __init__(
        self,
        store: DocumentStore,
        graph: LinkGraph,
        history_store: Optional[SearchHistoryStore] = None,
        session_manager: Optional[SessionManager] = None,
        family_registry: Optional[QueryFamilyRegistry] = None,
    ):
        self.store = store
        self.graph = graph
        self.history_store = history_store or LocalHistoryStore()
        self.session_manager = session_manager or SessionManager(self.history_store)
        self.family_registry = family_registry or QueryFamilyRegistry()

    def get_related_searches(
        self,
        query: str,
        top_slugs: Optional[List[str]] = None,
        limit: int = 5,
        debug: bool = False,
    ) -> RelatedSearchesResponse:
        """
        Generate ranked related searches for a query given top returned SERP document slugs.
        """
        start_time = time.perf_counter()
        q_clean = query.strip()
        q_lower = q_clean.lower()

        if not q_clean:
            return RelatedSearchesResponse(query="", related_searches=[], took_ms=0.0)

        top_slugs = top_slugs or []
        candidates: Dict[str, Dict[str, Any]] = {}

        # 1. Internal Link Graph Neighborhood Candidates
        # For the top returned documents, check incoming and outgoing neighbors
        for slug in top_slugs[:1]:
            # Outgoing links from this document
            out_neighbors = self.graph.get_out_links(slug)
            for neighbor_slug in out_neighbors:
                doc = self.store.get_by_slug(neighbor_slug)
                if doc:
                    self._add_candidate(
                        candidates,
                        text=doc.title,
                        source="link_neighborhood",
                        link_affinity=2.5,
                        topic_overlap=self._calculate_term_overlap(q_lower, doc.title.lower()),
                        slug=neighbor_slug,
                    )

            # Ingoing links to this document
            in_neighbors = self.graph.get_in_links(slug)
            for neighbor_slug in in_neighbors[:2]:
                doc = self.store.get_by_slug(neighbor_slug)
                if doc:
                    self._add_candidate(
                        candidates,
                        text=doc.title,
                        source="link_neighborhood",
                        link_affinity=2.0,
                        topic_overlap=self._calculate_term_overlap(q_lower, doc.title.lower()),
                        slug=neighbor_slug,
                    )

            # Headings from top documents
            top_doc = self.store.get_by_slug(slug)
            if top_doc:
                for h in top_doc.headings or []:
                    clean_h = re.sub(r'^(?:Phase\s+\d+:?|\d+\.?\s*)', '', h).strip()
                    if 4 <= len(clean_h) <= 50 and clean_h.lower() != q_lower:
                        self._add_candidate(
                            candidates,
                            text=clean_h,
                            source="heading",
                            link_affinity=1.5,
                            topic_overlap=self._calculate_term_overlap(q_lower, clean_h.lower()),
                            slug=slug,
                        )

        # 2. Query Reformulation History
        # If users previously queried A and then reformulated to B
        if self.history_store.is_history_enabled():
            chains = self.history_store.get_reformulation_chains()
            for prev_q, next_q, count in chains:
                if prev_q == q_lower and next_q != q_lower:
                    self._add_candidate(
                        candidates,
                        text=next_q,
                        source="reformulation",
                        reformulation_freq=count,
                        topic_overlap=self._calculate_term_overlap(q_lower, next_q),
                    )
                elif next_q == q_lower and prev_q != q_lower:
                    self._add_candidate(
                        candidates,
                        text=prev_q,
                        source="reformulation",
                        reformulation_freq=count,
                        topic_overlap=self._calculate_term_overlap(q_lower, prev_q),
                    )

        # 3. Query Family Matches
        matching_families = self.family_registry.match_families_by_query(q_clean)
        for fam in matching_families[:2]:
            for rq in fam.related_queries:
                if rq.lower() != q_lower:
                    self._add_candidate(
                        candidates,
                        text=rq,
                        source="query_family",
                        link_affinity=1.0,
                        topic_overlap=self._calculate_term_overlap(q_lower, rq.lower()) + 1.0,
                    )

        # 4. Score, filter, and rank all candidates
        scored_items: List[RelatedSearchItem] = []
        q_tokens = set(re.findall(r'[a-zA-Z0-9_\-]+', q_lower))

        for text_key, cand in candidates.items():
            cand_text = cand["text"]
            # Exclude if candidate is identical or too short
            if cand_text.lower() == q_lower or len(cand_text) < 3:
                continue

            # Remove subtitle or colon fragments if present
            display_text = cand_text.split(":")[0].strip()

            topic_overlap = cand.get("topic_overlap", 0.0)
            link_affinity = cand.get("link_affinity", 0.0)
            result_overlap = cand.get("result_overlap", 0.0)
            reformulation_freq = cand.get("reformulation_freq", 0)

            # Minimum evidence gate: must have at least some topic, link, or reformulation connection
            if topic_overlap < 0.5 and link_affinity < 1.0 and reformulation_freq < 1:
                continue

            score, debug_trace = calculate_related_search_score(
                topic_overlap=topic_overlap,
                link_affinity=link_affinity,
                result_overlap=result_overlap,
                reformulation_freq=reformulation_freq,
            )

            # Must meet minimum threshold to avoid surfacing nonsense
            if score < 2.0:
                continue

            scored_items.append(
                RelatedSearchItem(
                    query=display_text,
                    score=score,
                    source=cand.get("source", "topic_overlap"),
                    co_occurrence_score=topic_overlap,
                    result_overlap_score=result_overlap,
                    link_affinity_score=link_affinity,
                    debug_trace=debug_trace if debug else {},
                )
            )

        # 5. Sort descending by score
        scored_items.sort(key=lambda x: x.score, reverse=True)

        # Deduplicate
        unique_results: List[RelatedSearchItem] = []
        seen = set()
        for item in scored_items:
            norm = item.query.lower()
            if norm not in seen and norm != q_lower:
                seen.add(norm)
                unique_results.append(item)
                if len(unique_results) >= limit:
                    break

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        return RelatedSearchesResponse(
            query=q_clean,
            related_searches=unique_results,
            took_ms=elapsed_ms,
        )

    def _add_candidate(
        self,
        candidates: Dict[str, Dict[str, Any]],
        text: str,
        source: str,
        link_affinity: float = 0.0,
        topic_overlap: float = 0.0,
        result_overlap: float = 0.0,
        reformulation_freq: int = 0,
        slug: Optional[str] = None,
    ) -> None:
        key = text.strip().lower()
        if not key:
            return

        if key not in candidates:
            candidates[key] = {
                "text": text.strip(),
                "source": source,
                "link_affinity": link_affinity,
                "topic_overlap": topic_overlap,
                "result_overlap": result_overlap,
                "reformulation_freq": reformulation_freq,
                "slug": slug,
            }
        else:
            # Accumulate signals
            existing = candidates[key]
            existing["link_affinity"] = max(existing.get("link_affinity", 0.0), link_affinity)
            existing["topic_overlap"] = max(existing.get("topic_overlap", 0.0), topic_overlap)
            existing["result_overlap"] = max(existing.get("result_overlap", 0.0), result_overlap)
            existing["reformulation_freq"] = max(existing.get("reformulation_freq", 0), reformulation_freq)

    def _calculate_term_overlap(self, text_a: str, text_b: str) -> float:
        """Compute token overlap ratio between two strings."""
        tokens_a = set(re.findall(r'[a-zA-Z0-9_\-]+', text_a))
        tokens_b = set(re.findall(r'[a-zA-Z0-9_\-]+', text_b))
        stopwords = {"what", "is", "a", "the", "and", "in", "to", "for", "of", "on", "how", "why", "when"}
        filtered_a = tokens_a - stopwords
        filtered_b = tokens_b - stopwords
        if not filtered_a or not filtered_b:
            return 0.0
        common = filtered_a.intersection(filtered_b)
        return round(len(common) * 1.5, 2)
