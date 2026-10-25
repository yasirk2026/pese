"""
PESE Engine: FastAPI Service
Local search engine API connecting Next.js frontend with Python information retrieval pipeline.
"""

import time
import json
import hashlib
import logging
import os
from threading import RLock
from collections import OrderedDict
from uuid import uuid4
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..brain.profile import (
    load_profile,
    save_profile,
    import_avatar,
    remove_avatar,
    get_avatar_file,
    UserProfile
)

from ..sync import (
    GoogleDriveSyncService,
    SyncStatus,
    SyncConfigurationError,
    SyncAuthenticationError,
    SyncNetworkError,
    RestoreFailedError,
)
from ..indexing.document import Document
from ..indexing.store import DocumentStore
from ..indexing.snapshot import SearchSnapshot, SnapshotStore, document_generation
from ..indexing.inverted_index import InvertedIndex
from ..passages.extractor import PassageExtractor
from ..link_graph.graph import LinkGraph
from ..link_graph.authority import LinkAuthorityCalculator
from ..ranking.scorer import RankingEngine, SearchResult, RankingTrace
from ..ranking.explain import compare_traces
from ..data.seed_corpus import seed_corpus
from ..data.demo_corpus import seed_demo
from ..config import DEMO, RUNTIME_ROOT
from ..evaluation.runner import run_evaluation
from ..evaluation.discovery_runner import run_discovery_evaluation
try:
    from ..evaluation.answer_relevance_runner import run_answer_relevance_evaluation as _run_ar_eval
    _has_ar_runner = True
except ImportError:
    _has_ar_runner = False

# Semantic System Imports
from ..semantic.index import VectorIndex
from ..semantic.provider import FastembedProvider
from ..semantic.models import SemanticDiagnostics

# Discovery System Imports
from ..discovery.models import (
    AutocompleteSuggestion,
    SuggestResponse,
    RelatedSearchItem,
    RelatedSearchesResponse,
    PAAQuestionItem,
    QuestionsResponse,
    QuerySessionEvent,
)
from ..discovery.history import SearchHistoryStore, LocalHistoryStore
from ..discovery.sessions import SessionManager
from ..discovery.families import QueryFamilyRegistry
from ..discovery.autocomplete import AutocompleteEngine
from ..discovery.related_searches import RelatedSearchEngine
from ..discovery.questions import PAAQuestionEngine
from ..discovery.priority import primary_request

# Neural Genesis Imports
from ..neural.models.registry import registry as neural_registry
from ..neural.training.checkpoint import list_checkpoints, load_checkpoint, DEFAULT_CHECKPOINT_DIR
from ..neural.data.contracts import export_faqs_to_qa_contracts
from ..neural.inference.generator import NeuralGenerator
from ..neural.tokenization.bpe_tokenizer import BPETokenizer
from ..neural.data.dataset import SYNTHETIC_PUBLIC_CORPUS

# Search Sync Imports (Phase N3-A)
from ..search_sync.contracts import FeedbackSubmission, FeedbackEvent, FeedbackType, TargetType
from ..search_sync.feedback_store import feedback_store, SearchSyncFeedbackStore
from ..search_sync.preference_signal import preference_signal, normalize_sync_query

# Global state instances
store = DocumentStore()
index = InvertedIndex()
extractor = PassageExtractor()
graph = LinkGraph()
link_auth = LinkAuthorityCalculator(graph)
vector_index = VectorIndex()
engine: Optional[RankingEngine] = None
pipeline_lock = RLock()
active_snapshot: Optional[SearchSnapshot] = None
publication_state = {"dirty": False, "stage": "startup", "last_error": None}
BOOT_ID = uuid4().hex
discovery_contexts = OrderedDict()
discovery_lock = RLock()


def discovery_context(query, search_id=None):
    if search_id:
        with discovery_lock:
            context = discovery_contexts.get(search_id)
        if not context or context[0] != query:
            raise HTTPException(409, detail="Search context expired; repeat the primary search.")
        return context[1], context[2]
    # Standalone API callers still use real retrieval, never fabricated suggestions.
    snapshot = serving_snapshot()
    slugs = snapshot.engine.cached_primary_slugs(query)
    if not slugs:
        slugs = [result.slug for result in snapshot.engine.search(query, limit=5, skip_qa=True)]
    return snapshot, slugs


# Global Discovery Instances
history_store = LocalHistoryStore()
session_manager = SessionManager(history_store)
family_registry = QueryFamilyRegistry()
autocomplete_engine: Optional[AutocompleteEngine] = None
related_engine: Optional[RelatedSearchEngine] = None
paa_engine: Optional[PAAQuestionEngine] = None

EVENTS_LOG_PATH = RUNTIME_ROOT / "behavioural_events.jsonl"


