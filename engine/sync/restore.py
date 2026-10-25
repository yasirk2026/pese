"""Offline recovery into a NEW Brain directory. Existing Brains are never replaced.

The desktop endpoint remains disabled until host-controlled activation is verified.
An interrupted fresh-directory recovery cannot modify the original Brain.
"""
import asyncio
import json
import os
import shutil
import stat
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from ..brain.atomic import atomic_write_json
from ..brain.lifecycle import _is_application_runtime_dir
from .contracts import (PESESyncManifest, RestoreResult, SYNC_MANIFEST_FILENAME,
                        CorruptSnapshotError, RestoreFailedError)
from .manifest import compute_file_sha256, normalize_portable_path, verify_staged_snapshot
from .logical import LOGICAL_FILENAME, import_records
from .payload import ALLOWED, MAX_FILES, MAX_ARCHIVE_BYTES, MAX_PAYLOAD_BYTES, validate_payload, strict_json_loads


def validate_archive(snapshot_zip_path, staging, expected_brain_id, expected_snapshot_id, expected_zip_sha256, expected_metadata=None):
    zip_path = Path(snapshot_zip_path)
    if zip_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise CorruptSnapshotError("Snapshot exceeds compressed size limit.")
    if compute_file_sha256(zip_path) != expected_zip_sha256:
        raise CorruptSnapshotError("Downloaded archive digest differs from selected Drive metadata.")
    with zipfile.ZipFile(zip_path) as archive:
        entries = archive.infolist()
        if SYNC_MANIFEST_FILENAME not in archive.namelist():
            raise CorruptSnapshotError("Snapshot missing manifest.")
        if archive.getinfo(SYNC_MANIFEST_FILENAME).file_size > 1024 * 1024:
            raise CorruptSnapshotError("Snapshot manifest exceeds metadata size limit.")
        if len(entries) > MAX_FILES or sum(e.file_size for e in entries) > MAX_PAYLOAD_BYTES:
            raise CorruptSnapshotError("Snapshot exceeds extraction limits.")
        names = []
        aliases = set()
        for entry in entries:
            try:
                name = normalize_portable_path(entry.filename)
            except ValueError as exc:
                raise CorruptSnapshotError("Unsafe archive path.") from exc
            alias = name.casefold()
            mode = entry.external_attr >> 16
            if (name not in ALLOWED | {SYNC_MANIFEST_FILENAME} or alias in aliases or entry.is_dir()
                    or entry.flag_bits & 1 or stat.S_ISLNK(mode)):
                raise CorruptSnapshotError("Unexpected, duplicate, aliased or unsafe archive entry.")
            aliases.add(alias)
            names.append(name)
        if SYNC_MANIFEST_FILENAME not in names:
            raise CorruptSnapshotError("Snapshot missing manifest.")
        try:
            manifest = PESESyncManifest.model_validate(strict_json_loads(archive.read(SYNC_MANIFEST_FILENAME)))
        except Exception as exc:
            raise CorruptSnapshotError("Invalid snapshot manifest.") from exc
        if set(names) != set(manifest.files) | {SYNC_MANIFEST_FILENAME}:
            raise CorruptSnapshotError("Archive and manifest entries differ.")
        if manifest.brain_id != expected_brain_id or manifest.snapshot_id != expected_snapshot_id:
            raise CorruptSnapshotError("Selected Brain/snapshot identity mismatch.")
        if expected_metadata is not None:
            agreement = {"pese_schema_version": str(manifest.schema_version),
                         "pese_app_version": manifest.app_version,
                         "pese_content_digest": manifest.integrity.content_digest}
            if any(expected_metadata.get(key) != value for key, value in agreement.items()):
                raise CorruptSnapshotError("Drive metadata and snapshot manifest disagree.")
        for name in names:
            destination = Path(staging) / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, destination.open("xb") as target:
                shutil.copyfileobj(source, target, 65536)
    verify_staged_snapshot(Path(staging), manifest)
    validate_payload(staging, manifest.files, expected_brain_id)
    return manifest


def restore_snapshot(snapshot_zip_path, target_brain_path=None, backup_base_dir=None, *,
                     expected_brain_id=None, expected_snapshot_id=None, expected_zip_sha256=None, expected_metadata=None):
    if not target_brain_path or not all((expected_brain_id, expected_snapshot_id, expected_zip_sha256)):
        raise RestoreFailedError("Recovery requires a new explicit target and confirmed Brain, snapshot and archive digest.")
    target = Path(target_brain_path).resolve()
    if target.exists() or _is_application_runtime_dir(target):
        raise RestoreFailedError("Recovery never replaces an existing or active Brain. Choose a new user-owned directory.")
    target.parent.mkdir(parents=True, exist_ok=True)
    journal = target.parent / ("." + target.name + ".pese-recovery.json")
    if journal.exists():
        raise RestoreFailedError("An interrupted recovery receipt exists. Inspect it before retrying; no data was changed.")
    # Same-parent staging guarantees same-volume rename, even when the ZIP is on another drive.
    staging = Path(tempfile.mkdtemp(prefix=".pese-recovery-", dir=target.parent))
    try:
        manifest = validate_archive(snapshot_zip_path, staging, expected_brain_id, expected_snapshot_id, expected_zip_sha256, expected_metadata)
        records = json.loads((staging / LOGICAL_FILENAME).read_text(encoding="utf-8"))
        import_records(records, staging / "search_sync_feedback.db")
        (staging / LOGICAL_FILENAME).unlink()
        (staging / SYNC_MANIFEST_FILENAME).unlink()
        from ..desktop.launcher import validate_brain
        validate_brain(staging)
        atomic_write_json(journal, {"version": 1, "state": "validated", "target": str(target),
                                   "stage": str(staging), "snapshotId": manifest.snapshot_id})
        if target.exists():
            raise RestoreFailedError("Recovery target appeared during staging; activation refused.")
        os.rename(staging, target)
        atomic_write_json(journal, {"version": 1, "state": "complete", "target": str(target),
                                   "snapshotId": manifest.snapshot_id})
        return RestoreResult(success=True, brain_id=manifest.brain_id, snapshot_id=manifest.snapshot_id,
                             restored_at=datetime.now(timezone.utc).isoformat(), files_restored=len(manifest.files),
                             message="Recovered to a new inactive Brain. The original Brain was not changed; inspect before connecting.")
    finally:
        # Never delete the destination or original Brain, including after rename or receipt-write failure.
        if staging.exists():
            shutil.rmtree(staging)


async def restore_snapshot_async(*args, **kwargs):
    return await asyncio.to_thread(restore_snapshot, *args, **kwargs)
