"""
PESE Brain Recovery: Recover and reconcile knowledge corpus into an existing Brain.

Preserves the existing Brain identity, Search Sync feedback DB, and behavioural events.
Normalizes source documents using the canonical Document schema and deduplicates against
existing documents before importing.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from ..indexing.document import Document
from ..brain.resolver import resolve_brain_path

logger = logging.getLogger(__name__)


def recover_knowledge_corpus(
    brain_path: Optional[Path] = None,
    source_documents_path: Optional[Path] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Recover lost or missing knowledge corpus into the specified Brain.

    Guarantees:
      1. Brain identity (pese-brain.json) is never modified.
      2. Existing documents in the Brain are preserved and never lost.
      3. Missing documents are validated, normalized, and imported.
      4. Detailed ledger is returned for full auditability.
    """
    target_brain = Path(brain_path) if brain_path else resolve_brain_path(allow_dev_fallback=True)
    if not target_brain.exists():
        raise FileNotFoundError(f"Target Brain path does not exist: {target_brain}")

    manifest_file = target_brain / "pese-brain.json"
    if not manifest_file.exists():
        raise ValueError(f"Target directory is not a valid PESE Brain (missing pese-brain.json): {target_brain}")

    with open(manifest_file, "r", encoding="utf-8") as f:
        brain_manifest = json.load(f)
    brain_id = brain_manifest.get("brainId")

    # Resolve source documents file
    if source_documents_path:
        source_path = Path(source_documents_path)
    else:
        # Default authoritative corpus bundled with engine
        source_path = Path(__file__).resolve().parent.parent / "data" / "firestore_documents.json"

    if not source_path.exists():
        raise FileNotFoundError(f"Source corpus documents file not found: {source_path}")

    # Read existing target documents
    target_docs_file = target_brain / "firestore_documents.json"
    existing_docs: Dict[str, Any] = {}
    if target_docs_file.exists():
        with open(target_docs_file, "r", encoding="utf-8") as f:
            existing_docs = json.load(f)

    # Read source candidates
    with open(source_path, "r", encoding="utf-8") as f:
        source_docs: Dict[str, Any] = json.load(f)

    ledger: List[Dict[str, Any]] = []
    merged_docs: Dict[str, Any] = dict(existing_docs)
    imported_count = 0
    existing_count = 0
    upgraded_count = 0

    for doc_id, candidate in source_docs.items():
        # Validate candidate through Document model
        validated_doc = Document(**candidate)
        doc_dict = validated_doc.model_dump()

        if doc_id in existing_docs:
            current = existing_docs[doc_id]
            # Check if active is missing rich AST but candidate has it
            if current.get("content_schema_version", 1) < doc_dict.get("content_schema_version", 1):
                # Enrich with structured content while preserving active metadata
                enriched = dict(current)
                enriched["content_schema_version"] = doc_dict["content_schema_version"]
                enriched["structured_content"] = doc_dict.get("structured_content")
                if not enriched.get("meta_description") and doc_dict.get("meta_description"):
                    enriched["meta_description"] = doc_dict["meta_description"]
                merged_docs[doc_id] = enriched
                ledger.append({
                    "source": str(source_path),
                    "source_id": doc_id,
                    "destination_id": doc_id,
                    "title": current.get("title", doc_dict.get("title")),
                    "status": "upgraded_schema",
                    "indexed": True,
                })
                upgraded_count += 1
            else:
                ledger.append({
                    "source": str(source_path),
                    "source_id": doc_id,
                    "destination_id": doc_id,
                    "title": current.get("title", doc_dict.get("title")),
                    "status": "existing",
                    "indexed": True,
                })
                existing_count += 1
        else:
            # New document to import
            merged_docs[doc_id] = doc_dict
            ledger.append({
                "source": str(source_path),
                "source_id": doc_id,
                "destination_id": doc_id,
                "title": doc_dict.get("title"),
                "status": "new",
                "indexed": True,
            })
            imported_count += 1

    if not dry_run:
        # Atomic write
        temp_file = target_docs_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(merged_docs, f, indent=2, ensure_ascii=False)
            f.flush()
        temp_file.replace(target_docs_file)

    return {
        "brain_id": brain_id,
        "brain_path": str(target_brain),
        "source_path": str(source_path),
        "total_source_candidates": len(source_docs),
        "existing_before": len(existing_docs),
        "new_imported": imported_count,
        "existing_retained": existing_count,
        "upgraded_schema": upgraded_count,
        "total_after": len(merged_docs),
        "dry_run": dry_run,
        "ledger": ledger,
    }
