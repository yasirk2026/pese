"""Metadata-only owner inventory and approved G1 backup/INACTIVE restore.

Never starts the engine, connects a Brain, changes a pointer, or prints document
text, titles, queries, profile names, or feedback rows. G1 internally validates
canonical content for backup; no content is used for diagnostics or learning.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inventory(brain):
    # Only the existing Brain validator sees canonical JSON for structural
    # validation/counting. Diagnostics receive its metadata-only BrainInfo.
    # Exact store-byte equality proves identity equality without extracting
    # document fields or decoding any private passage in this diagnostic.
    from engine.brain.lifecycle import open_brain
    info = open_brain(brain)
    manifest = json.loads((brain / "pese-brain.json").read_bytes())
    files = {}
    # Names of private user assets are not included in receipts.
    tree = []
    for path in sorted(brain.rglob("*")):
        if path.is_symlink() or path.is_junction():
            raise ValueError("Linked Brain entries require separate inspection")
        if path.is_file():
            relative = path.relative_to(brain).as_posix()
            entry = {"bytes": path.stat().st_size, "sha256": sha(path)}
            tree.append((relative, entry))
            if relative in {"pese-brain.json", "firestore_documents.json", "privacy_settings.json",
                            "behavioural_events.jsonl", "search_sync_feedback.db", ".desktop-writer.lock"}:
                files[relative] = entry
    with closing(sqlite3.connect((brain / "search_sync_feedback.db").as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ValueError("Canonical feedback database integrity failure")
        counts = {t: db.execute("SELECT count(*) FROM " + t).fetchone()[0] for t in
                  ("active_preferences", "feedback_audit_events", "neural_shadow_observations")}
    return {"brain_id": manifest["brainId"], "format": manifest["format"],
            "schema_version": manifest["schemaVersion"], "document_count": info.document_count,
            "document_identity_evidence": "full_canonical_document_bytes_including_identities", "files": files,
            "file_count": len(tree), "tree_sha256": hashlib.sha256(json.dumps(tree, sort_keys=True).encode()).hexdigest(),
            "canonical_feedback_counts": counts, "feedback_integrity": "ok",
            "experimental_sidecar_exists": (brain / ".pese-intelligence-v1").exists()}


def run(settings, install, output):
    settings, install, output = (Path(os.path.abspath(p)).resolve() for p in (settings, install, output))
    pointer_before = sha(settings)
    brain = Path(json.loads(settings.read_bytes())["brainPath"]).resolve()
    if output.exists() or output == ROOT or output.is_relative_to(ROOT) or output.is_relative_to(brain) or brain.is_relative_to(output):
        raise ValueError("Use a fresh output directory outside the checkout and original Brain")
    output.mkdir(parents=True)
    # All incidental runtime configuration resolves into a separate local profile.
    os.environ.update(LOCALAPPDATA=str(output / "profile"), PESE_BRAIN_PATH=str(brain), PESE_DATA_DIR=str(brain))
    sys.path.insert(0, str(ROOT))
    from engine.sync.snapshot import create_snapshot
    from engine.sync.restore import restore_snapshot
    from engine.sync.logical import export_records
    from engine.sync.payload import json_bytes
    from engine.brain.coordination import ensure_capture_process
    from engine.brain.lifecycle import open_brain

    ensure_capture_process(brain)  # Refuse an active writer; never stop owner processes.
    before = inventory(brain)
    app_before = {n: sha(install / n) for n in ("PESE.exe", "PESE.dll", "source-provenance.json")}
    source = json.loads((install / "source-provenance.json").read_bytes())
    bundle = create_snapshot(brain, output / "backups")
    recovered = output / "inactive-recovery"
    result = restore_snapshot(bundle.zip_path, recovered, expected_brain_id=bundle.brain_id,
                              expected_snapshot_id=bundle.snapshot_id, expected_zip_sha256=bundle.zip_sha256)
    restored = inventory(recovered)
    logical_original = hashlib.sha256(json_bytes(export_records(brain / "search_sync_feedback.db"))).hexdigest()
    logical_restored = hashlib.sha256(json_bytes(export_records(recovered / "search_sync_feedback.db"))).hexdigest()
    with zipfile.ZipFile(bundle.zip_path) as archive:
        names = archive.namelist()
        payload_hashes = {n: hashlib.sha256(archive.read(n)).hexdigest() for n in names}
    after = inventory(brain)
    checks = {
        "original_tree_unchanged": before == after,
        "pointer_unchanged": pointer_before == sha(settings),
        "stable_application_unchanged": app_before == {n: sha(install / n) for n in app_before},
        "brain_identity_equal": before["brain_id"] == restored["brain_id"] == bundle.brain_id,
        "document_count_equal": before["document_count"] == restored["document_count"],
        "document_identities_equal": before["files"]["firestore_documents.json"]["sha256"] == restored["files"]["firestore_documents.json"]["sha256"],
        "document_bytes_equal": before["files"]["firestore_documents.json"] == restored["files"]["firestore_documents.json"],
        "canonical_payload_bytes_equal": all((recovered / n).is_file() and sha(recovered / n) == h for n, h in payload_hashes.items()
                                             if n not in {"pese-sync-manifest.json", "search-sync-records.json"}),
        "logical_feedback_equal": logical_original == logical_restored,
        "desktop_validator_passed": open_brain(recovered).brain_id == bundle.brain_id,
        "experimental_assets_excluded": not any(".pese-intelligence" in n or n.endswith((".db", "weights.pt")) for n in names),
    }
    receipt = {"version": 1, "created_at": datetime.now(timezone.utc).isoformat(), "passed": all(checks.values()),
               "settings_path": str(settings), "original_brain": str(brain), "inactive_restore": str(recovered),
               "backup": str(bundle.zip_path), "snapshot_id": bundle.snapshot_id, "zip_sha256": bundle.zip_sha256,
               "original": before, "restored": restored, "checks": checks, "payload_sha256": payload_hashes,
               "application": {"install": str(install), "version": source["version"], "commit": source["commit"], "hashes": app_before},
               "private_text_displayed": False, "private_text_used_for_learning": False,
               "remote_drive_used": False, "restore_activated": False, "owner_beta_activated": False}
    (output / "safety-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": receipt["passed"], "documents": before["document_count"], "checks": checks,
                      "receipt": str(output / "safety-receipt.json")}))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", required=True)
    parser.add_argument("--install", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.settings, args.install, args.output))
