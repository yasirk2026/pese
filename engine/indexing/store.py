"""
PESE Indexing: Document Store
Abstraction layer for Firestore persistence with local fallback.
Provides identical CRUD semantics whether running against Google Cloud Firestore,
the local Firestore Emulator, or local JSON document storage.
"""

from ..brain.coordination import canonical_write

import os
import json
import logging
from threading import RLock
from pathlib import Path
from typing import List, Optional, Dict
from .document import Document
from ..config import RUNTIME_ROOT, BACKEND, DEMO

DATA_DIR = RUNTIME_ROOT
DEFAULT_STORE_PATH = DATA_DIR / ("documents.json" if DEMO else "firestore_documents.json")


class DocumentStore:
    """Document store managing documents with Firestore semantics."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or DEFAULT_STORE_PATH
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.use_firestore = False
        self.firestore_db = None
        self._mem_cache: Optional[Dict[str, dict]] = None
        self._cache_stamp = None
        self._lock = RLock()

        # Check for Firestore configuration
        if storage_path is None and BACKEND == "firestore":
            try:
                import firebase_admin
                from firebase_admin import credentials, firestore
                if not firebase_admin._apps:
                    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                        cred = credentials.Certificate(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
                        firebase_admin.initialize_app(cred)
                    else:
                        firebase_admin.initialize_app()
                self.firestore_db = firestore.client()
                self.use_firestore = True
            except Exception as e:
                raise RuntimeError("Configured Firestore backend failed; refusing silent local fallback") from e

    def _read_local_docs(self) -> Dict[str, dict]:
        """Read all documents from local JSON file with in-memory caching."""
        stamp = self._local_stamp()
        if self._mem_cache is not None and stamp == self._cache_stamp:
            return self._mem_cache
        if not self.storage_path.exists():
            self._mem_cache = {}
            return self._mem_cache
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                self._mem_cache = json.load(f)
                self._cache_stamp = stamp
                return self._mem_cache
        except Exception as exc:
            raise RuntimeError(f"Cannot read document store: {self.storage_path.name}") from exc

    def _write_local_docs(self, docs: Dict[str, dict]) -> None:
        """Write all documents to local JSON file atomically and update memory cache."""
        temp_path = self.storage_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(docs, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        temp_path.replace(self.storage_path)
        self._mem_cache = dict(docs)
        self._cache_stamp = self._local_stamp()

    def _local_stamp(self):
        try:
            stat = self.storage_path.stat()
            # Rapid atomic replacements can share a filesystem timestamp.
            # File identity and size distinguish those writes without reading
            # the entire canonical store on every CMS lookup.
            return (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino)
        except FileNotFoundError:
            return None

    def get_document(self, doc_id: str) -> Optional[Document]:
        """Fetch a document by ID."""
        if self.use_firestore and self.firestore_db:
            doc_ref = self.firestore_db.collection("documents").document(doc_id)
            snapshot = doc_ref.get()
            if snapshot.exists:
                return Document.from_dict(snapshot.to_dict())
            return None

        docs = self._read_local_docs()
        if doc_id in docs:
            return Document.from_dict(docs[doc_id])
        # Also check by slug
        for d in docs.values():
            if d.get("slug") == doc_id:
                return Document.from_dict(d)
        return None

    def get_by_slug(self, slug: str) -> Optional[Document]:
        """Fetch a document by slug."""
        if self.use_firestore and self.firestore_db:
            results = self.firestore_db.collection("documents").where("slug", "==", slug).limit(1).get()
            for doc in results:
                return Document.from_dict(doc.to_dict())
            return None

        docs = self._read_local_docs()
        for d in docs.values():
            if d.get("slug") == slug:
                return Document.from_dict(d)
        return None

    def list_documents(self, status: Optional[str] = None) -> List[Document]:
        """List all documents, optionally filtering by status (e.g. 'published')."""
        if self.use_firestore and self.firestore_db:
            query = self.firestore_db.collection("documents")
            if status:
                query = query.where("status", "==", status)
            docs = []
            for item in query.stream():
                docs.append(Document.from_dict(item.to_dict()))
            return docs

        local_docs = self._read_local_docs()
        results = []
        for d in local_docs.values():
            if status is None or d.get("status") == status:
                results.append(Document.from_dict(d))
        return results

    @canonical_write
    def save_document(self, doc: Document) -> Document:
        """Save or update a document."""
        data = doc.to_dict()
        if self.use_firestore and self.firestore_db:
            self.firestore_db.collection("documents").document(doc.id).set(data)
            return doc

        with self._lock:
            docs = dict(self._read_local_docs())
            docs[doc.id] = data
            self._write_local_docs(docs)
        return doc

    @canonical_write
    def delete_document(self, doc_id: str) -> bool:
        with self._lock:
            return self._delete_document(doc_id)

    def _delete_document(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        if self.use_firestore and self.firestore_db:
            self.firestore_db.collection("documents").document(doc_id).delete()
            return True

        docs = self._read_local_docs()
        if doc_id in docs:
            del docs[doc_id]
            self._write_local_docs(docs)
            return True
        # Try finding by slug
        for k, v in list(docs.items()):
            if v.get("slug") == doc_id:
                del docs[k]
                self._write_local_docs(docs)
                return True
        return False
