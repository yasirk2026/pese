"""
PESE Semantic Retrieval Subsystem
Provides local dense embeddings, incremental vector indexing, semantic retrieval,
drift detection, and hybrid candidate fusion (BM25F + Dense).
"""

from .provider import EmbeddingProvider, FastembedProvider, DeterministicMockProvider
from .models import (
    PassageVectorMeta,
    DocumentVectorMeta,
    SemanticCandidate,
    FusedCandidate,
    SemanticDiagnostics,
)
from .index import VectorIndex
from .drift import SemanticDriftDetector
from .retriever import SemanticRetriever
from .fusion import HybridCandidateFuser

__all__ = [
    "EmbeddingProvider",
    "FastembedProvider",
    "DeterministicMockProvider",
    "PassageVectorMeta",
    "DocumentVectorMeta",
    "SemanticCandidate",
    "FusedCandidate",
    "SemanticDiagnostics",
    "VectorIndex",
    "SemanticDriftDetector",
    "SemanticRetriever",
    "HybridCandidateFuser",
]
