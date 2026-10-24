"""
PESE Semantic: Vector Index
Manages passage and document dense vectors, incremental hashing cache, persistence,
and fast local dot-product similarity search.
"""

import os
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
import numpy as np

from .models import PassageVectorMeta, DocumentVectorMeta, SemanticDiagnostics
from .provider import EmbeddingProvider, FastembedProvider
from ..indexing.document import Document
from ..indexing.passage import Passage
from ..config import RUNTIME_ROOT


DEFAULT_INDEX_DIR = RUNTIME_ROOT / "semantic_index"


class VectorIndex:
    """
    Local Vector Index storing float32 normalized embeddings.
    Features incremental rebuilding via SHA256 content hashing to avoid
    re-embedding unchanged passages.
    """

    def __init__(
        self,
        provider: Optional[EmbeddingProvider] = None,
        index_dir: Optional[Path] = None,
    ):
        self.provider = provider or FastembedProvider()
        self.index_dir = index_dir or DEFAULT_INDEX_DIR
        self.index_dir.mkdir(parents=True, exist_ok=True)

        # In-memory vector arrays (normalized float32)
        self.passage_vectors: np.ndarray = np.empty((0, 384), dtype=np.float32)
        self.passage_meta: List[PassageVectorMeta] = []
        self.doc_vectors: np.ndarray = np.empty((0, 384), dtype=np.float32)
        self.doc_meta: List[DocumentVectorMeta] = []

        # Content hash persistent cache: hash -> 1D vector
        self._hash_cache: Dict[str, np.ndarray] = {}
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.last_indexed_at: str = ""

        # Load existing cache if present
        self._load_cache()

    def _hash_passage(self, doc_id: str, heading: Optional[str], text: str) -> str:
        raw = f"v2|{self.provider.get_metadata()}|{doc_id}|{heading or ''}|{text.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _hash_document(self, doc: Document) -> str:
        raw = f"v2|{self.provider.get_metadata()}|{doc.id}|{self._document_text(doc)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _document_text(doc: Document) -> str:
        return f"{doc.title}. {doc.meta_description or ''}. Keywords: {', '.join(doc.keywords)}. {doc.content[:600]}"

    def _load_cache(self) -> None:
        cache_file = self.index_dir / "cache_store.npz"
        if cache_file.exists():
            try:
                npz = np.load(cache_file, allow_pickle=False)
                for k in npz.files:
                    self._hash_cache[k] = npz[k]
            except Exception as e:
                print(f"[VectorIndex] Warning: Failed to load cache_store.npz: {e}")

    def _save_cache(self) -> None:
        cache_file = self.index_dir / "cache_store.npz"
        try:
            np.savez_compressed(cache_file, **self._hash_cache)
        except Exception as e:
            print(f"[VectorIndex] Warning: Failed to save cache_store.npz: {e}")

    def build_index(
        self,
        documents: List[Document],
        passages_by_doc: Dict[str, List[Passage]],
        persist: bool = True,
    ) -> None:
        """
        Build or incrementally update vectors for all documents and passages.
        Uses content hashing to embed only new or modified entries.
        """
        new_passage_meta: List[PassageVectorMeta] = []
        new_passage_vectors: List[np.ndarray] = []

        new_doc_meta: List[DocumentVectorMeta] = []
        new_doc_vectors: List[np.ndarray] = []

        # 1. Process Passages
        passages_to_embed: List[Tuple[int, str, Passage]] = []  # (index, text, passage)
        passage_counter = 0

        for doc in documents:
            doc_passages = passages_by_doc.get(doc.id, [])
            for p in doc_passages:
                chash = self._hash_passage(doc.id, p.heading_context, p.text)
                meta = PassageVectorMeta(
                    passage_id=p.passage_id,
                    doc_id=doc.id,
                    slug=doc.slug,
                    title=doc.title,
                    heading=p.heading_context,
                    text=p.text,
                    content_hash=chash,
                    vector_idx=passage_counter,
                )
                new_passage_meta.append(meta)

                if chash in self._hash_cache:
                    new_passage_vectors.append(self._hash_cache[chash])
                    self.cache_hits += 1
                else:
                    embed_text = f"{p.heading_context + ': ' if p.heading_context else ''}{p.text}"
                    passages_to_embed.append((passage_counter, embed_text, p))
                    new_passage_vectors.append(None)  # Placeholder
                    self.cache_misses += 1

                passage_counter += 1

        # Embed passage cache misses
        if passages_to_embed:
            texts = [item[1] for item in passages_to_embed]
            embedded_matrix = self.provider.embed_texts(texts)
            for idx, (p_idx, text, p) in enumerate(passages_to_embed):
                vec = embedded_matrix[idx]
                meta = new_passage_meta[p_idx]
                self._hash_cache[meta.content_hash] = vec
                new_passage_vectors[p_idx] = vec

        # 2. Process Document level summaries
        docs_to_embed: List[Tuple[int, str, Document]] = []
        doc_counter = 0

        for doc in documents:
            chash = self._hash_document(doc)
            meta = DocumentVectorMeta(
                doc_id=doc.id,
                slug=doc.slug,
                title=doc.title,
                content_hash=chash,
                vector_idx=doc_counter,
            )
            new_doc_meta.append(meta)

            if chash in self._hash_cache:
                new_doc_vectors.append(self._hash_cache[chash])
                self.cache_hits += 1
            else:
                summary_text = self._document_text(doc)
                docs_to_embed.append((doc_counter, summary_text, doc))
                new_doc_vectors.append(None)
                self.cache_misses += 1

            doc_counter += 1

        # Embed document cache misses
        if docs_to_embed:
            texts = [item[1] for item in docs_to_embed]
            embedded_matrix = self.provider.embed_texts(texts)
            for idx, (d_idx, text, doc) in enumerate(docs_to_embed):
                vec = embedded_matrix[idx]
                meta = new_doc_meta[d_idx]
                self._hash_cache[meta.content_hash] = vec
                new_doc_vectors[d_idx] = vec

        # Finalize numpy arrays
        dim = self.provider.get_metadata().get("vector_dimension", 384)
        if new_passage_vectors:
            self.passage_vectors = np.vstack(new_passage_vectors).astype(np.float32)
        else:
            self.passage_vectors = np.empty((0, dim), dtype=np.float32)

        if new_doc_vectors:
            self.doc_vectors = np.vstack(new_doc_vectors).astype(np.float32)
        else:
            self.doc_vectors = np.empty((0, dim), dtype=np.float32)

        self.passage_meta = new_passage_meta
        self.doc_meta = new_doc_meta
        self.last_indexed_at = datetime.now(timezone.utc).isoformat()

        # Retain only vectors in this generation; removed/edited content must
        # not cause an ever-growing private-content cache.
        active_hashes = {m.content_hash for m in new_passage_meta + new_doc_meta}
        self._hash_cache = {k:v for k,v in self._hash_cache.items() if k in active_hashes}

        # Persist to disk
        if persist:
            self._save_cache()
            self.save_to_disk()

    def save_to_disk(self) -> None:
        """Persist vector index and metadata to disk."""
        np.save(self.index_dir / "passage_vectors.npy", self.passage_vectors)
        np.save(self.index_dir / "doc_vectors.npy", self.doc_vectors)

        with open(self.index_dir / "passage_meta.json", "w", encoding="utf-8") as f:
            json.dump([m.model_dump() for m in self.passage_meta], f, indent=2)

        with open(self.index_dir / "doc_meta.json", "w", encoding="utf-8") as f:
            json.dump([m.model_dump() for m in self.doc_meta], f, indent=2)

        meta = {
            "provider_metadata": self.provider.get_metadata(),
            "total_passages": len(self.passage_meta),
            "total_documents": len(self.doc_meta),
            "last_indexed_at": self.last_indexed_at,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
        }
        with open(self.index_dir / "index_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    def load_from_disk(self) -> bool:
        """Load persisted vector arrays and metadata if available."""
        p_vec_file = self.index_dir / "passage_vectors.npy"
        d_vec_file = self.index_dir / "doc_vectors.npy"
        p_meta_file = self.index_dir / "passage_meta.json"
        d_meta_file = self.index_dir / "doc_meta.json"
        meta_file = self.index_dir / "index_meta.json"

        if not (p_vec_file.exists() and d_vec_file.exists() and p_meta_file.exists() and d_meta_file.exists()):
            return False

        try:
            self.passage_vectors = np.load(p_vec_file)
            self.doc_vectors = np.load(d_vec_file)

            with open(p_meta_file, "r", encoding="utf-8") as f:
                raw_pm = json.load(f)
                self.passage_meta = [PassageVectorMeta(**item) for item in raw_pm]

            with open(d_meta_file, "r", encoding="utf-8") as f:
                raw_dm = json.load(f)
                self.doc_meta = [DocumentVectorMeta(**item) for item in raw_dm]

            if meta_file.exists():
                with open(meta_file, "r", encoding="utf-8") as f:
                    idx_meta = json.load(f)
                    self.last_indexed_at = idx_meta.get("last_indexed_at", "")
                    self.cache_hits = idx_meta.get("cache_hits", 0)
                    self.cache_misses = idx_meta.get("cache_misses", 0)

            return True
        except Exception as e:
            print(f"[VectorIndex] Failed to load index from disk: {e}")
            return False

    def search_passages(
        self,
        query_vec: np.ndarray,
        top_k: int = 50,
    ) -> List[Tuple[PassageVectorMeta, float]]:
        """Compute cosine similarity against all indexed passages and return top-k."""
        if len(self.passage_vectors) == 0:
            return []

        # Cosine similarity via dot product of normalized vectors
        scores = np.dot(self.passage_vectors, query_vec)
        top_k = min(top_k, len(scores))
        if top_k <= 0:
            return []

        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(self.passage_meta[i], float(scores[i])) for i in top_indices]

    def search_documents(
        self,
        query_vec: np.ndarray,
        top_k: int = 50,
    ) -> List[Tuple[DocumentVectorMeta, float]]:
        """Compute cosine similarity against all indexed documents and return top-k."""
        if len(self.doc_vectors) == 0:
            return []

        scores = np.dot(self.doc_vectors, query_vec)
        top_k = min(top_k, len(scores))
        if top_k <= 0:
            return []

        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(self.doc_meta[i], float(scores[i])) for i in top_indices]

    def get_diagnostics(self) -> SemanticDiagnostics:
        prov_meta = self.provider.get_metadata()
        return SemanticDiagnostics(
            provider_name=prov_meta.get("provider_type", "unknown"),
            model_name=prov_meta.get("model_name", "unknown"),
            vector_dimension=prov_meta.get("vector_dimension", 384),
            total_passages_indexed=len(self.passage_meta),
            total_documents_indexed=len(self.doc_meta),
            cache_hits=self.cache_hits,
            cache_misses=self.cache_misses,
            index_path=str(self.index_dir),
            last_indexed_at=self.last_indexed_at,
        )
