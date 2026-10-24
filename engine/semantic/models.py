"""
PESE Semantic: Data Models
Data structures for semantic passages, document embeddings, hybrid candidates, and traces.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PassageVectorMeta(BaseModel):
    """Metadata associated with an indexed passage vector."""
    passage_id: str
    doc_id: str
    slug: str
    title: str
    heading: Optional[str] = None
    text: str
    content_hash: str
    vector_idx: int


class DocumentVectorMeta(BaseModel):
    """Metadata associated with an indexed document-level vector."""
    doc_id: str
    slug: str
    title: str
    content_hash: str
    vector_idx: int


class SemanticCandidate(BaseModel):
    """A candidate document retrieved via dense vector similarity."""
    doc_id: str
    slug: str
    title: str
    semantic_score: float              # Cosine similarity [0.0, 1.0]
    best_passage_id: Optional[str] = None
    best_passage_text: Optional[str] = None
    best_passage_score: float = 0.0
    doc_similarity: float = 0.0
    semantic_rank: int = 0
    is_semantic_rescue: bool = False
    drift_penalty_applied: float = 0.0
    drift_reason: Optional[str] = None


class FusedCandidate(BaseModel):
    """Unified candidate resulting from reciprocal rank fusion of lexical and semantic signals."""
    doc_id: str
    slug: str
    title: str
    bm25_rank: Optional[int] = None
    semantic_rank: Optional[int] = None
    bm25_score: float = 0.0
    semantic_score: float = 0.0
    rrf_score: float = 0.0
    is_semantic_rescue: bool = False
    best_passage_id: Optional[str] = None
    best_passage_text: Optional[str] = None
    best_passage_score: float = 0.0
    drift_penalty: float = 0.0
    drift_reason: Optional[str] = None
    doc_meta: Dict[str, Any] = Field(default_factory=dict)
    bm25f_data: Dict[str, Any] = Field(default_factory=dict)


class SemanticDiagnostics(BaseModel):
    """Inspection metadata for the active semantic indexing subsystem."""
    provider_name: str
    model_name: str
    vector_dimension: int
    total_passages_indexed: int
    total_documents_indexed: int
    cache_hits: int
    cache_misses: int
    index_path: str
    last_indexed_at: str
