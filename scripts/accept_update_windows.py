"""Exercise the actual installed native updater using synthetic data and a portable case.

Does not install/uninstall/register a product or alter the user's saved Brain pointer.
"""
import argparse
import gc
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path, help="New disposable case outside the source checkout")
    parser.add_argument("base_package", type=Path)
    parser.add_argument("target_artifacts", type=Path)
    parser.add_argument("updater", type=Path, help="Pinned Velopack 0.0.1298 Update.exe")
    parser.add_argument("--unicode-path", action="store_true")
    parser.add_argument("--ui", action="store_true", help="Exercise real WPF/WebView2 Settings controls")
    args = parser.parse_args()
    root = args.case.resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / ".pese-disposable-fixture").write_text("Synthetic updater acceptance only\n", encoding="utf-8")
    install = root / "install"
    current = install / "current"
    current.mkdir(parents=True)
    (install / ".portable").touch()
    shutil.copy2(args.updater, install / "Update.exe")
    with zipfile.ZipFile(args.base_package) as package:
        for entry in package.infolist():
            if not entry.filename.startswith("lib/app/") or entry.is_dir():
                continue
            target = (current / entry.filename[len("lib/app/"):]).resolve()
            if current not in target.parents:
                raise ValueError("Unsafe package member")
            target.parent.mkdir(parents=True, exist_ok=True)
            with package.open(entry) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
        (current / "sq.version").write_bytes(package.read("ManiacSoftwares.PESE.nuspec"))
    packages = install / "packages"
    packages.mkdir()
    shutil.copy2(args.base_package, packages / args.base_package.name)
    feed = root / "feed"
    feed.mkdir()
    target_feed = json.loads((args.target_artifacts / "releases.win.json").read_text(encoding="utf-8-sig"))
    targets = [a for a in target_feed["Assets"] if a["Type"] == "Full"]
    if len(targets) != 1:
        raise ValueError("Controlled feed must contain exactly one target")
    shutil.copy2(args.target_artifacts / targets[0]["FileName"], feed)
    shutil.copy2(args.target_artifacts / "releases.win.json", feed)
    profile = root / "LocalAppData"
    brain = (root / "Custom drive — علم" / "My PESE Brain") if args.unicode_path else profile / "ManiacSoftwares/PESE/Brain"
    os.environ.update(LOCALAPPDATA=str(profile), PESE_DATA_DIR=str(brain), PESE_BRAIN_PATH=str(brain))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from engine.brain import initialize_brain
    initialize_brain(brain, name="Synthetic update fixture")
    from engine.indexing.document import Document
    from engine.indexing.store import DocumentStore
    store = DocumentStore(brain / "firestore_documents.json")
    store.save_document(Document(id="pese", slug="pese", title="What is PESE?",
        content="PESE is a local personal search engine. PESE keeps documents in a separate Brain folder.",
        keywords=["PESE", "search"], status="published"))
    from engine.search_sync.feedback_store import SearchSyncFeedbackStore
    from engine.search_sync.contracts import FeedbackEvent
    feedback = SearchSyncFeedbackStore(brain / "search_sync_feedback.db")
    feedback.record_feedback(FeedbackEvent(query="PESE", normalized_query="pese", target_id="pese",
        target_type="SERP_RESULT", feedback="LIKE"))
    privacy = brain / "privacy_settings.json"
    settings = json.loads(privacy.read_text(encoding="utf-8"))
    settings["history_enabled"] = False
    privacy.write_text(json.dumps(settings), encoding="utf-8")
    from engine.brain.profile import save_profile
    save_profile("Synthetic update tester", "Disposable profile preservation fixture", brain_path=brain)
    (brain / "personalization" / "synthetic-fixture.json").write_text('{"fixture": true}', encoding="utf-8")
    (profile / "ManiacSoftwares/PESE").mkdir(parents=True, exist_ok=True)
    (profile / "ManiacSoftwares/PESE/desktop-settings.json").write_text(
        json.dumps({"brainPath": str(brain)}), encoding="utf-8")
    (profile / "ManiacSoftwares/PESE/credential-preservation.fixture").write_bytes(b"synthetic non-credential sentinel")
    del store, feedback
    gc.collect()
    account_sentinel = profile / "ManiacSoftwares/PESE/credential-preservation.fixture"
    account_digest = hashlib.sha256(account_sentinel.read_bytes()).hexdigest()
    plan = root / "plan.json"
    plan.write_text(json.dumps({"install": str(install), "brain": str(brain), "feed": str(feed),
        "targetVersion": targets[0]["Version"],
        "expectedNotes": targets[0].get("NotesMarkdown", "").splitlines()[0].lstrip("# ")}, indent=2), encoding="utf-8")
    command = "--accept-update-ui" if args.ui else "--accept-updater"
    process = subprocess.Popen([str(current / "PESE.exe"), command, str(plan)], cwd=current)
    code = process.wait(timeout=600)
    if code:
        raise RuntimeError(f"Native update handoff failed ({code}); inspect the private case report")
    after = root / "update-after.json"
    deadline = time.monotonic() + 600
    while not after.exists() and time.monotonic() < deadline:
        time.sleep(0.25)
    if not after.exists() or not json.loads(after.read_text(encoding="utf-8"))["passed"]:
        raise RuntimeError("The restarted target did not pass acceptance")
    if hashlib.sha256(account_sentinel.read_bytes()).hexdigest() != account_digest:
        raise RuntimeError("The synthetic account sentinel changed during update")
    with zipfile.ZipFile(args.base_package) as package:
        base_source = json.loads(package.read("lib/app/source-provenance.json"))
    def digest(path):
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    acceptance = {"passed": True, "real_native_update": True, "real_restart": True,
        "target": targets[0]["Version"], "portable_installation": True,
        "synthetic_data_only": True, "unicode_path": args.unicode_path, "native_ui": args.ui,
        "base_version": base_source["version"], "base_commit": base_source["commit"],
        "base_package_sha256": digest(args.base_package),
        "target_package_sha256": digest(args.target_artifacts / targets[0]["FileName"]),
        "canonical_and_pointer_preserved": True, "account_sentinel_preserved": True}
    (root / "acceptance.json").write_text(json.dumps(acceptance, indent=2), encoding="utf-8")
    print(json.dumps(acceptance))


if __name__ == "__main__":
    main()
