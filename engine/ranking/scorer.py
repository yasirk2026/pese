"""
PESE Ranking: Scorer & Pipeline
Orchestrates Query Analysis, Minimum Evidence Gating, dense semantic retrieval,
hybrid candidate fusion (RRF), auditable ranking traces, and generalized featured-answer extraction.
"""

import time
import logging
import re
from threading import RLock
from collections import OrderedDict
from copy import deepcopy
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from ..indexing.inverted_index import InvertedIndex
from ..indexing.store import DocumentStore
from ..nlp.tokenizer import QueryRepresentation
from ..retrieval.candidate_retriever import CandidateRetriever
from ..passages.scorer import PassageScorer
from ..passages.highlighter import SnippetGenerator
from ..passages.answer_extractor import FeaturedAnswerExtractor
from ..link_graph.authority import LinkAuthorityCalculator
from ..quality.spam_detector import SpamDetector
from ..quality.quality_signals import QualitySignalScorer
from ..query_analysis.spelling import CorpusSpellingCorrector
from ..query_analysis.analyzer import QueryAnalyzer, AnalyzedQuery
from .evidence_gate import MinimumEvidenceGate, CandidateEvidenceDecision
from .signals import (
    calculate_freshness_signal,
    calculate_phrase_signal,
    calculate_title_signal,
    calculate_heading_signal,
    calculate_keyword_signal,
)

# Semantic hybrid imports
from ..semantic.models import SemanticCandidate, FusedCandidate
from ..semantic.index import VectorIndex
from ..semantic.retriever import SemanticRetriever
from ..semantic.fusion import HybridCandidateFuser
from ..semantic.relations import RelationMatcher
from ..nlp.evidence import term_matches
from ..search_sync.contracts import TargetType, FeedbackType
from ..search_sync.preference_signal import (
    SearchSyncPreferenceSignal,
    preference_signal as default_preference_signal,
)
from ..search_sync.neural_shadow import (
    PESERelationShadowAdapter,
    shadow_adapter as default_shadow_adapter,
)
from uuid import uuid4


class RankingTrace(BaseModel):
    """Auditable mathematical trace explaining exactly how a document was scored."""
    doc_id: str
    slug: str
    title: str
    neural_adjustment: float = 0.0
    neural_model_version: Optional[str] = None

    # Retrieval mode & Hybrid signals
    retrieval_mode: str = "hybrid"
    bm25_rank: Optional[int] = None
    semantic_rank: Optional[int] = None
    semantic_similarity: float = 0.0
    rrf_score: float = 0.0
    is_semantic_rescue: bool = False
    drift_penalty_applied: float = 0.0
    drift_reason: Optional[str] = None

    # Query Analysis Data
    query_intent: str = "GENERAL"
    content_terms: List[str] = Field(default_factory=list)
    effective_query: str = ""
    evidence_gate_passed: bool = True
    evidence_gate_reason: str = "Passed"

    # Neural QA Shadow Mode
    qa_shadow_answer: Optional[str] = None
    qa_agreement: Optional[str] = None
    qa_confidence: Optional[float] = None

    # Phase 2D.2 — Answer Relevance Gate
    answer_relevance_verdict: Optional[str] = None
    answer_relevance_failure: Optional[str] = None
    answer_relevance_score: Optional[float] = None

    # Lexical BM25F components
    bm25f_lexical: float
    bm25f_breakdown: Dict[str, float]

    # Specific field signals
    title_signal: float
    heading_signal: float
    passage_signal: float
    phrase_signal: float
    keyword_signal: float

    # Coverage
    matched_query_terms: int
    total_query_terms: int
    coverage_ratio: float
    coverage_factor: float
    ownership_factor: float = 1.0

    # Graph & Quality signals
    link_authority: float
    freshness_bonus: float
    quality_bonus: float

    # Penalties
    spam_penalty: float
    spam_reasons: List[str]

    # Intermediates
    base_relevance: float
    relevance_gated: float
    positive_total: float
    final_score: float

    # Search Sync Signals (Phase N3-A)
    base_score: Optional[float] = None
    search_sync_adjustment: float = 0.0
    search_sync_feedback: Optional[str] = None

    # Neural Shadow Signals (Phase N3-B: PESE-Rel-0 Observer — Authority: NONE)
    rel_shadow_answers_prob: Optional[float] = None
    rel_shadow_does_not_answer_prob: Optional[float] = None
    rel_shadow_label: Optional[str] = None
    rel_shadow_evidence_id: Optional[str] = None
    rel_shadow_evidence_count: int = 0
    rel_shadow_authority: str = "NONE"
    rel_shadow_alignment: Optional[str] = None
    rel_shadow_status: Optional[str] = None

    def summary_lines(self) -> List[str]:
        lines = [
            f"Retrieval Mode: {self.retrieval_mode.upper()}",
            f"Query Intent: {self.query_intent}",
            f"Effective Query: {self.effective_query}",
            f"Evidence Gate: {self.evidence_gate_reason}",
            f"BM25F Lexical: {self.bm25f_lexical:.4f} (Rank #{self.bm25_rank if self.bm25_rank else 'N/A'})",
            f"Semantic Dense: {self.semantic_similarity:.4f} (Rank #{self.semantic_rank if self.semantic_rank else 'N/A'})",
            f"RRF Fusion Score: {self.rrf_score:.6f}",
            f"Semantic Rescue: {'YES (Rescued Paraphrase)' if self.is_semantic_rescue else 'NO'}",
            f"Title Signal: {self.title_signal:.4f}",
            f"Heading Signal: {self.heading_signal:.4f}",
            f"Passage Signal: {self.passage_signal:.4f}",
            f"Phrase Match Signal: {self.phrase_signal:.4f}",
            f"Keyword Tag Signal: {self.keyword_signal:.4f}",
            f"Coverage Gating: {self.coverage_factor:.4f} ({self.matched_query_terms}/{self.total_query_terms} terms)",
            f"Link Authority: +{self.link_authority:.4f}",
            f"Freshness Bonus: +{self.freshness_bonus:.4f}",
            f"Quality Bonus: +{self.quality_bonus:.4f}",
            f"Spam Penalty: -{round(self.spam_penalty * 100, 1)}%",
        ]
        if self.drift_penalty_applied > 0:
            lines.append(f"Semantic Drift Penalty: -{round(self.drift_penalty_applied * 100, 1)}% ({self.drift_reason})")
        if self.qa_shadow_answer is not None or self.qa_agreement is not None:
            lines.append(f"PESE-QA-0 Shadow: {self.qa_shadow_answer or 'None (Abstained)'} (Agreement: {self.qa_agreement})")
        if self.answer_relevance_verdict is not None:
            lines.append(f"Answer Relevance Gate: {self.answer_relevance_verdict} (Score: {self.answer_relevance_score}, Failure: {self.answer_relevance_failure or 'None'})")
        if self.base_score is not None:
            lines.append(f"MAAE Base Score: {self.base_score:.4f}")
        if self.search_sync_adjustment != 0.0 or self.search_sync_feedback is not None:
            lines.append(f"Search Sync Preference: {self.search_sync_feedback or 'NONE'} ({self.search_sync_adjustment:+.4f})")
        if self.neural_model_version is not None:
            lines.append(f"Neural ranking: {self.neural_model_version} ({self.neural_adjustment:+.4f}; bounded ranking only)")
        if self.rel_shadow_answers_prob is not None:
            not_ans = self.rel_shadow_does_not_answer_prob if self.rel_shadow_does_not_answer_prob is not None else (1.0 - self.rel_shadow_answers_prob)
            lines.extend([
                f"NEURAL SHADOW (PESE-Rel-0)",
                f"Evidence: {self.rel_shadow_evidence_id or 'N/A'}",
                f"P(ANSWERS): {self.rel_shadow_answers_prob:.4f}",
                f"P(DOES_NOT_ANSWER): {not_ans:.4f}",
                f"Shadow Label: {self.rel_shadow_label or 'N/A'}",
                f"Authority: {self.rel_shadow_authority}",
            ])
            if self.rel_shadow_alignment:
                lines.append(f"Diagnostic Alignment: {self.rel_shadow_alignment}")
        lines.extend([
            f"----------------------------------------",
            f"Final Ranking Score: {self.final_score:.4f}",
        ])
        return lines


