"""
PESE Sync Manifest: Creation, Normalization, and Integrity Verification.
Enforces portable, platform-independent relative paths for all snapshot items.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

from .contracts import (
    PESESyncManifest,
    FileChecksumInfo,
    SnapshotIntegrity,
    SYNC_FORMAT_VERSION,
    SYNC_MANIFEST_FILENAME,
    CURRENT_APP_VERSION,
    CURRENT_SCHEMA_VERSION,
    CorruptSnapshotError,
    IncompatibleSnapshotError,
)


def compute_file_sha256(file_path: Path) -> str:
    """Computes SHA-256 hex digest of a file in 64KB chunks."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_bytes_sha256(data: bytes) -> str:
    """Computes SHA-256 hex digest of in-memory bytes."""
    return hashlib.sha256(data).hexdigest()


def normalize_portable_path(path_str: str) -> str:
    """
    Validates and normalizes a relative path to device-neutral forward-slash format.
    Rejects:
      - Windows backslashes
      - Drive letters (e.g. C:)
      - Leading slashes
      - Directory traversal (..)
      - Empty segments
    """
    import re
    if not isinstance(path_str, str) or "\\" in path_str:
        raise ValueError("Path must not contain Windows backslashes.")
    if path_str.startswith("/"):
        raise ValueError("Path must not be absolute.")
    if ":" in path_str:
        raise ValueError("Path must not contain drive letter or alternate stream.")
    parts = path_str.split("/")
    if any(p in ("..", ".", "") for p in parts):
        raise ValueError("Path contains traversal or empty segments.")
    if any(p.endswith((" ", ".")) or re.search(r'[<>"|?*\x00-\x1f]', p) or
           p.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1,10)), *(f"LPT{i}" for i in range(1,10))}
           for p in parts):
        raise ValueError("Path has a Windows alias or reserved name.")
    return path_str



def build_snapshot_manifest(
    brain_id: str,
    snapshot_id: str,
    created_at_iso: str,
    staged_files: List[Tuple[str, Path, str]],  # (relative_path, actual_path, category)
    app_version: str = CURRENT_APP_VERSION,
    schema_version: int = CURRENT_SCHEMA_VERSION,
) -> PESESyncManifest:
    """
    Constructs a deterministic PESESyncManifest from staged files.
    """
    file_entries: Dict[str, FileChecksumInfo] = {}
    categories_set = set()
    total_bytes = 0

    # Sort files deterministically by portable relative path
    sorted_staged = sorted(staged_files, key=lambda x: normalize_portable_path(x[0]))

    for rel_path, actual_path, category in sorted_staged:
        norm_rel = normalize_portable_path(rel_path)
        sha = compute_file_sha256(actual_path)
        size = actual_path.stat().st_size
        total_bytes += size
        categories_set.add(category)

        file_entries[norm_rel] = FileChecksumInfo(
            relativePath=norm_rel,
            sha256=sha,
            sizeBytes=size,
            category=category,
        )

    # Compute a content digest over all file hashes
    digest_hasher = hashlib.sha256()
    for rel_path in sorted(file_entries.keys()):
        digest_hasher.update(f"{rel_path}:{file_entries[rel_path].sha256}".encode("utf-8"))
    content_digest = digest_hasher.hexdigest()

    integrity = SnapshotIntegrity(
        algorithm="sha256",
        totalFiles=len(file_entries),
        totalBytes=total_bytes,
        contentDigest=content_digest,
    )

    return PESESyncManifest(
        syncFormatVersion=SYNC_FORMAT_VERSION,
        appVersion=app_version,
        brainId=brain_id,
        snapshotId=snapshot_id,
        createdAt=created_at_iso,
        schemaVersion=schema_version,
        categories=sorted(list(categories_set)),
        files=file_entries,
        integrity=integrity,
    )


def verify_staged_snapshot(
    staged_dir: Path,
    manifest: PESESyncManifest,
) -> None:
    """
    Verifies that all files listed in the manifest exist in staged_dir with matching hashes.
    Raises CorruptSnapshotError or IncompatibleSnapshotError if verification fails.
    """
    if manifest.sync_format_version != SYNC_FORMAT_VERSION:
        raise IncompatibleSnapshotError(
            f"Unsupported sync format version {manifest.sync_format_version}. Expected {SYNC_FORMAT_VERSION}."
        )

    if manifest.schema_version != CURRENT_SCHEMA_VERSION:
        raise IncompatibleSnapshotError(
            f"Unsupported Brain schema version {manifest.schema_version}. Expected {CURRENT_SCHEMA_VERSION}."
        )

    from .payload import ALLOWED, REQUIRED
    if not REQUIRED <= set(manifest.files) or not set(manifest.files) <= ALLOWED:
        raise CorruptSnapshotError("Snapshot files do not match the canonical payload contract.")
    if any(key != item.relative_path for key, item in manifest.files.items()):
        raise CorruptSnapshotError("Manifest path keys and entries disagree.")
    if manifest.integrity.algorithm != "sha256" or not manifest.integrity.content_digest:
        raise CorruptSnapshotError("Snapshot requires SHA-256 aggregate integrity.")
    if not manifest.brain_id or not manifest.snapshot_id:
        raise CorruptSnapshotError("Manifest missing required brain_id or snapshot_id.")

    digest_hasher = hashlib.sha256()
    verified_files = 0
    verified_bytes = 0

    for rel_path in sorted(manifest.files.keys()):
        file_info = manifest.files[rel_path]
        norm_path = normalize_portable_path(rel_path)
        target = staged_dir / Path(norm_path)

        if not target.exists() or not target.is_file():
            raise CorruptSnapshotError(f"Snapshot missing required file: {norm_path}")

        actual_sha = compute_file_sha256(target)
        if actual_sha != file_info.sha256:
            raise CorruptSnapshotError(
                f"Integrity check failed for '{norm_path}': expected {file_info.sha256}, got {actual_sha}"
            )

        actual_size = target.stat().st_size
        if actual_size != file_info.size_bytes:
            raise CorruptSnapshotError(
                f"Size check failed for '{norm_path}': expected {file_info.size_bytes}, got {actual_size}"
            )

        digest_hasher.update(f"{norm_path}:{actual_sha}".encode("utf-8"))
        verified_files += 1
        verified_bytes += actual_size

    if manifest.integrity.content_digest:
        actual_digest = digest_hasher.hexdigest()
        if actual_digest != manifest.integrity.content_digest:
            raise CorruptSnapshotError(
                f"Overall content digest mismatch: expected {manifest.integrity.content_digest}, got {actual_digest}"
            )

    if verified_files != manifest.integrity.total_files or verified_bytes != manifest.integrity.total_bytes:
        raise CorruptSnapshotError(
            f"File count or byte totals mismatch: {verified_files}/{manifest.integrity.total_files} files, "
            f"{verified_bytes}/{manifest.integrity.total_bytes} bytes"
        )
