"""
PESE Semantic: Embedding Provider
Abstract base class and local fastembed/ONNX dense embedding provider.
Zero remote APIs. Zero cloud dependencies.
"""

import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union, Optional
import numpy as np
import hashlib
from functools import lru_cache
from threading import RLock


class EmbeddingProvider(ABC):
    """Abstract interface for local embedding inference engines."""

    @abstractmethod
    def embed_query(self, query: str) -> np.ndarray:
        """Generate a 1D normalized float32 vector for a search query."""
        pass

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Generate a 2D normalized float32 matrix (N, D) for a batch of texts."""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return provider and model inspection details."""
        pass


class FastembedProvider(EmbeddingProvider):
    """
    Local ONNX-based embedding provider using fastembed and bge-small-en-v1.5.
    Ultra-lightweight (384 dimensions, ~65MB ONNX quantized), running entirely on CPU.
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", cache_dir: Optional[str] = None):
        self.model_name = model_name
        self.cache_dir = cache_dir or os.getenv("PESE_FASTEMBED_CACHE")
        self._model = None
        self._dim = 384
        self._lock = RLock()

    def _ensure_model(self):
        with self._lock:
            self._initialize_model()

    def _initialize_model(self):
        if self._model is None:
            try:
                from fastembed import TextEmbedding
                # Desktop supplies the exact proven ONNX files, with no hub lookup.
                # Development retains its existing cache/download behavior.
                local_path = os.getenv("PESE_FASTEMBED_MODEL_PATH")
                desktop_options = {"specific_model_path": local_path, "local_files_only": True} if local_path else {}
                self._model = TextEmbedding(model_name=self.model_name, cache_dir=self.cache_dir, threads=2, **desktop_options)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to initialize local Fastembed model '{self.model_name}': {e}"
                )

    def embed_query(self, query: str) -> np.ndarray:
        return self._cached_query(query.strip()).copy()

    @lru_cache(maxsize=256)
    def _cached_query(self, query: str) -> np.ndarray:
        self._ensure_model()
        cleaned = query.strip()
        if not cleaned:
            # Zero vector fallback
            return np.zeros(self._dim, dtype=np.float32)

        # Fastembed query embedding
        # bge models benefit from query prefix or standard passage embed
        embs = list(self._model.embed([cleaned]))
        vec = np.array(embs[0], dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 1e-9:
            vec = vec / norm
        return vec

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        self._ensure_model()
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)

        # Batch embed
        embs = list(self._model.embed(texts))
        matrix = np.array(embs, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.where(norms > 1e-9, norms, 1.0)
        matrix = matrix / norms
        return matrix

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "provider_type": "fastembed_onnx_local",
            "model_name": self.model_name,
            "vector_dimension": self._dim,
            "device": "cpu",
            "normalized": True,
        }


class DeterministicMockProvider(EmbeddingProvider):
    """
    Fast deterministic hashing embedding provider for headless unit testing.
    Produces repeatable normalized vectors based on token hashes without downloading models.
    """

    def __init__(self, dimension: int = 384):
        self._dim = dimension

    def _hash_text(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dim, dtype=np.float32)
        tokens = text.lower().split()
        if not tokens:
            return vec
        for i, token in enumerate(tokens):
            idx = int.from_bytes(hashlib.blake2b(token.encode(),digest_size=8).digest(),"big") % self._dim
            vec[idx] += 1.0 / (1.0 + (i * 0.1))
        norm = np.linalg.norm(vec)
        if norm > 1e-9:
            vec = vec / norm
        return vec

    def embed_query(self, query: str) -> np.ndarray:
        return self._hash_text(query)

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)
        matrix = np.vstack([self._hash_text(t) for t in texts])
        return matrix

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "provider_type": "deterministic_mock",
            "model_name": "mock-hash-384",
            "vector_dimension": self._dim,
            "device": "cpu",
            "normalized": True,
        }