class SearchResult(BaseModel):
    """Ranked search result item returned to the SERP."""
    rank: int
    doc_id: str
    slug: str
    title: str
    snippet_text: str
    snippet_html: str
    featured_answer: Optional[str] = None
    featured_justification: Optional[str] = None
    is_featured: bool = False
    source_type: str = "authored"
    word_count: int = 0
    in_links_count: int = 0
    base_score: Optional[float] = None
    search_sync_adjustment: float = 0.0
    neural_adjustment: float = 0.0
    search_sync_feedback: Optional[str] = None
    final_score: float
    is_semantic_rescue: bool = False
    semantic_similarity: float = 0.0
    rrf_score: float = 0.0
    trace: RankingTrace
    answer_audit: Dict[str, Any] = Field(default_factory=dict)
    neural_shadow: Optional[Dict[str, Any]] = None
    evidence_provenance: Dict[str, Any] = Field(default_factory=dict)
    learning_evidence_text: Optional[str] = Field(default=None, exclude=True)


class SearchResultsList(list):
    """
    Subclass of list holding SearchResult items, while exposing
    query_analysis, evidence gate, hybrid retrieval metadata, and stage timings for API consumers.
    """
    def __init__(
        self,
        items: List[SearchResult],
        query_analysis: AnalyzedQuery,
        gate_decisions: List[CandidateEvidenceDecision],
        hybrid_trace: Optional[Dict[str, Any]] = None,
        timing: Optional[Dict[str, float]] = None,
        qa_trace: Optional[Dict[str, Any]] = None,
        neural_shadow_trace: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(items)
        self.query_analysis = query_analysis
        self.gate_decisions = gate_decisions
        self.rejected_candidates = [d.to_dict() for d in gate_decisions if not d.passed]
        self.qa_trace = qa_trace
        self.neural_shadow_trace = neural_shadow_trace
        self.hybrid_trace = hybrid_trace or {
            "retrieval_mode": "lexical_only",
            "lexical_candidates_count": len(items),
            "semantic_candidates_count": 0,
            "fused_candidates_count": len(items),
            "semantic_rescues_count": 0,
            "rescued_slugs": [],
        }
        self.timing = timing or {
            "query_analysis_ms": 0.0,
            "bm25f_retrieval_ms": 0.0,
            "dense_retrieval_ms": 0.0,
            "rrf_fusion_ms": 0.0,
            "evidence_gating_ms": 0.0,
            "ranking_scoring_ms": 0.0,
            "passage_scoring_ms": 0.0,
            "answer_extraction_ms": 0.0,
            "server_total_ms": 0.0,
        }


class RankingEngine:
    """The master hybrid search ranking engine."""

    def __init__(
        self,
        index: InvertedIndex,
        link_authority: LinkAuthorityCalculator,
        vector_index: Optional[VectorIndex] = None,
        doc_store: Optional[DocumentStore] = None,
        search_sync: Optional[SearchSyncPreferenceSignal] = None,
        shadow_adapter: Optional[PESERelationShadowAdapter] = None,
        neural_ranker=None,
    ):
        self.index = index
        self.link_authority = link_authority
        self.doc_store = doc_store
        self.search_sync = search_sync or default_preference_signal
        self.shadow_adapter = shadow_adapter or default_shadow_adapter
        from ..intelligence.reranking import NeuralReranker
        self.neural_ranker = neural_ranker or NeuralReranker()
        if neural_ranker is None:
            from ..intelligence.beta.runtime import beta_channel, runtime
            if beta_channel():
                self.neural_ranker = runtime().ranker
        self.retriever = CandidateRetriever(index)
        self.passage_scorer = PassageScorer(index)
        self.snippet_gen = SnippetGenerator()
        self.answer_extractor = FeaturedAnswerExtractor()
        self.spam_detector = SpamDetector()
        self.quality_scorer = QualitySignalScorer()
        from ..indexing.document import Document
        self._documents = {identity: Document.from_dict(meta) for identity, meta in index.documents.items()}
        self._quality = {identity: self.quality_scorer.compute_quality(doc) for identity, doc in self._documents.items()}
        self._spam = {identity: self.spam_detector.evaluate_document(doc) for identity, doc in self._documents.items()}
        self.weights = dict(title=1.8, heading=1.2, passage=1.5, phrase=2.0, keyword=1.4,
                            dense=5.5, rrf=45.0, coverage=1.0)
        self.relation_matcher = RelationMatcher(vector_index.provider) if vector_index else None

        # Query Analysis & Spelling Corrector
        self.spelling_corrector = CorpusSpellingCorrector()
        self.spelling_corrector.build_vocabulary(index.index, raw_terms=getattr(index, "raw_terms", None))
        self.query_analyzer = QueryAnalyzer(self.spelling_corrector)

        # Minimum Evidence Gate
        self.evidence_gate = MinimumEvidenceGate(index)

        # Semantic Hybrid Layer
        self.vector_index = vector_index
        if self.vector_index is not None:
            self.semantic_retriever = SemanticRetriever(
                vector_index=self.vector_index,
                doc_store=self.doc_store,
                document_metadata=self.index.documents,
            )
            self.candidate_fuser = HybridCandidateFuser()
        else:
            self.semantic_retriever = None
            self.candidate_fuser = None

        # PESE-QA-0 Neural Reader Cache
        self._qa_reader = None
        self._qa_load_attempted = False
        self._qa_error = None
        self._qa_lock = RLock()
        self.index_versions = {}
        self._search_cache = OrderedDict()
        self._search_cache_lock = RLock()

    def invalidate_query_cache(self, query: Optional[str] = None) -> None:
        """Invalidate cached SERPs for a given query (e.g. after user feedback) or clear all."""
        with self._search_cache_lock:
            if query is None:
                self._search_cache.clear()
            else:
                norm_target = self.search_sync.normalize_query(query) if self.search_sync else query.strip().lower()
                keys_to_remove = [
                    k for k in list(self._search_cache.keys())
                    if k[0] == query or (self.search_sync and self.search_sync.normalize_query(k[0]) == norm_target)
                ]
                for k in keys_to_remove:
                    self._search_cache.pop(k, None)

    def _get_qa_reader(self):
        with self._qa_lock:
            return self._load_qa_reader()

    def _load_qa_reader(self):
        """Lazily load trained PESE-QA-0 inference reader."""
        if self._qa_reader is not None:
            return self._qa_reader
        if self._qa_load_attempted:
            return None
        self._qa_load_attempted = True
        try:
            import json
            from ..neural.training.checkpoint import load_checkpoint, DEFAULT_QA_CHECKPOINT_DIR
            from ..neural.tokenization.bpe_tokenizer import BPETokenizer
            from ..neural.inference.qa_reader import PESEQAInferenceReader

            chk_file = DEFAULT_QA_CHECKPOINT_DIR / "peseqa0_baseline_final.pt"
            vocab_file = DEFAULT_QA_CHECKPOINT_DIR / "peseqa0_tokenizer.json"
            if chk_file.exists() and vocab_file.exists():
                model, _ = load_checkpoint(chk_file, device="cpu")
                with open(vocab_file, "r", encoding="utf-8") as f:
                    vdata = json.load(f)
                tok = BPETokenizer(vocab=vdata["vocab"], merges=[tuple(m) for m in vdata["merges"]])
                self._qa_reader = PESEQAInferenceReader(model, tok, answerability_threshold=0.50)
                return self._qa_reader
            self._qa_error = "QA checkpoint or tokenizer missing"
        except Exception as exc:
            self._qa_reader = None
            self._qa_error = f"{type(exc).__name__}: {exc}"
            logging.getLogger(__name__).exception("qa_load_failed")
        return None

    def refresh_spelling_vocabulary(self) -> None:
        """Rebuild spelling dictionary after index updates."""
        self.spelling_corrector.build_vocabulary(self.index.index, raw_terms=getattr(self.index, "raw_terms", None))

    def search(
        self, query: str, limit: int = 20, force_raw: bool = False,
        retrieval_mode: str = "hybrid", skip_qa: bool = False,
        search_context_id: Optional[str] = None,
    ) -> SearchResultsList:
        # An engine owns one immutable index generation. Discovery can reuse
        # the primary ranking without repeating retrieval or answer selection.
        # Debug neural inference stays uncached at this layer.
        if not skip_qa:
            return self._search_uncached(query, limit, force_raw, retrieval_mode, False, search_context_id=search_context_id)
        start = time.perf_counter()
        key = self._cache_key(query, force_raw, retrieval_mode)
        with self._search_cache_lock:
            cached = self._search_cache.get(key)
            if cached is not None:
                self._search_cache.move_to_end(key)
                result = deepcopy(cached)
                # A cache hit is a new presentation, not fresh neural inference.
                context_id = search_context_id or f"sc_{uuid4().hex}"
                for item in result:
                    item.evidence_provenance["context_id"] = context_id
                    item.neural_shadow = None
                    item.answer_audit.pop("neural_shadow_observation", None)
                    for field in ("rel_shadow_answers_prob", "rel_shadow_does_not_answer_prob", "rel_shadow_label",
                                  "rel_shadow_evidence_id", "rel_shadow_alignment"):
                        setattr(item.trace, field, None)
                    item.trace.rel_shadow_evidence_count = 0
                    item.trace.rel_shadow_status = "CACHED_NOT_OBSERVED"
                result.neural_shadow_trace = {"authority": "NONE", "status": "CACHED_NOT_OBSERVED",
                                              "search_context_id": context_id}
                del result[limit:]
                result.timing = {name:0.0 for name in result.timing}
                result.timing.update(cache_hit=1.0,server_total_ms=round((time.perf_counter()-start)*1000,2))
                return result
        result = self._search_uncached(query, 100, force_raw, retrieval_mode, True, search_context_id=search_context_id)
        transient_failure = result.hybrid_trace.get("semantic_error") or any(
            item.answer_audit.get("validation",{}).get("failure_class") == "ANSWER_GATE_EXCEPTION"
            for item in result if item.answer_audit.get("validation"))
        transient_failure = transient_failure or any(
            "ANSWER_GATE_EXCEPTION" in item.answer_audit.get("pipeline_v2", {}).get("arbitration", "") or
            any("ANSWER_GATE_EXCEPTION" in c.get("reason", "") for c in item.answer_audit.get("pipeline_v2", {}).get("candidates", []))
            for item in result)
        if not transient_failure:
            with self._search_cache_lock:
                self._search_cache[key] = deepcopy(result)
                self._search_cache.move_to_end(key)
                if len(self._search_cache)>32:
                    self._search_cache.popitem(last=False)
        del result[limit:]
        result.timing["cache_hit"] = 0.0
        result.timing["server_total_ms"] = round((time.perf_counter()-start)*1000,2)
        return result

    def cached_primary_slugs(self, query):
        with self._search_cache_lock:
            cached = self._search_cache.get(self._cache_key(query, False, "hybrid"))
            return [r.slug for r in cached[:5]] if cached is not None else []

    def _cache_key(self,query,force_raw,retrieval_mode):
        key=(query,force_raw,retrieval_mode)
        identity=getattr(self.neural_ranker,"cache_identity",None)
        return (*key,identity) if identity is not None else key

    def _search_uncached(
        self,
        query: str,
        limit: int = 20,
        force_raw: bool = False,
        retrieval_mode: str = "hybrid",
        skip_qa: bool = False,
        search_context_id: Optional[str] = None,
    ) -> SearchResultsList:
        """Execute the end-to-end PESE query analysis, hybrid retrieval, gating, and ranking pipeline."""
        t_total_start = time.perf_counter()
        search_ctx_id = search_context_id or f"sc_{uuid4().hex[:12]}"
        if not query.strip():
            empty_analysis = self.query_analyzer.analyze_query("", force_raw=force_raw)
            return SearchResultsList([], empty_analysis, [])

        # 1. Query Analysis (Normalization, Intent, Important Terms, Typo Recovery)
        t_qa = time.perf_counter()
        analyzed_query = self.query_analyzer.analyze_query(query, force_raw=force_raw)
        effective_qrep = QueryRepresentation(analyzed_query.effective_query, content_terms=analyzed_query.effective_content_terms)
        # Request-local answer state: concurrent PAA/search calls cannot overwrite
        # another query's verdict via last_relevance_result.
        answer_extractor = FeaturedAnswerExtractor()
        # Relation embeddings remain a diagnostic experiment. The independent
        # holdout demonstrated topical similarity passing a wrong WHO relation;
        # cosine similarity must not authorize a production answer.
        _, predicates, properties = answer_extractor.relevance_gate._extract_query_semantic_components(analyzed_query)
        effective_qrep.relation_terms = predicates + properties
        query_analysis_ms = round((time.perf_counter() - t_qa) * 1000.0, 2)

        # Search Sync Active Preference Pre-fetch (Phase N3-A)
        normalized_sync_q = self.search_sync.normalize_query(analyzed_query.effective_query or query)
        active_preferences = self.search_sync.get_query_active_preferences(normalized_sync_q)

        # 2. Candidate Retrieval (Lexical, Semantic, or Fused Hybrid)
        active_mode = retrieval_mode
        if active_mode != "lexical_only" and self.semantic_retriever is None:
            active_mode = "lexical_only"

        raw_lexical: List[Dict[str, Any]] = []
        raw_semantic: List[SemanticCandidate] = []
        candidates: List[Dict[str, Any]] = []
        rescued_slugs: List[str] = []
        bm25f_retrieval_ms = 0.0
        dense_retrieval_ms = 0.0
        rrf_fusion_ms = 0.0

        if active_mode in ("hybrid", "lexical_only"):
            t_bm25 = time.perf_counter()
            raw_lexical = self.retriever.retrieve_candidates(effective_qrep, max_candidates=50)
            bm25f_retrieval_ms = round((time.perf_counter() - t_bm25) * 1000.0, 2)

        if active_mode in ("hybrid", "semantic_only"):
            t_dense = time.perf_counter()
            try:
                raw_semantic = self.semantic_retriever.retrieve_candidates(
                    query=analyzed_query.effective_query,
                    query_terms=analyzed_query.effective_content_terms,
                    max_candidates=50,
                )
            except Exception as exc:
                logging.getLogger(__name__).exception("semantic_retrieval_failed")
                semantic_error = f"{type(exc).__name__}: {exc}"
                raw_semantic = []
                if active_mode == "hybrid":
                    active_mode = "lexical_only"
            dense_retrieval_ms = round((time.perf_counter() - t_dense) * 1000.0, 2)

        if active_mode == "hybrid":
            t_fusion = time.perf_counter()
            fused = self.candidate_fuser.fuse(raw_lexical, raw_semantic, max_fused=50)
            rrf_fusion_ms = round((time.perf_counter() - t_fusion) * 1000.0, 2)
            for f in fused:
                doc_meta = self.index.documents.get(f.doc_id, f.doc_meta)
                bm25_data = f.bm25f_data
                if not bm25_data.get("bm25f_total") and f.bm25_score > 0:
                    bm25_data["bm25f_total"] = f.bm25_score

                cand_dict = {
                    "doc_id": f.doc_id,
                    "slug": f.slug,
                    "title": f.title,
                    "bm25f_data": bm25_data,
                    "preliminary_score": f.bm25_score,
                    "doc_meta": doc_meta,
                    "semantic_score": f.semantic_score,
                    "semantic_rank": f.semantic_rank,
                    "bm25_rank": f.bm25_rank,
                    "rrf_score": f.rrf_score,
                    "is_semantic_rescue": f.is_semantic_rescue,
                    "best_passage_text": f.best_passage_text,
                    "best_passage_id": f.best_passage_id,
                    "best_passage_score": f.best_passage_score,
                    "drift_penalty": f.drift_penalty,
                    "drift_reason": f.drift_reason,
                }
                if f.is_semantic_rescue:
                    rescued_slugs.append(f.slug)
                candidates.append(cand_dict)

        elif active_mode == "semantic_only":
            for rank, s in enumerate(raw_semantic, start=1):
                doc_meta = self.index.documents.get(s.doc_id, {})
                cand_dict = {
                    "doc_id": s.doc_id,
                    "slug": s.slug,
                    "title": s.title,
                    "bm25f_data": {
                        "bm25f_total": 0.0,
                        "title_score": 0.0,
                        "headings_score": 0.0,
                        "keywords_score": 0.0,
                        "meta_score": 0.0,
                        "body_score": 0.0,
                        "matched_terms": 0,
                        "total_query_terms": max(1, len(analyzed_query.effective_content_terms)),
                    },
                    "preliminary_score": s.semantic_score,
                    "doc_meta": doc_meta,
                    "semantic_score": s.semantic_score,
                    "semantic_rank": rank,
                    "bm25_rank": None,
                    "rrf_score": round(1.0 / (60 + rank), 6),
                    "is_semantic_rescue": True,
                    "best_passage_text": s.best_passage_text,
                    "best_passage_id": s.best_passage_id,
                    "best_passage_score": s.best_passage_score,
                    "drift_penalty": s.drift_penalty_applied,
                    "drift_reason": s.drift_reason,
                }
                rescued_slugs.append(s.slug)
                candidates.append(cand_dict)

        else:  # lexical_only
            for c in raw_lexical:
                c["semantic_score"] = 0.0
                c["semantic_rank"] = None
                c["bm25_rank"] = None
                c["rrf_score"] = 0.0
                c["is_semantic_rescue"] = False
                c["drift_penalty"] = 0.0
                c["drift_reason"] = None
                candidates.append(c)

        hybrid_trace = {
            "retrieval_mode": active_mode,
            "lexical_candidates_count": len(raw_lexical),
            "semantic_candidates_count": len(raw_semantic),
            "fused_candidates_count": len(candidates),
            "semantic_rescues_count": len(rescued_slugs),
            "rescued_slugs": rescued_slugs,
            "semantic_error": locals().get("semantic_error"),
        }

        # 4. Minimum Evidence Gating
        t_gate = time.perf_counter()
        passed_candidates, gate_decisions = self.evidence_gate.evaluate_candidates(
            candidates, analyzed_query
        )
        evidence_gating_ms = round((time.perf_counter() - t_gate) * 1000.0, 2)

        if not passed_candidates:
            total_empty_ms = round((time.perf_counter() - t_total_start) * 1000.0, 2)
            empty_timing = {
                "query_analysis_ms": query_analysis_ms,
                "bm25f_retrieval_ms": bm25f_retrieval_ms,
                "dense_retrieval_ms": dense_retrieval_ms,
                "rrf_fusion_ms": rrf_fusion_ms,
                "evidence_gating_ms": evidence_gating_ms,
                "ranking_scoring_ms": 0.0,
                "passage_scoring_ms": 0.0,
                "answer_extraction_ms": 0.0,
                "server_total_ms": total_empty_ms,
            }
            return SearchResultsList([], analyzed_query, gate_decisions, hybrid_trace, timing=empty_timing)

        # 5. Score and build traces for each eligible candidate
        t_scoring = time.perf_counter()
        passage_scoring_accum = 0.0
        decision_map = {d.doc_id: d for d in gate_decisions}
        scored_candidates = []

        for candidate in passed_candidates:
            doc_id = candidate["doc_id"]
            slug = candidate["slug"]
            doc_meta = self.index.documents.get(doc_id, candidate.get("doc_meta", {}))
            gate_decision = decision_map.get(doc_id)

            temp_doc = self._documents[doc_id]

            # Signal 1: BM25F Lexical Score
            bm25_data = candidate.get("bm25f_data", {})
            bm25f_score = bm25_data.get("bm25f_total", 0.0)

            # Signal 2: Field Signals
            title_sig = calculate_title_signal(temp_doc.title, effective_qrep)["title_signal"]
            heading_sig = calculate_heading_signal(temp_doc.get_all_headings(), effective_qrep)["heading_signal"]
            keyword_sig = calculate_keyword_signal(temp_doc.keywords, effective_qrep)["keyword_signal"]
            phrase_sig = calculate_phrase_signal(temp_doc.content, temp_doc.title, effective_qrep)["phrase_score"]

            # Signal 3: Passage Relevance
            t_psg = time.perf_counter()
            scored_passages = self.passage_scorer.score_passages_for_doc(slug, effective_qrep)
            passage_scoring_accum += (time.perf_counter() - t_psg)
            top_passage = scored_passages[0][0] if scored_passages else None
            top_passage_score = scored_passages[0][1] if scored_passages else 0.0

            # Signal 4: Dense Semantic Affinity & Rescued Passage
            semantic_score = candidate.get("semantic_score", 0.0)
            is_semantic_rescue = candidate.get("is_semantic_rescue", False)
            best_sem_passage_text = candidate.get("best_passage_text")
            best_sem_passage_score = candidate.get("best_passage_score", 0.0)

            if is_semantic_rescue and top_passage_score < 0.1 and best_sem_passage_score > 0.0:
                top_passage_score = best_sem_passage_score * 4.0

            # Signal 5: Coverage Gating
            matched_terms = bm25_data.get("matched_terms", 0)
            total_qterms = max(1, bm25_data.get("total_query_terms", 1))
            coverage_ratio = min(1.0, matched_terms / total_qterms)
            if is_semantic_rescue:
                # Semantic rescue was gated and approved by dense model for paraphrase
                coverage_factor = 0.60 + 0.40 * min(1.0, semantic_score)
            else:
                coverage_factor = 0.3 + 0.7 * coverage_ratio

            # Signal 6: Link Authority
            link_auth = self.link_authority.get_authority_score(slug)

            # Signal 7: Freshness
            freshness_data = calculate_freshness_signal(doc_meta)
            freshness_bonus = freshness_data["freshness_score"]

            # Signal 8: Content Quality
            quality_data = self._quality[doc_id]
            quality_bonus = quality_data["quality_score"]

            # Signal 9: Spam Penalty
            spam_data = self._spam[doc_id]
            spam_penalty = spam_data["spam_penalty"]

            # Mathematical Combination:
            # BM25F lexical + structural signals + dense semantic affinity
            base_relevance = (
                bm25f_score
                + (self.weights["title"] * title_sig)
                + (self.weights["heading"] * heading_sig)
                + (self.weights["passage"] * top_passage_score)
                + (self.weights["phrase"] * phrase_sig)
                + (self.weights["keyword"] * keyword_sig)
                + (self.weights["dense"] * semantic_score)
            )

            rrf_score = candidate.get("rrf_score", 0.0)
            if rrf_score > 0:
                base_relevance += self.weights["rrf"] * rrf_score

            ownership_factor = 1.0
            if re.search(r"\b(?:my|our)\b", analyzed_query.original_query, re.I):
                # Ownership is a query feature, never a hardcoded topic or slug.
                owned_title = bool(re.search(r"\b(?:my|our)\b", temp_doc.title, re.I))
                owned_body = bool(re.search(r"\b(?:my|our)\s+\w+", temp_doc.content, re.I))
                entity_terms, _, _ = answer_extractor.relevance_gate._extract_query_semantic_components(analyzed_query)
                title_entity = bool(entity_terms) and all(term_matches(t, temp_doc.title) for t in entity_terms)
                ownership_factor = 1.65 if owned_title and title_entity else (1.15 if owned_body and title_entity else 0.7)
            coverage_factor = coverage_factor ** self.weights["coverage"]
            relevance_gated = base_relevance * coverage_factor * ownership_factor
            positive_total = relevance_gated + link_auth + freshness_bonus + quality_bonus
            base_maae_score = round(max(0.0, positive_total * (1.0 - spam_penalty)), 4)

            # Search Sync preference signal adjustment (Phase N3-A)
            pref_adjustment = self.search_sync.get_preference_adjustment(
                normalized_query=normalized_sync_q,
                target_id=doc_id,
                target_slug=slug,
                active_map=active_preferences,
                target_type=TargetType.SERP_RESULT,
            )
            search_sync_adjustment = pref_adjustment.adjustment
            search_sync_feedback = pref_adjustment.feedback.value if pref_adjustment.feedback else None
            final_score = round(max(0.0, base_maae_score + search_sync_adjustment), 4)

            # Trace Audit Record
            trace = RankingTrace(
                doc_id=doc_id,
                slug=slug,
                title=temp_doc.title,
                retrieval_mode=active_mode,
                bm25_rank=candidate.get("bm25_rank"),
                semantic_rank=candidate.get("semantic_rank"),
                semantic_similarity=round(semantic_score, 4),
                rrf_score=round(rrf_score, 6),
                is_semantic_rescue=is_semantic_rescue,
                drift_penalty_applied=round(candidate.get("drift_penalty", 0.0), 4),
                drift_reason=candidate.get("drift_reason"),
                query_intent=analyzed_query.intent.value,
                content_terms=analyzed_query.effective_content_terms,
                effective_query=analyzed_query.effective_query,
                evidence_gate_passed=True,
                evidence_gate_reason=gate_decision.reason if gate_decision else "Passed",
                bm25f_lexical=round(bm25f_score, 4),
                bm25f_breakdown={
                    "title": round(bm25_data.get("title_score", 0.0), 4),
                    "headings": round(bm25_data.get("headings_score", 0.0), 4),
                    "keywords": round(bm25_data.get("keywords_score", 0.0), 4),
                    "meta_description": round(bm25_data.get("meta_score", 0.0), 4),
                    "body": round(bm25_data.get("body_score", 0.0), 4),
                },
                title_signal=round(title_sig, 4),
                heading_signal=round(heading_sig, 4),
                passage_signal=round(top_passage_score, 4),
                phrase_signal=round(phrase_sig, 4),
                keyword_signal=round(keyword_sig, 4),
                matched_query_terms=matched_terms,
                total_query_terms=total_qterms,
                coverage_ratio=round(coverage_ratio, 4),
                coverage_factor=round(coverage_factor, 4),
                ownership_factor=ownership_factor,
                link_authority=round(link_auth, 4),
                freshness_bonus=round(freshness_bonus, 4),
                quality_bonus=round(quality_bonus, 4),
                spam_penalty=round(spam_penalty, 4),
                spam_reasons=spam_data["reasons"],
                base_relevance=round(base_relevance, 4),
                relevance_gated=round(relevance_gated, 4),
                positive_total=round(positive_total, 4),
                base_score=base_maae_score,
                search_sync_adjustment=search_sync_adjustment,
                search_sync_feedback=search_sync_feedback,
                final_score=final_score,
            )

            # Snippet & Answer Extraction
            passage_text = (
                best_sem_passage_text
                if (is_semantic_rescue and best_sem_passage_text)
                else (top_passage.text if top_passage else temp_doc.content)
            )
            if is_semantic_rescue and best_sem_passage_text:
                top_passage = self.index.passages.get(candidate.get("best_passage_id"))

            snippet_dict = self.snippet_gen.generate_snippet(
                passage_text=passage_text,
                query_rep=effective_qrep,
                is_featured_candidate=True,
            )

            scored_candidates.append({
                "doc_id": doc_id,
                "slug": slug,
                "title": temp_doc.title,
                "top_passage": top_passage,
                "passage_text": passage_text,
                "top_passage_score": top_passage_score,
                "snippet_text": snippet_dict["snippet_text"],
                "snippet_html": snippet_dict["snippet_html"],
                "source_type": temp_doc.source_type,
                "word_count": doc_meta.get("raw_word_count", 0),
                "in_links_count": self.link_authority.graph.in_degree(slug),
                "base_score": base_maae_score,
                "search_sync_adjustment": search_sync_adjustment,
                "search_sync_feedback": search_sync_feedback,
                "final_score": final_score,
                "is_semantic_rescue": is_semantic_rescue,
                "semantic_similarity": round(semantic_score, 4),
                "rrf_score": round(rrf_score, 6),
                "trace": trace,
            })

        scoring_total_ms = (time.perf_counter() - t_scoring) * 1000.0
        passage_scoring_ms = round(passage_scoring_accum * 1000.0, 2)
        ranking_scoring_ms = round(max(0.0, scoring_total_ms - (passage_scoring_accum * 1000.0)), 2)

        # Neural influence is unavailable until a signed, independently accepted
        # relevance model is installed. Existing Rel-0 cannot pass that gate.
        neural_ranking_trace = self.neural_ranker.adjust(scored_candidates, analyzed_query.effective_query or query,
                                                       enabled=self._neural_search_enabled())
        hybrid_trace["neural_ranking"] = neural_ranking_trace
        # 6. Sort descending by Final Score
        scored_candidates.sort(key=lambda x: x["final_score"], reverse=True)

        # 7. Generalized Featured Answer Selection for Top #1 result
        t_ans = time.perf_counter()
        top_item = scored_candidates[0] if scored_candidates else None
        featured_answer = None
        featured_justification = None
        is_featured = False

        if top_item:
            # Check for Search Sync Featured Answer suppression for this query
            fa_suppressed, fa_event = self.search_sync.check_featured_answer_suppression(
                normalized_query=normalized_sync_q,
                doc_id=top_item["doc_id"]
            )
            if fa_suppressed:
                featured_answer = None
                featured_justification = f"Suppressed by Search Sync user dislike preference for '{normalized_sync_q}'"
                is_featured = False
            else:
                source_passages = self.passage_scorer.score_passages_for_doc(top_item["slug"], effective_qrep)
                selected = list(source_passages[:3])
                selected_ids = {p.passage_id for p, _, _ in selected}
                selected.extend([(p, score, breakdown) for p, score, breakdown in source_passages
                                 if p.block_type == "faq" and p.passage_id not in selected_ids][:4])
                answer_text, justification = answer_extractor.extract_source_answer(
                    analyzed_query=analyzed_query,
                    passages=[{"text": p.text, "heading": p.heading_context or "", "id": p.passage_id, "score": score}
                              for p, score, _ in selected],
                    title=top_item["title"], document_score=top_item["final_score"],
                )
                if answer_text:
                    featured_answer = answer_text
                    featured_justification = justification
                    is_featured = True
        answer_extraction_ms = round((time.perf_counter() - t_ans) * 1000.0, 2)

        # Record Answer Relevance audit on top candidate trace
        relevance_audit = None
        if answer_extractor.last_relevance_result:
            lr = answer_extractor.last_relevance_result
            if scored_candidates:
                scored_candidates[0]["trace"].answer_relevance_verdict = lr.decision
                scored_candidates[0]["trace"].answer_relevance_failure = lr.failure_class
                scored_candidates[0]["trace"].answer_relevance_score = lr.final_entailment
            relevance_audit = {
                "verdict": lr.decision,
                "failure_class": lr.failure_class,
                "score": lr.final_entailment,
                "entity_alignment": lr.entity_alignment,
                "predicate_alignment": lr.predicate_alignment,
                "property_alignment": lr.property_alignment,
                "answer_type_alignment": lr.answer_type_alignment,
                "semantic_support": lr.semantic_support,
                "reason": lr.reason,
                "negation_preserved": lr.negation_preserved,
                "debug_lines": lr.debug_lines,
            }

        # 7.5 PESE-QA-0 Neural Reading Comprehension (Shadow Mode)
        t_qa = time.perf_counter()
        qa_trace = None
        qa_candidates_count = 0
        qa_reader = self._get_qa_reader() if not skip_qa else None
        if not skip_qa and qa_reader and scored_candidates:
            candidate_passages = []
            top_retrieval_score = scored_candidates[0]["final_score"] if scored_candidates else 1.0

            # Candidate passage budgeting: max 3 passages total across top candidates
            # Priority 1: Top result #1 (1 or 2 highest-scoring passages)
            # Priority 2: Result #2 (top passage if score within 40% of top result)
            for c_idx, cand in enumerate(scored_candidates[:2]):
                if cand["final_score"] < (top_retrieval_score * 0.40):
                    continue
                qa_candidates_count += 1
                slug = cand["slug"]
                doc_id = cand["doc_id"]
                final_score = cand["final_score"]
                spam_penalty = cand.get("trace").spam_penalty if cand.get("trace") else 0.0

                all_psgs = self.passage_scorer.score_passages_for_doc(slug, effective_qrep)
                if all_psgs:
                    # For rank 1 take top 2 passages; for rank 2 take top 1
                    psg_budget = 2 if c_idx == 0 else 1
                    for p, p_score, _ in all_psgs[:psg_budget]:
                        if len(candidate_passages) >= 3:
                            break
                        p_text = f"## {p.heading_context}\n{p.text}" if (getattr(p, "heading_context", None) and not p.text.startswith("#")) else p.text
                        candidate_passages.append({
                            "passage_text": p_text,
                            "doc_id": doc_id,
                            "slug": slug,
                            "final_score": final_score,
                            "passage_score": p_score,
                            "spam_penalty": spam_penalty,
                        })
                else:
                    if len(candidate_passages) < 3:
                        candidate_passages.append({
                            "passage_text": cand["passage_text"],
                            "doc_id": doc_id,
                            "slug": slug,
                            "final_score": final_score,
                            "passage_score": cand.get("top_passage_score", 1.0),
                            "spam_penalty": spam_penalty,
                        })

                if len(candidate_passages) >= 3:
                    break

            try:
                qa_res = qa_reader.read_candidate_passages(analyzed_query.effective_query, candidate_passages)
            except Exception as exc:
                from ..neural.inference.qa_reader import QAResult
                logging.getLogger(__name__).exception("qa_inference_failed")
                qa_res = QAResult(abstention_reason=f"QA failure: {type(exc).__name__}", trace={"error":str(exc)})

            agreement = "NO"
            if featured_answer and qa_res.answer:
                if featured_answer.lower() in qa_res.answer.lower() or qa_res.answer.lower() in featured_answer.lower():
                    agreement = "YES"
                else:
                    agreement = "NO"
            elif not featured_answer and not qa_res.answer:
                agreement = "BOTH_ABSTAIN"
            else:
                agreement = "NO"

            import torch
            thread_count = torch.get_num_threads() if hasattr(torch, "get_num_threads") else 2

            qa_trace = {
                "model": "PESE-QA-0",
                "query": analyzed_query.original_query,
                "deterministic_answer": featured_answer,
                "shadow_answer": qa_res.answer,
                "is_answerable": qa_res.answerable,
                "confidence": qa_res.answer_confidence,
                "start_confidence": qa_res.start_confidence,
                "end_confidence": qa_res.end_confidence,
                "source_passage": qa_res.source_passage[:250] if qa_res.source_passage else None,
                "source_doc_id": qa_res.source_doc_id,
                "source_slug": qa_res.source_slug,
                "start_char": qa_res.start_char,
                "end_char": qa_res.end_char,
                "agreement": agreement,
                "execution_ms": round((time.perf_counter() - t_qa) * 1000.0, 2),
                "qa_candidates": qa_candidates_count,
                "qa_passages_budgeted": len(candidate_passages),
                "qa_windows_created": qa_res.trace.get("windows_created", 1),
                "qa_forward_passes": qa_res.trace.get("forward_passes", 1),
                "qa_cache_hit": qa_res.trace.get("cache_hits", 0) > 0,
                "qa_early_exit": qa_res.trace.get("early_exit", False),
                "model_reused": True,
                "torch_threads": thread_count,
                "answer_relevance": relevance_audit,
                "error": qa_res.trace.get("error"),
            }

            if scored_candidates:
                scored_candidates[0]["trace"].qa_shadow_answer = qa_res.answer
                scored_candidates[0]["trace"].qa_agreement = agreement
                scored_candidates[0]["trace"].qa_confidence = qa_res.answer_confidence

        qa_shadow_ms = round((time.perf_counter() - t_qa) * 1000.0, 2) if not skip_qa else 0.0

        # 7.6 PESE-Rel-0 Neural Relation Shadow Observer (Phase N3-B — Authority: NONE)
        t_shadow = time.perf_counter()
        shadow_candidate_items: List[Dict[str, Any]] = []
        if self.shadow_adapter.is_enabled() and scored_candidates:
            # Candidate Budget: Top 3 organic documents, up to 2 passages per document (max 6)
            for cand in scored_candidates[:3]:
                cand_slug = cand["slug"]
                cand_doc_id = cand["doc_id"]
                cand_psgs = self.passage_scorer.score_passages_for_doc(cand_slug, effective_qrep)
                if cand_psgs:
                    for p, _, _ in cand_psgs[:2]:
                        p_text = f"## {p.heading_context}\n{p.text}" if (getattr(p, "heading_context", None) and not p.text.startswith("#")) else p.text
                        shadow_candidate_items.append({
                            "target_id": cand_doc_id,
                            "target_slug": cand_slug,
                            "target_type": "SERP_RESULT",
                            "evidence_id": p.passage_id,
                            "evidence_text": p_text,
                            "source_text": p.text,
                        })
                elif cand.get("passage_text"):
                    shadow_candidate_items.append({
                        "target_id": cand_doc_id,
                        "target_slug": cand_slug,
                        "target_type": "SERP_RESULT",
                        "evidence_id": f"{cand_slug}#p0",
                        "evidence_text": cand["passage_text"],
                    })

            # Also budget Featured Answer candidate evidence if present
            if featured_answer and scored_candidates:
                top_cand = scored_candidates[0]
                fa_ev_text = featured_answer
                if fa_ev_text:
                    shadow_candidate_items.append({
                        "target_id": top_cand["doc_id"],
                        "target_slug": top_cand["slug"],
                        "target_type": "FEATURED_ANSWER",
                        "evidence_id": f"{top_cand['slug']}#fa",
                        "evidence_text": fa_ev_text,
                    })

        for evidence in shadow_candidate_items:
            from ..intelligence.evidence import digest
            candidate = next(c for c in scored_candidates if c["doc_id"] == evidence["target_id"])
            receipt = self._evidence_receipt(candidate, search_ctx_id, analyzed_query.effective_query or query)
            receipt.update(target_type=evidence["target_type"], evidence_id=evidence["evidence_id"],
                           evidence_hash=digest(evidence.get("source_text", evidence["evidence_text"])),
                           model_input_hash=digest(evidence["evidence_text"]))
            evidence["provenance"] = receipt
        shadow_summaries, shadow_observations = self.shadow_adapter.observe_candidates(
            query=analyzed_query.effective_query or query,
            normalized_query=normalized_sync_q,
            search_context_id=search_ctx_id,
            candidate_items=shadow_candidate_items,
            active_feedback_map=active_preferences,
        )

        # Persist observations to Search Sync store (fail-open)
        if shadow_observations:
            try:
                self.search_sync.store.record_neural_observations(shadow_observations)
            except Exception as store_exc:
                logging.getLogger(__name__).warning("Failed to record neural observations: %s", store_exc)

        neural_shadow_ms = round((time.perf_counter() - t_shadow) * 1000.0, 2)

        # 8. Compile SearchResult objects
        results: List[SearchResult] = []
        for idx, item in enumerate(scored_candidates[:limit]):
            is_item_featured = is_featured if idx == 0 else False
            item_featured_justification = featured_justification if (is_item_featured or (idx == 0 and featured_justification)) else None

            # Attach neural shadow summary to trace and SearchResult (Authority: NONE)
            item_shadow_summary = shadow_summaries.get(item["doc_id"])
            if item_shadow_summary:
                item["trace"].rel_shadow_answers_prob = item_shadow_summary.answers_probability
                item["trace"].rel_shadow_does_not_answer_prob = item_shadow_summary.does_not_answer_probability
                item["trace"].rel_shadow_label = item_shadow_summary.predicted_label
                item["trace"].rel_shadow_evidence_id = item_shadow_summary.best_evidence_id
                item["trace"].rel_shadow_evidence_count = item_shadow_summary.evidence_count
                item["trace"].rel_shadow_authority = item_shadow_summary.authority
                item["trace"].rel_shadow_alignment = item_shadow_summary.alignment
                item["trace"].rel_shadow_status = item_shadow_summary.status

            results.append(
                SearchResult(
                    rank=idx + 1,
                    doc_id=item["doc_id"],
                    slug=item["slug"],
                    title=item["title"],
                    snippet_text=item["snippet_text"],
                    snippet_html=item["snippet_html"],
                    featured_answer=featured_answer if is_item_featured else None,
                    featured_justification=item_featured_justification,
                    is_featured=is_item_featured,
                    source_type=item["source_type"],
                    word_count=item["word_count"],
                    in_links_count=item["in_links_count"],
                    base_score=item.get("base_score", item["final_score"]),
                    search_sync_adjustment=item.get("search_sync_adjustment", 0.0),
                    neural_adjustment=item.get("neural_adjustment", 0.0),
                    search_sync_feedback=item.get("search_sync_feedback"),
                    final_score=item["final_score"],
                    is_semantic_rescue=item["is_semantic_rescue"],
                    semantic_similarity=item["semantic_similarity"],
                    rrf_score=item["rrf_score"],
                    trace=item["trace"],
                    answer_audit={
                        "source_slug": item["slug"],
                        "source_passage": item["passage_text"],
                        "source_passage_id": item["top_passage"].passage_id if item["top_passage"] else None,
                        "producer": "bounded_deterministic_v2",
                        "candidate_span": answer_extractor.last_relevance_result.candidate if answer_extractor.last_relevance_result else None,
                        "validation": relevance_audit,
                        "pipeline_v2": answer_extractor.pipeline_audit,
                        "arbitration_reason": featured_justification or justification if top_item else "No candidates",
                        "abstained": not is_item_featured,
                        "qa_status": "skipped" if skip_qa else (self._qa_error or "shadow_only"),
                        "neural_shadow_observation": next((o.model_dump() for o in shadow_observations if o.target_type == "FEATURED_ANSWER"), None),
                    } if idx == 0 else {},
                    neural_shadow=item_shadow_summary.model_dump() if item_shadow_summary else None,
                    evidence_provenance=self._evidence_receipt(item, search_ctx_id, analyzed_query.effective_query or query),
                    learning_evidence_text=item["passage_text"],
                )
            )

        neural_shadow_trace = {
            "model_id": "PESE-Rel-0",
            "checkpoint_hash": self.shadow_adapter.checkpoint_hash,
            "authority": "NONE",
            "status": "OK" if shadow_observations else ("DISABLED" if not self.shadow_adapter.is_enabled() else "NO_CANDIDATES"),
            "candidates_budgeted": len(shadow_candidate_items),
            "candidates_evaluated": len(shadow_observations),
            "search_context_id": search_ctx_id,
            "latency_ms": neural_shadow_ms,
        }

        total_server_ms = round((time.perf_counter() - t_total_start) * 1000.0, 2)
        timing = {
            "query_analysis_ms": query_analysis_ms,
            "bm25f_retrieval_ms": bm25f_retrieval_ms,
            "dense_retrieval_ms": dense_retrieval_ms,
            "rrf_fusion_ms": rrf_fusion_ms,
            "evidence_gating_ms": evidence_gating_ms,
            "ranking_scoring_ms": ranking_scoring_ms,
            "passage_scoring_ms": passage_scoring_ms,
            "answer_extraction_ms": answer_extraction_ms,
            "qa_shadow_ms": qa_shadow_ms,
            "neural_shadow_ms": neural_shadow_ms,
            "server_total_ms": total_server_ms,
        }

        return SearchResultsList(results, analyzed_query, gate_decisions, hybrid_trace, timing=timing, qa_trace=qa_trace, neural_shadow_trace=neural_shadow_trace)

    def _evidence_receipt(self, item, context_id, effective_query):
        from ..intelligence.evidence import digest, RANKING_VERSION
        document = self._documents[item["doc_id"]].model_dump()
        document.pop("indexed_at", None)
        return {"version": 1, "context_id": context_id, "effective_query": effective_query,
                "target_type": "SERP_RESULT", "target_id": item["doc_id"],
                "document_revision": digest(document),
                "evidence_id": item["top_passage"].passage_id if item["top_passage"] else item["slug"] + "#document",
                "evidence_hash": digest(item["passage_text"]), "ranking_version": RANKING_VERSION,
                "generation": str(self.index_versions.get("document_version") or digest(sorted(self._documents))),
                "model_versions": {"relation": "PESE-Rel-0:shadow:" + self.shadow_adapter.checkpoint_hash,
                    "ranking": item["trace"].neural_model_version or "deterministic_maae"}}

    def _neural_search_enabled(self):
        # A settings flag cannot install a model or bypass release acceptance.
        if not self.neural_ranker.available:
            return False
        from ..intelligence.settings import intelligence_settings
        return intelligence_settings.read().neural_search
