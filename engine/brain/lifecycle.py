"""
PESE Brain Lifecycle Management: Initialization, Opening, and Validation
Implements the core contracts for creating new Brains and validating existing Brains.
"""

import os
import sys
import json
import sqlite3
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Union

from .contracts import (
    BrainIdentity,
    BrainInfo,
    BrainStatus,
    BrainMissingError,
    BrainInvalidError,
    BrainConflictError,
    BrainPermissionError,
    BrainSecurityError,
    BRAIN_FORMAT_IDENTIFIER,
    CURRENT_SCHEMA_VERSION,
    BRAIN_MANIFEST_FILENAME,
)
from .atomic import atomic_write_json


DEFAULT_DOCUMENTS_FILENAME = "firestore_documents.json"
DEFAULT_FEEDBACK_DB_FILENAME = "search_sync_feedback.db"
DEFAULT_SETTINGS_FILENAME = "privacy_settings.json"
DEFAULT_EVENTS_FILENAME = "behavioural_events.jsonl"
DEFAULT_SEMANTIC_INDEX_DIRNAME = "semantic_index"
DEFAULT_PERSONALIZATION_DIRNAME = "personalization"


def _is_application_runtime_dir(target_dir: Path) -> bool:
    """
    Guards against accidentally selecting the application or python runtime directory.
    """
    resolved_target = target_dir.resolve()
    engine_root = Path(__file__).resolve().parent.parent
    app_root = engine_root.parent
    py_prefix = Path(sys.prefix).resolve()
    py_exec = Path(sys.executable).parent.resolve()

    forbidden_roots = [
        engine_root,
        app_root,
        py_prefix,
        py_exec,
        app_root / "packaging",
        app_root / "web",
    ]

    for forbidden in forbidden_roots:
        try:
            if resolved_target == forbidden or forbidden in resolved_target.parents:
                return True
        except Exception:
            pass
    return False


def initialize_brain(
    path: Union[str, Path],
    name: Optional[str] = None,
    seed_documents: bool = False,
    source_seed_path: Optional[Path] = None
) -> BrainIdentity:
    """
    Initializes a new local PESE Brain at the specified directory.

    Guarantees:
      1. Normalizes path.
      2. Verifies destination exists or creates it safely.
      3. Verifies write permission.
      4. Rejects application installation or runtime directories.
      5. NEVER overwrites an existing Brain (raises BrainConflictError if pese-brain.json exists).
      6. Creates pese-brain.json with format, schemaVersion=1, unique UUID, and UTC timestamp.
      7. Initializes minimum required storage files atomically:
         - firestore_documents.json
         - privacy_settings.json
         - search_sync_feedback.db
         - behavioural_events.jsonl
         - semantic_index/
         - personalization/
      8. Returns structured BrainIdentity.
    """
    target = Path(path).resolve()

    # 1. Security Check: Prevent initializing inside application runtime
    if _is_application_runtime_dir(target):
        raise BrainSecurityError(
            target,
            "Cannot store Brain inside the PESE application runtime directory. The Brain must reside in user-owned storage."
        )

    # 2. Destination directory creation
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise BrainPermissionError(target, f"Failed to create directory: {exc}")

    # 3. Write Permission Verification
    test_probe = target / f".pese_write_probe_{os.getpid()}"
    try:
        test_probe.write_text("probe", encoding="utf-8")
        test_probe.unlink()
    except Exception as exc:
        raise BrainPermissionError(target, f"Directory is not writable: {exc}")

    # 4. Invariant: NEVER overwrite an existing Brain
    manifest_path = target / BRAIN_MANIFEST_FILENAME
    if manifest_path.exists():
        raise BrainConflictError(target)

    # 5. Create Brain Identity
    identity = BrainIdentity.create_new(name=name)
    atomic_write_json(manifest_path, identity.to_dict())

    # 6. Initialize canonical documents store
    docs_path = target / DEFAULT_DOCUMENTS_FILENAME
    if not docs_path.exists():
        if seed_documents and source_seed_path and Path(source_seed_path).exists():
            shutil.copy2(source_seed_path, docs_path)
        else:
            atomic_write_json(docs_path, {})

    # 7. Initialize privacy settings
    settings_path = target / DEFAULT_SETTINGS_FILENAME
    if not settings_path.exists():
        initial_settings = {
            "history_enabled": True,
            "storage_mode": "local",
            "version": "1.0",
            "created_at": identity.created_at
        }
        atomic_write_json(settings_path, initial_settings)

    # 8. Initialize behavioural events log
    events_path = target / DEFAULT_EVENTS_FILENAME
    if not events_path.exists():
        events_path.touch()

    # 9. Initialize Search Sync SQLite feedback store
    feedback_db_path = target / DEFAULT_FEEDBACK_DB_FILENAME
    if not feedback_db_path.exists():
        # Brain creation and runtime use the same existing Search Sync DDL.
        # Importing the schema has no global store/configuration side effects.
        from .feedback_schema import initialize_feedback_schema
        conn = sqlite3.connect(str(feedback_db_path), timeout=10.0)
        try:
            initialize_feedback_schema(conn)
            conn.commit()
        finally:
            conn.close()

    # 10. Create subdirectories
    (target / DEFAULT_SEMANTIC_INDEX_DIRNAME).mkdir(exist_ok=True)
    (target / DEFAULT_PERSONALIZATION_DIRNAME).mkdir(exist_ok=True)

    return identity