def reload_search_pipeline() -> None:
    with pipeline_lock:
        publication_state.update(dirty=True, last_error=None)
        try:
            _reload_search_pipeline()
            publication_state.update(dirty=False, stage="ready", last_error=None)
        except Exception as exc:
            publication_state["last_error"] = type(exc).__name__
            logging.getLogger(__name__).exception("index_publication_failed stage=%s", publication_state["stage"])
            raise


def _reload_search_pipeline() -> None:
    """Reload all published documents, build inverted index, build vector index, and compute graph authority."""
    global index, graph, link_auth, engine, vector_index, autocomplete_engine, related_engine, paa_engine, family_registry, active_snapshot
    docs = store.list_documents(status="published")
    from ..startup_progress import emit_progress
    emit_progress("lexical", 0, len(docs))
    publication_state["stage"] = "lexical_passages"
    new_index = InvertedIndex()
    passages_by_doc = {}
    for doc in docs:
        passages = extractor.extract_passages(doc)
        passages_by_doc[doc.id] = passages
        new_index.index_document(doc, passages)

    # Incrementally build dense vector index
    # Build a new vector snapshot so in-flight searches retain a consistent
    # lexical/passage/vector generation while the CMS publishes the next one.
    next_vectors = VectorIndex(provider=vector_index.provider, index_dir=vector_index.index_dir)
    publication_state["stage"] = "semantic"
    next_vectors._hash_cache = dict(vector_index._hash_cache)
    next_vectors.build_index(docs, passages_by_doc, persist=False)

    publication_state["stage"] = "graph"
    new_graph = LinkGraph()
    new_graph.build_from_documents(docs)
    new_auth = LinkAuthorityCalculator(new_graph)
    new_auth.compute_scores()

    previous_reader = engine._qa_reader if engine else None
    frozen_store = SnapshotStore(docs)
    next_engine = RankingEngine(new_index, new_auth, vector_index=next_vectors, doc_store=frozen_store)
    next_engine._qa_reader = previous_reader
    generation = document_generation(docs)
    next_engine.index_versions = {name:generation for name in ("document_version","lexical_index_version","semantic_index_version","passage_index_version","faq_index_version","graph_version")}
    publication_state["stage"] = "discovery_faq"
    next_families = QueryFamilyRegistry.from_documents(docs)

    # Initialize Discovery engines
    next_autocomplete = AutocompleteEngine(
        store=frozen_store,
        spelling_corrector=next_engine.spelling_corrector,
        history_store=history_store,
        session_manager=session_manager,
        family_registry=next_families,
    )
    next_related = RelatedSearchEngine(
        store=frozen_store,
        graph=new_graph,
        history_store=history_store,
        session_manager=session_manager,
        family_registry=next_families,
    )
    next_paa = PAAQuestionEngine(
        store=frozen_store,
        ranking_engine=next_engine,
        family_registry=next_families,
    )
    publication_state["stage"] = "validate"
    assert set(new_index.documents) == {d.id for d in docs}
    assert set(p.doc_id for p in next_vectors.passage_meta) <= set(new_index.documents)
    assert len(next_vectors.passage_meta) == len(new_index.passages)
    # This is a rebuildable, content-hashed local cache, never snapshot payload.
    # Persist only a fully validated generation, without mutating serving arrays.
    publication_state["cache_persisted"] = next_vectors._save_cache()
    emit_progress("finalizing", len(docs), len(docs))
    # The only serving publication. Every request captures this pointer once.
    active_snapshot = SearchSnapshot(generation, next_engine, new_index, next_vectors,
                                    new_graph, new_auth, next_autocomplete, next_related, next_paa)
    # Compatibility aliases for laboratory tools; serving reads the snapshot.
    index, vector_index, graph, link_auth, engine = new_index, next_vectors, new_graph, new_auth, next_engine
    autocomplete_engine, related_engine, paa_engine = next_autocomplete, next_related, next_paa
    family_registry = next_families


def serving_snapshot():
    snapshot = active_snapshot
    if snapshot is None or publication_state["dirty"]:
        raise HTTPException(503, detail={"code": "INDEX_NOT_CURRENT", "publication": dict(publication_state),
                                        "recovery": "Retry POST /api/index after resolving the rebuild error"})
    return snapshot


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure documents are present, seed if empty
    existing = store.list_documents()
    if not existing and DEMO:
        seed_demo(store)
    reload_search_pipeline()

    # Optimal CPU thread configuration for resident inference
    try:
        import torch
        torch.set_num_threads(2)
    except Exception as e:
        print(f"Torch thread config warning: {e}")

    # Prewarm ONNX embedding model to guarantee instant sub-100ms first search
    try:
        if vector_index and hasattr(vector_index, "provider"):
            vector_index.provider.embed_query("pese startup prewarm query")
    except Exception as e:
        raise RuntimeError("The local semantic model could not initialize; search is not ready.") from e

    # Neural QA is a laboratory opt-in, never a production startup dependency.
    try:
        if engine and os.getenv("PESE_PREWARM_QA") == "1":
            reader = engine._get_qa_reader()
            if reader:
                reader.read_passage("warmup question", "warmup passage evidence for resident model")
    except Exception as e:
        print(f"Startup PESE-QA prewarm warning: {e}")

    from ..startup_progress import emit_progress
    emit_progress("ready", len(store.list_documents()), len(store.list_documents()))
    yield


