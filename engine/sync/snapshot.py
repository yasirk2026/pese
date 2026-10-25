"""Coherent allowlisted canonical capture; format 2 never transports SQLite/vectors."""
import asyncio
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from ..brain.coordination import canonical_lock, ensure_capture_process
from ..brain.lifecycle import open_brain
from ..brain.resolver import resolve_brain_path
from .contracts import SnapshotBundle, SnapshotValidationError, SYNC_MANIFEST_FILENAME
from .logical import export_records, LOGICAL_FILENAME
from .payload import REQUIRED, ALLOWED, AVATARS, json_bytes, validate_payload, MAX_ARCHIVE_BYTES, MAX_PAYLOAD_BYTES
from .manifest import build_snapshot_manifest, compute_file_sha256, verify_staged_snapshot


def capture_canonical(brain, staging):
    """Caller holds canonical_lock. External file editors must be stopped."""
    brain, staging = Path(brain), Path(staging)
    ensure_capture_process(brain)
    info = open_brain(brain)
    personalization = brain / "personalization"
    if personalization.exists() and any(personalization.iterdir()):
        raise SnapshotValidationError("Personalization data has no portable G1 schema; capture refused.")
    paths = set(REQUIRED) - {LOGICAL_FILENAME}
    profile = brain / "profile/profile.json"
    if profile.exists():
        paths.add("profile/profile.json")
        from ..brain.profile import UserProfile
        data = UserProfile.model_validate_json(profile.read_text(encoding="utf-8"))
        if data.avatar and data.avatar.relative_path:
            if data.avatar.relative_path not in AVATARS:
                raise SnapshotValidationError("Unsupported profile avatar path.")
            paths.add(data.avatar.relative_path)
    if (brain / "profile").exists():
        actual = {p.relative_to(brain).as_posix() for p in (brain / "profile").iterdir()}
        if actual != paths & (AVATARS | {"profile/profile.json"}):
            raise SnapshotValidationError("Profile contains unsupported or incomplete assets.")
    for name in sorted(paths):
        source = brain / name
        if not source.is_file() or source.is_symlink() or not source.resolve().is_relative_to(brain.resolve()):
            raise SnapshotValidationError("Canonical capture requires regular Brain-owned files.")
        if source.stat().st_size > MAX_PAYLOAD_BYTES:
            raise SnapshotValidationError("Canonical file exceeds snapshot size limit.")
        destination = staging / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    db = brain / "search_sync_feedback.db"
    if not db.is_file() or db.is_symlink():
        raise SnapshotValidationError("Missing canonical Search Sync database.")
    (staging / LOGICAL_FILENAME).write_bytes(json_bytes(export_records(db)))
    paths.add(LOGICAL_FILENAME)
    if sum((staging / name).stat().st_size for name in paths) > MAX_PAYLOAD_BYTES:
        raise SnapshotValidationError("Canonical payload exceeds snapshot size limit.")
    validate_payload(staging, paths, info.brain_id)
    return info, paths


def canonical_state_digest(brain):
    from .payload import content_digest
    with tempfile.TemporaryDirectory(prefix="pese-state-") as temp:
        with canonical_lock:
            _, paths = capture_canonical(Path(brain), Path(temp))
        return content_digest(Path(temp), paths)


def create_snapshot(brain_path=None, destination_dir=None, include_semantic_cache=False):
    if include_semantic_cache:
        raise SnapshotValidationError("Rebuildable semantic caches are excluded from sync format 2.")
    brain = Path(brain_path) if brain_path else resolve_brain_path(allow_dev_fallback=True)
    if destination_dir and Path(destination_dir).resolve().is_relative_to(brain.resolve()):
        raise SnapshotValidationError("Snapshot archives must be written outside the Brain.")
    now = datetime.now(timezone.utc)
    snapshot_id = now.strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    bundle_path = None
    try:
        with tempfile.TemporaryDirectory(prefix="pese-capture-") as temp:
            staging = Path(temp)
            with canonical_lock:
                info, paths = capture_canonical(brain, staging)
            staged = [(name, staging / name, "canonical") for name in sorted(paths)]
            manifest = build_snapshot_manifest(info.brain_id, snapshot_id,
                                              now.isoformat().replace("+00:00", "Z"), staged)
            (staging / SYNC_MANIFEST_FILENAME).write_bytes(json_bytes(manifest.to_dict()))
            verify_staged_snapshot(staging, manifest)
            base = Path(destination_dir) if destination_dir else Path(tempfile.gettempdir())
            base.mkdir(parents=True, exist_ok=True)
            bundle_path = base / ("pese-snapshot-" + snapshot_id + ".zip")
            with zipfile.ZipFile(bundle_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
                for name in [SYNC_MANIFEST_FILENAME] + sorted(paths):
                    archive.write(staging / name, name)
            if bundle_path.stat().st_size > MAX_ARCHIVE_BYTES:
                raise SnapshotValidationError("Compressed snapshot exceeds transport size limit.")
            return SnapshotBundle(snapshot_id=snapshot_id, brain_id=info.brain_id, zip_path=bundle_path,
                                  zip_sha256=compute_file_sha256(bundle_path), total_size_bytes=bundle_path.stat().st_size,
                                  manifest=manifest)
    except Exception:
        if bundle_path:
            bundle_path.unlink(missing_ok=True)
        raise


async def create_snapshot_async(brain_path=None, destination_dir=None, include_semantic_cache=False):
    return await asyncio.to_thread(create_snapshot, brain_path, destination_dir, include_semantic_cache)