def open_brain(path: Union[str, Path]) -> BrainInfo:
    """
    Opens and validates an existing PESE Brain directory.

    Validates:
      - Directory exists on disk (if not, raises BrainMissingError)
      - pese-brain.json exists (if not, raises BrainInvalidError)
      - Manifest is valid JSON (if not, raises BrainInvalidError)
      - format == "pese-brain"
      - schemaVersion is supported (currently version 1)
      - Required files can be safely opened

    Guarantees:
      - NEVER silently repairs unknown/corrupted Brain structures.
      - Returns structured BrainInfo.
    """
    target = Path(path).resolve()

    # 1. Existence check
    if not target.exists() or not target.is_dir():
        raise BrainMissingError(target, f"Brain directory does not exist: {target}")

    # 2. Identity manifest check
    manifest_path = target / BRAIN_MANIFEST_FILENAME
    if not manifest_path.exists():
        raise BrainInvalidError(target, f"Missing required identity manifest: '{BRAIN_MANIFEST_FILENAME}'")

    # 3. Parse manifest JSON
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as exc:
        raise BrainInvalidError(target, f"Corrupted or unreadable '{BRAIN_MANIFEST_FILENAME}': {exc}")

    # 4. Format validation
    fmt = raw_data.get("format")
    if fmt != BRAIN_FORMAT_IDENTIFIER:
        raise BrainInvalidError(
            target,
            f"Unsupported format '{fmt}'. Expected '{BRAIN_FORMAT_IDENTIFIER}'."
        )

    # 5. Schema version validation
    version = raw_data.get("schemaVersion")
    if version != CURRENT_SCHEMA_VERSION:
        raise BrainInvalidError(
            target,
            f"Unsupported schemaVersion '{version}'. Current supported version is {CURRENT_SCHEMA_VERSION}."
        )

    # 6. Brain ID validation
    brain_id = raw_data.get("brainId")
    if not brain_id or not isinstance(brain_id, str):
        raise BrainInvalidError(target, "Missing or invalid 'brainId' in manifest")

    created_at = raw_data.get("createdAt", "")
    name = raw_data.get("name")

    # 7. Document store validation
    docs_path = target / DEFAULT_DOCUMENTS_FILENAME
    doc_count = 0
    if docs_path.exists():
        try:
            with open(docs_path, "r", encoding="utf-8") as f:
                docs = json.load(f)
                if isinstance(docs, dict):
                    doc_count = len(docs)
        except Exception as exc:
            raise BrainInvalidError(target, f"Corrupted document store '{DEFAULT_DOCUMENTS_FILENAME}': {exc}")

    # 8. Check components presence
    has_feedback = (target / DEFAULT_FEEDBACK_DB_FILENAME).exists()
    has_settings = (target / DEFAULT_SETTINGS_FILENAME).exists()
    has_history = (target / DEFAULT_EVENTS_FILENAME).exists()

    return BrainInfo(
        brain_id=brain_id,
        schema_version=version,
        created_at=created_at,
        name=name,
        path=str(target),
        status=BrainStatus.ACTIVE,
        document_count=doc_count,
        has_feedback_db=has_feedback,
        has_privacy_settings=has_settings,
        has_history_log=has_history
    )


def verify_brain_integrity(path: Union[str, Path]) -> Dict[str, Any]:
    """
    Performs an in-depth integrity audit of a Brain directory.
    Returns a dictionary of component statuses.
    """
    info = open_brain(path)
    target = Path(path).resolve()

    checks = {
        "brain_id": info.brain_id,
        "schema_version": info.schema_version,
        "path": str(target),
        "manifest_ok": True,
        "documents_ok": False,
        "documents_count": info.document_count,
        "feedback_db_ok": False,
        "privacy_settings_ok": False,
        "semantic_cache_ok": False,
    }

    # Verify SQLite feedback store table accessibility
    db_path = target / DEFAULT_FEEDBACK_DB_FILENAME
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path), timeout=5.0)
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM active_preferences")
            cur.fetchone()
            conn.close()
            checks["feedback_db_ok"] = True
        except Exception:
            checks["feedback_db_ok"] = False

    # Verify document store
    docs_path = target / DEFAULT_DOCUMENTS_FILENAME
    if docs_path.exists() and info.document_count >= 0:
        checks["documents_ok"] = True

    # Verify settings
    settings_path = target / DEFAULT_SETTINGS_FILENAME
    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                json.load(f)
            checks["privacy_settings_ok"] = True
        except Exception:
            pass

    # Verify cache
    cache_dir = target / DEFAULT_SEMANTIC_INDEX_DIRNAME
    if cache_dir.exists() and cache_dir.is_dir():
        checks["semantic_cache_ok"] = True

    return checks