app = FastAPI(
    title="PESE — Personal Evil Search Engine API 😈",
    version="2.0.0-rc.1",
    description="Local Python information retrieval, fielded BM25F, passage indexing, and explainable ranking engine.",
    lifespan=lifespan,
)

# CORS configured for Next.js local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== SCHEMAS ====================

class SearchResponse(BaseModel):
    search_id: str = ""
    boot_id: str = ""
    index_versions: Dict[str, str] = Field(default_factory=dict)
    query: str
    effective_query: str
    has_corrections: bool
    correction_confidence: str
    corrections: List[Dict[str, Any]] = Field(default_factory=list)
    query_analysis: Dict[str, Any] = Field(default_factory=dict)
    rejected_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    hybrid_trace: Dict[str, Any] = Field(default_factory=dict)
    timing: Dict[str, float] = Field(default_factory=dict)
    qa_trace: Optional[Dict[str, Any]] = None
    neural_shadow_trace: Optional[Dict[str, Any]] = None
    total_results: int
    took_ms: float
    results: List[SearchResult]


class EventPayload(BaseModel):
    event_type: str  # 'query_submitted', 'result_clicked', 'position_clicked', 'dwell_time', 'reformulated'
    session_id: Optional[str] = None
    query: Optional[str] = None
    target_slug: Optional[str] = None
    rank_position: Optional[int] = None
    dwell_seconds: Optional[float] = None
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ==================== SEARCH ENDPOINTS ====================

@app.get("/health")
def health_check():
    canonical = document_generation(store.list_documents(status="published"))
    snapshot = active_snapshot
    current = bool(snapshot and snapshot.generation == canonical and not publication_state["dirty"])
    return {
        "status": "healthy" if current else "degraded",
        "service": "PESE Search Engine",
        "boot_id": BOOT_ID,
        "storage_backend": "firestore" if store.use_firestore else "local",
        "canonical_document_version": canonical,
        "publication": dict(publication_state),
        "index_versions": snapshot.engine.index_versions if snapshot else {},
        "documents_indexed": snapshot.index.total_docs if snapshot else 0,
        "passages_indexed": len(snapshot.index.passages) if snapshot else 0,
        "vector_passages_indexed": len(snapshot.vectors.passage_meta) if snapshot else 0,
    }


@app.get("/api/brain/info")
def get_brain_info():
    """Return read-only metadata about the currently bound PESE Brain."""
    try:
        from ..brain.lifecycle import open_brain
        info = open_brain(RUNTIME_ROOT)
        data = info.model_dump(mode="json")
        data["document_count"] = len(store.list_documents())
        return data
    except Exception:
        return {
            "brain_id": "local",
            "name": "Local Brain",
            "path": str(RUNTIME_ROOT),
            "status": "active",
            "document_count": len(store.list_documents()),
            "schema_version": 1,
            "created_at": "",
        }


# ==================== PROFILE / ACCOUNT ENDPOINTS ====================

class ProfileUpdateRequest(BaseModel):
    display_name: str = "Local User"
    about: str = ""


class AvatarUploadRequest(BaseModel):
    image_base64: str
    filename: Optional[str] = "avatar.png"


@app.get("/api/profile", response_model=UserProfile)
def get_user_profile():
    """Get the local owner profile stored with the active Brain."""
    return load_profile(RUNTIME_ROOT)


@app.post("/api/profile", response_model=UserProfile)
def update_user_profile(payload: ProfileUpdateRequest):
    """Update user display name and about biography."""
    return save_profile(payload.display_name, payload.about, RUNTIME_ROOT)


@app.post("/api/profile/avatar", response_model=UserProfile)
async def upload_user_avatar(payload: AvatarUploadRequest):
    """Import and set a new profile avatar from base64 into portable Brain storage."""
    import base64
    raw_b64 = payload.image_base64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]
    try:
        image_bytes = base64.b64decode(raw_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image data") from exc
    return import_avatar(image_bytes, payload.filename or "avatar.png", RUNTIME_ROOT)


@app.delete("/api/profile/avatar", response_model=UserProfile)
def delete_user_avatar():
    """Remove avatar image from Brain-owned storage."""
    return remove_avatar(RUNTIME_ROOT)


@app.get("/api/profile/avatar")
def get_user_avatar():
    """Serve the active avatar image from portable Brain storage."""
    avatar_file = get_avatar_file(RUNTIME_ROOT)
    if not avatar_file or not avatar_file.exists():
        raise HTTPException(status_code=404, detail="No avatar found")
    media_type = "image/png"
    if avatar_file.suffix.lower() in [".jpg", ".jpeg"]:
        media_type = "image/jpeg"
    elif avatar_file.suffix.lower() == ".webp":
        media_type = "image/webp"
    elif avatar_file.suffix.lower() == ".gif":
        media_type = "image/gif"
    return FileResponse(avatar_file, media_type=media_type, headers={"Cache-Control": "no-cache"})



@app.get("/api/search", response_model=SearchResponse)
def search_documents(
    q: str = Query(..., description="Search query string"),
    session_id: Optional[str] = Query(None, description="Optional search session ID"),
    limit: int = Query(20, ge=1, le=100),
    debug: bool = Query(False, description="Include full ranking traces"),
    force_raw: bool = Query(False, description="Bypass typo correction"),
    mode: str = Query("hybrid", description="Retrieval mode: 'hybrid', 'lexical_only', or 'semantic_only'"),
):
    """Execute end-to-end PESE hybrid retrieval, query analysis, gating, and ranking."""
    if not engine:
        raise HTTPException(status_code=503, detail="Search engine initializing")

    start_time = time.perf_counter()
    search_id = uuid4().hex
    snapshot = serving_snapshot()
    active_engine = snapshot.engine
    with primary_request():
        ranked_results = active_engine.search(q, limit=limit, force_raw=force_raw, retrieval_mode=mode, skip_qa=not debug, search_context_id=search_id)
    with discovery_lock:
        discovery_contexts[search_id] = (q, snapshot, [result.slug for result in ranked_results[:5]])
        while len(discovery_contexts) > 64:
            discovery_contexts.popitem(last=False)
    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    qa = getattr(ranked_results, "query_analysis", None)
    qa_dict = qa.model_dump() if qa else {}
    rejected = getattr(ranked_results, "rejected_candidates", [])
    ht = getattr(ranked_results, "hybrid_trace", {})
    timing_data = dict(getattr(ranked_results, "timing", {}))
    timing_data["server_total_ms"] = elapsed_ms

    if session_id:
        session_manager.record_session_event(
            QuerySessionEvent(
                session_id=session_id,
                event_type="query_submitted",
                query=q,
                effective_query=qa.effective_query if qa else q,
            )
        )

    logging.getLogger("uvicorn.error").info(json.dumps({"search_id":search_id,"total_ms":elapsed_ms,"candidate_count":len(ranked_results),"abstained":not bool(ranked_results and ranked_results[0].is_featured),"qa_requested":debug,"index_version":active_engine.index_versions.get("document_version")}))
    return SearchResponse(
        search_id=search_id,
        boot_id=BOOT_ID,
        index_versions=active_engine.index_versions,
        query=q,
        effective_query=qa.effective_query if qa else q,
        has_corrections=qa.has_corrections if qa else False,
        correction_confidence=qa.correction_confidence if qa else "NONE",
        corrections=[c.model_dump() for c in qa.corrections] if qa else [],
        query_analysis=qa_dict,
        rejected_candidates=rejected,
        hybrid_trace=ht,
        timing=timing_data,
        qa_trace=getattr(ranked_results, "qa_trace", None),
        neural_shadow_trace=getattr(ranked_results, "neural_shadow_trace", None),
        total_results=len(ranked_results),
        took_ms=elapsed_ms,
        results=ranked_results,
    )


# ==================== SEMANTIC SYSTEM ENDPOINTS ====================

@app.get("/api/semantic/diagnostics", response_model=SemanticDiagnostics)
def get_semantic_diagnostics():
    """Return model, dimension, passage count, document count, and caching statistics."""
    if not vector_index:
        raise HTTPException(status_code=503, detail="Semantic subsystem initializing")
    return vector_index.get_diagnostics()


@app.post("/api/semantic/reindex")
def reindex_semantic():
    """Force re-indexing of semantic vectors and report cache timing."""
    start = time.perf_counter()
    reload_search_pipeline()
    elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
    return {
        "status": "reindexed",
        "took_ms": elapsed_ms,
        "diagnostics": vector_index.get_diagnostics().model_dump(),
    }


@app.get("/api/explain")
def explain_ranking(
    q: str = Query(..., description="Query used for comparison"),
    winner: str = Query(..., description="Slug of winning document"),
    loser: str = Query(..., description="Slug of losing document"),
):
    """Compare two ranking traces and explain why Document A outranked Document B."""
    if not engine:
        raise HTTPException(status_code=503, detail="Search engine initializing")

    results = engine.search(q, limit=50)
    trace_winner = next((r.trace for r in results if r.slug == winner), None)
    trace_loser = next((r.trace for r in results if r.slug == loser), None)

    if not trace_winner:
        raise HTTPException(status_code=404, detail=f"Document '{winner}' not found in candidate pool")
    if not trace_loser:
        raise HTTPException(status_code=404, detail=f"Document '{loser}' not found in candidate pool")

    comparison = compare_traces(trace_winner, trace_loser)
    return comparison


@app.get("/api/stats")
def get_engine_stats():
    """Return index stats, graph topology, and dictionary summaries."""
    return {
        "total_documents": index.total_docs,
        "total_passages": len(index.passages),
        "total_terms": len(index.index),
        "avg_field_lengths": index.avg_field_lengths,
        "graph_nodes": len(graph.nodes),
        "graph_edges": sum(len(edges) for edges in graph.adj_list.values()),
    }


# ==================== CMS & DOCUMENT MANAGEMENT ====================

@app.get("/api/documents")
def list_documents(status: Optional[str] = None):
    """List documents from store."""
    return store.list_documents(status=status)


@app.get("/api/documents/{slug}")
def get_document(slug: str):
    """Get single document by slug."""
    doc = store.get_by_slug(slug) or store.get_document(slug)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    # Attach link details
    link_details = link_auth.get_doc_link_details(doc.slug)
    return {
        **doc.to_dict(),
        "link_details": link_details,
    }


@app.post("/api/documents")
def save_document(doc_data: dict = Body(...)):
    """Create or update document in canonical store and trigger index update."""
    doc = Document.from_dict(doc_data)
    with pipeline_lock:
        saved = store.save_document(doc)
        try:
            reload_search_pipeline()
        except Exception:
            raise HTTPException(503, detail={"code": "SAVED_NOT_INDEXED", "saved_id": saved.id,
                                            "publication": dict(publication_state)})
    return saved


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    """Delete document by ID or slug."""
    with pipeline_lock:
        success = store.delete_document(doc_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        try:
            reload_search_pipeline()
        except Exception:
            raise HTTPException(503, detail={"code": "DELETED_NOT_INDEXED", "publication": dict(publication_state)})
    return {"status": "deleted", "id": doc_id}


@app.post("/api/index")
def reindex_all():
    """Trigger full reindexing of all published documents."""
    start = time.perf_counter()
    reload_search_pipeline()
    ms = round((time.perf_counter() - start) * 1000.0, 2)
    return {
        "status": "reindexed",
        "documents_indexed": index.total_docs,
        "passages_indexed": len(index.passages),
        "took_ms": ms,
    }


@app.post("/api/seed")
def reseed_database():
    """Reset / seed the evil testing universe."""
    docs = seed_demo(store) if DEMO else seed_corpus(store)
    reload_search_pipeline()
    return {"status": "seeded", "count": len(docs)}


# ==================== DISCOVERY ENDPOINTS ====================

@app.get("/api/suggest", response_model=SuggestResponse)
def get_autocomplete_suggestions(
    q: str = Query(..., description="Query prefix string"),
    session_id: Optional[str] = Query(None, description="Optional search session ID"),
    limit: int = Query(6, ge=1, le=20),
    debug: bool = Query(False, description="Include detailed scoring traces"),
):
    """
    Generate instant typo-aware, corpus-derived, and session-informed suggestions.
    Designed for sub-millisecond local debounce keystrokes.
    """
    if not autocomplete_engine:
        raise HTTPException(status_code=503, detail="Autocomplete engine initializing")
    return serving_snapshot().autocomplete.get_suggestions(
        raw_prefix=q,
        limit=limit,
        session_id=session_id,
        debug=debug,
    )


@app.get("/api/related", response_model=RelatedSearchesResponse)
def get_related_searches(
    q: str = Query(..., description="Query string"),
    session_id: Optional[str] = Query(None, description="Optional search session ID"),
    search_id: Optional[str] = Query(None, description="Primary search generation context"),
    limit: int = Query(5, ge=1, le=10),
    debug: bool = Query(False, description="Include scoring traces"),
):
    """
    Surface topically coherent related search queries grounded in link graph
    neighborhoods, query reformulation patterns, and document headings.
    """
    if not related_engine or not engine:
        raise HTTPException(status_code=503, detail="Related searches engine initializing")

    # Evaluate search to extract top candidate slugs for link neighborhood (skip heavy QA on discovery auxiliary endpoints)
    snapshot, top_slugs = discovery_context(q, search_id)
    if not top_slugs:
        return RelatedSearchesResponse(query=q, related_searches=[], took_ms=0.0)

    return snapshot.related.get_related_searches(
        query=q,
        top_slugs=top_slugs,
        limit=limit,
        debug=debug,
    )


@app.get("/api/questions", response_model=QuestionsResponse)
def get_you_might_also_ask(
    q: str = Query(..., description="Query string"),
    session_id: Optional[str] = Query(None, description="Optional search session ID"),
    search_id: Optional[str] = Query(None, description="Primary search generation context"),
    limit: int = Query(4, ge=1, le=10),
    debug: bool = Query(False, description="Include answerability traces"),
):
    """
    'You Might Also Ask' (PAA): Evaluates grounded candidate questions
    through the Answerability Gate and surfaces pre-extracted passage answers.
    """
    if not paa_engine or not engine:
        raise HTTPException(status_code=503, detail="PAA questions engine initializing")

    snapshot, top_slugs = discovery_context(q, search_id)
    if not top_slugs:
        return QuestionsResponse(query=q, questions=[], took_ms=0.0, total_candidates_evaluated=0, total_passed_gate=0)

    return snapshot.questions.get_questions_for_query(
        query=q,
        top_slugs=top_slugs,
        limit=limit,
        debug=debug,
    )


@app.post("/api/session/event")
def record_session_event(event: QuerySessionEvent):
    """Record discovery interaction telemetry (autocomplete, PAA open, related clicks)."""
    session_manager.record_session_event(event)
    return {"status": "recorded", "event_type": event.event_type, "session_id": event.session_id}


@app.get("/api/history")
def get_search_history(
    limit: int = Query(15, ge=1, le=100),
    session_id: Optional[str] = Query(None),
):
    """Retrieve private user search history."""
    return {
        "history_enabled": history_store.is_history_enabled(),
        "recent_searches": history_store.get_recent_searches(limit=limit, session_id=session_id),
        "total_unique_queries": len(history_store.get_query_frequencies()),
    }


@app.delete("/api/history")
def clear_search_history():
    """Clear all stored behavioural query history."""
    history_store.clear_history()
    return {"status": "cleared"}


@app.post("/api/history/settings")
def update_history_settings(payload: Dict[str, Any] = Body(...)):
    """Toggle search history collection setting."""
    enabled = payload.get("history_enabled", True)
    history_store.set_history_enabled(enabled)
    return {"status": "updated", "history_enabled": history_store.is_history_enabled()}


# ==================== BEHAVIOURAL LEARNING DATA CONTRACT ====================

@app.post("/api/events")
def record_event(payload: EventPayload):
    """
    Ingest behavioural telemetry events (query, click, position, dwell).
    Saved to disk for future learning-to-rank models (Phase 2).
    STRICTLY PASSIVE in Phase 1: Does NOT affect deterministic rankings.
    """
    # Route through session manager & history store
    qse = QuerySessionEvent(
        session_id=payload.session_id or "default-session",
        event_type=payload.event_type,
        query=payload.query,
        target_slug=payload.target_slug,
        rank_position=payload.rank_position,
        timestamp=payload.timestamp,
        metadata={**payload.metadata, "dwell_seconds": payload.dwell_seconds},
    )
    session_manager.record_session_event(qse)
    return {"status": "recorded", "event": payload.event_type}


# ==================== SEARCH SYNC FEEDBACK ENDPOINTS (Phase N3-A) ====================

@app.post("/api/search/feedback")
def submit_search_feedback(submission: FeedbackSubmission):
    """
    Submits user preference feedback (LIKE / DISLIKE) on an organic SERP result
    or a Featured Answer. Bounded preference signal is saved locally and immediately
    influences next search for the same query.
    """
    normalized_q = preference_signal.normalize_query(submission.query)
    if not normalized_q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if not submission.target_id.strip():
        raise HTTPException(status_code=400, detail="Target ID cannot be empty")

    event = FeedbackEvent(
        query=submission.query,
        normalized_query=normalized_q,
        target_type=submission.target_type,
        target_id=submission.target_id.strip(),
        target_slug=submission.target_slug,
        rank_position=submission.rank_position,
        feedback=submission.feedback,
        reason=submission.reason,
        search_context_id=submission.search_context_id,
        metadata=submission.metadata,
    )
    recorded = feedback_store.record_feedback(event)

    # Invalidate cache for this query in serving engine so next search immediately reflects feedback
    if active_snapshot and active_snapshot.engine:
        active_snapshot.engine.invalidate_query_cache(submission.query)
    if engine:
        engine.invalidate_query_cache(submission.query)

    pref_adj = preference_signal.get_preference_adjustment(
        normalized_query=normalized_q,
        target_id=submission.target_id.strip(),
        target_slug=submission.target_slug,
        target_type=submission.target_type,
    )

    return {
        "status": "success",
        "event_id": recorded.event_id,
        "query": recorded.query,
        "normalized_query": recorded.normalized_query,
        "target_type": recorded.target_type.value,
        "target_id": recorded.target_id,
        "feedback": recorded.feedback.value,
        "reason": recorded.reason,
        "search_sync_adjustment": pref_adj.adjustment,
        "created_at": recorded.created_at,
    }


@app.get("/api/search/feedback")
def list_search_feedback(q: Optional[str] = Query(None, description="Optional query to filter feedback")):
    """Inspect active Search Sync feedback preferences."""
    if q:
        norm_q = preference_signal.normalize_query(q)
        prefs = feedback_store.get_active_preferences_for_query(norm_q)
        return {
            "query": q,
            "normalized_query": norm_q,
            "preferences": {k: v.model_dump() for k, v in prefs.items()}
        }
    all_prefs = feedback_store.list_all_active_preferences()
    return {
        "total_active_preferences": len(all_prefs),
        "preferences": [p.model_dump() for p in all_prefs]
    }


@app.delete("/api/search/feedback")
def clear_search_feedback():
    """Development / Test fixture: resets all Search Sync feedback memory."""
    feedback_store.clear_all()
    if active_snapshot and active_snapshot.engine:
        active_snapshot.engine.invalidate_query_cache()
    if engine:
        engine.invalidate_query_cache()
    return {"status": "cleared", "detail": "All Search Sync feedback memory reset"}


# ==================== PHASE N3-B: NEURAL SHADOW ENDPOINTS ====================

@app.get("/api/search/neural-shadow")
def get_neural_shadow_records(
    q: Optional[str] = Query(None, description="Optional query to filter joined observations")
):
    """
    Developer audit view: Returns joined records of MAAE decisions,
    PESE-Rel-0 neural shadow observations, and human feedback preferences.
    """
    records = feedback_store.get_feedback_with_neural_observations(query=q)
    return {
        "model_id": "PESE-Rel-0",
        "authority": "NONE",
        "total_records": len(records),
        "records": records,
    }


@app.get("/api/search/neural-shadow/stats")
def get_neural_shadow_statistics():
    """
    Developer telemetry view: Returns aggregate shadow observation statistics
    and neural/human agreement/disagreement rates.
    """
    stats = feedback_store.get_neural_shadow_statistics()
    return stats


# ==================== EVALUATION ENDPOINT ====================

@app.get("/api/benchmark")
def run_benchmark():
    """Execute scientific evaluation suite and return IR metrics."""
    if not engine:
        raise HTTPException(status_code=503, detail="Search engine initializing")
    summary = run_evaluation(engine=engine)
    return summary


@app.get("/api/discovery/benchmark")
def run_discovery_benchmark_endpoint():
    """Execute Phase 2A discovery benchmark suite (Autocomplete, PAA, Related)."""
    summary = run_discovery_evaluation()
    return summary


@app.get("/api/answer-relevance/benchmark")
def run_answer_relevance_benchmark():
    """Execute Phase 2D.2 Answer Relevance Gate benchmark suite and return metrics."""
    if not _has_ar_runner:
        raise HTTPException(status_code=503, detail="Answer relevance evaluation runner not available.")
    return _run_ar_eval()


# ==================== NEURAL GENESIS LABORATORY API ====================

class NeuralGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=500)
    max_new_tokens: int = Field(20, ge=1, le=100)
    temperature: float = Field(0.8, ge=0.0, le=2.0)
    top_k: int = Field(40, ge=1, le=100)


# Lazy cached inference generator for PESE-NG-0
_cached_generator: Optional[NeuralGenerator] = None

def get_neural_generator() -> Optional[NeuralGenerator]:
    global _cached_generator
    if _cached_generator is not None:
        return _cached_generator

    chk_path = DEFAULT_CHECKPOINT_DIR / "peseng0_baseline_final.pt"
    if not chk_path.exists():
        # Fallback to any step100 checkpoint if available
        chk_path = DEFAULT_CHECKPOINT_DIR / "PESE-NG-0_step100.pt"

    if not chk_path.exists():
        return None

    try:
        model, _ = load_checkpoint(chk_path, device="cpu")
        tok = BPETokenizer()
        tok.train(SYNTHETIC_PUBLIC_CORPUS, target_vocab_size=model.config.vocab_size, min_frequency=2)
        _cached_generator = NeuralGenerator(model, tok)
        return _cached_generator
    except Exception as e:
        print(f"Failed to load cached neural generator: {e}")
        return None


@app.get("/api/neural/registry")
def get_neural_registry():
    """Return catalog of registered PESE neural architectures and their lifecycle states."""
    models = neural_registry.list_models()
    return {"models": [m.model_dump() for m in models]}


@app.get("/api/neural/experiments")
def get_neural_experiments():
    """Return scientific report and telemetry from Neural Genesis experiments."""
    report_file = Path(__file__).resolve().parent.parent / "data" / "neural_genesis_report.json"
    if not report_file.exists():
        return {"status": "pending", "message": "Neural Genesis experiment report has not been generated yet."}
    
    with open(report_file, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/neural/checkpoints")
def get_neural_checkpoints():
    """List saved PyTorch neural checkpoints with step, loss, and file metadata."""
    checkpoints = list_checkpoints(DEFAULT_CHECKPOINT_DIR)
    return {"checkpoints": checkpoints}


@app.get("/api/neural/qa-contracts")
def get_qa_contracts():
    """
    Export current indexed documents into structured QAExample contracts
    ready for future PESE-QA-0 extractive question answering and abstention.
    """
    all_docs = [d.to_dict() for d in store.list_documents()]
    qa_contracts = export_faqs_to_qa_contracts(all_docs, include_negative_abstentions=True)
    return {
        "count": len(qa_contracts),
        "contracts": [q.model_dump() for q in qa_contracts]
    }


@app.post("/api/neural/generate")
def neural_generate(payload: NeuralGenerateRequest):
    """
    Experimental text completion endpoint using PESE-NG-0 Transformer.
    Tagged with strict experimental disclaimer. Zero influence on search rankings.
    """
    gen = get_neural_generator()
    if gen is None:
        raise HTTPException(
            status_code=503,
            detail="PESE-NG-0 model checkpoint not loaded. Run neural experiment suite first."
        )

    res = gen.generate(
        prompt=payload.prompt,
        max_new_tokens=payload.max_new_tokens,
        temperature=payload.temperature,
        top_k=payload.top_k
    )
    return res


# ==================== PESE-QA-0 READING LABORATORY API ====================

class QAReadRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=300)
    passage: str = Field(..., min_length=5, max_length=3000)
    answerability_threshold: float = Field(0.50, ge=0.0, le=1.0)


@app.get("/api/neural/qa/report")
def get_qa_report():
    """Return latest PESE-QA-0 reading comprehension experiment report."""
    report_file = Path(__file__).resolve().parent.parent / "data" / "qa_experiment_report.json"
    if not report_file.exists():
        return {"status": "pending", "message": "PESE-QA experiment report has not been generated yet."}
    with open(report_file, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/neural/qa/read")
def qa_read_passage(payload: QAReadRequest):
    """
    Run PESE-QA-0 reading comprehension reader on a question + passage pair.
    Returns exact answer span, start/end char offsets, confidence, and abstention status.
    """
    qa_reader = engine._get_qa_reader() if engine else None
    if qa_reader is None:
        raise HTTPException(
            status_code=503,
            detail="PESE-QA-0 reader checkpoint not loaded. Run QA experiments first."
        )

    res = qa_reader.read_passage(payload.question, payload.passage)
    return res.model_dump()


# ==================== GOOGLE DRIVE SYNC ENDPOINTS ====================

_sync_service: Optional[GoogleDriveSyncService] = None
_sync_service_lock = RLock()


def get_sync_service() -> GoogleDriveSyncService:
    global _sync_service
    with _sync_service_lock:
        if _sync_service is None:
            _sync_service = GoogleDriveSyncService(brain_path=RUNTIME_ROOT)
        return _sync_service


class RestoreRequestBody(BaseModel):
    snapshot_id: Optional[str] = None


@app.get("/api/sync/status", response_model=SyncStatus)
def api_get_sync_status():
    """Get current Google Drive synchronization status."""
    service = get_sync_service()
    return service.get_status()


@app.post("/api/sync/connect")
def api_sync_connect():
    """Initiate desktop Google OAuth PKCE authorization flow."""
    service = get_sync_service()
    try:
        return service.start_oauth_flow(open_browser=True)
    except SyncConfigurationError as cfg_err:
        raise HTTPException(status_code=400, detail=str(cfg_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start Google OAuth flow: {exc}")


@app.post("/api/sync/disconnect")
def api_sync_disconnect():
    """Disconnect Google Drive and clear local credentials while preserving Brain."""
    service = get_sync_service()
    try:
        return service.disconnect()
    except SyncAuthenticationError as exc:
        raise HTTPException(409, detail=str(exc))


@app.post("/api/sync/now")
def api_sync_now():
    """Create a safe snapshot of the local Brain and upload to Google Drive."""
    service = get_sync_service()
    try:
        return service.sync_now()
    except SyncAuthenticationError as auth_err:
        raise HTTPException(status_code=401, detail=str(auth_err))
    except SyncNetworkError as net_err:
        raise HTTPException(status_code=503, detail=str(net_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sync failed: {exc}")


@app.post("/api/sync/restore")
def api_sync_restore(body: Optional[RestoreRequestBody] = None):
    from ..sync.service import RESTORE_DISABLED_REASON
    raise HTTPException(409, detail=RESTORE_DISABLED_REASON)


@app.get("/api/sync/snapshots")
def api_get_sync_snapshots():
    """List available PESE snapshots stored in Google Drive appDataFolder."""
    service = get_sync_service()
    try:
        snapshots = service.list_remote_snapshots()
        return {"snapshots": snapshots}
    except SyncAuthenticationError as auth_err:
        raise HTTPException(status_code=401, detail=str(auth_err))
    except SyncNetworkError as net_err:
        raise HTTPException(status_code=503, detail=str(net_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
