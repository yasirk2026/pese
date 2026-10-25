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
import sqlite3
import ctypes
from ctypes import wintypes
import xml.etree.ElementTree as ET
from contextlib import closing
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path, help="New disposable case outside the source checkout")
    parser.add_argument("base_package", type=Path)
    parser.add_argument("target_artifacts", type=Path)
    parser.add_argument("updater", type=Path, help="Pinned Velopack 0.0.1298 Update.exe")
    parser.add_argument("--unicode-path", action="store_true")
    parser.add_argument("--ui", action="store_true", help="Exercise real WPF/WebView2 Settings controls")
    parser.add_argument("--interrupt-before-activation", action="store_true", help="Stop only the fixture updater during staging, verify the old installation, then retry")
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
        base_source = json.loads(package.read("lib/app/source-provenance.json"))
        original_host_sha = hashlib.sha256(package.read("lib/app/PESE.dll")).hexdigest()
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
    def logical_rows():
        with closing(sqlite3.connect((brain / "search_sync_feedback.db").as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            return {table: {json.dumps(dict(row), sort_keys=True) for row in db.execute("SELECT * FROM " + table)}
                    for table in ("active_preferences", "feedback_audit_events", "neural_shadow_observations")}
    before_rows = logical_rows()
    plan = root / "plan.json"
    plan.write_text(json.dumps({"install": str(install), "brain": str(brain), "feed": str(feed),
        "targetVersion": targets[0]["Version"],
        "expectedNotes": targets[0].get("NotesMarkdown", "").splitlines()[0].lstrip("# ")}, indent=2), encoding="utf-8")
    command = "--accept-update-ui" if args.ui else "--accept-updater"
    process = subprocess.Popen([str(current / "PESE.exe"), command, str(plan)], cwd=current)
    code = process.wait(timeout=600)
    if code:
        raise RuntimeError(f"Native update handoff failed ({code}); inspect the private case report")
    interrupted = False
    if args.interrupt_before_activation:
        first_handoff_time = (root / "update-before.json").stat().st_mtime_ns
        environment = dict(os.environ, PESE_UPDATE_TEST_ROOT=str(install))
        command_text = "$p=Join-Path $env:PESE_UPDATE_TEST_ROOT 'Update.exe'; Get-CimInstance Win32_Process -Filter \"Name='Update.exe'\" | Where-Object { $_.ExecutablePath -eq $p } | Select-Object -ExpandProperty ProcessId"
        shell = str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe")
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            output = subprocess.check_output([shell, "-NoProfile", "-NonInteractive", "-Command", command_text], env=environment, text=True).strip()
            staging = install / "packages/VelopackTemp"
            if output and staging.exists() and any(staging.iterdir()):
                versions = {e.tag.rsplit("}", 1)[-1]: e.text for e in ET.fromstring((current / "sq.version").read_bytes()).iter()}
                if versions.get("version") != base_source["version"]:
                    raise RuntimeError("Safe interruption window was missed; updater was not terminated")
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
                kernel.OpenProcess.restype = wintypes.HANDLE
                kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
                kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
                kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                handle = kernel.OpenProcess(0x1001, False, int(output))
                if not handle:
                    raise OSError("Cannot open the fixture updater")
                try:
                    buffer = ctypes.create_unicode_buffer(32768)
                    size = wintypes.DWORD(len(buffer))
                    if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)) or Path(buffer.value).resolve() != (install / "Update.exe").resolve():
                        raise RuntimeError("Updater identity mismatch; no process was terminated")
                    if not kernel.TerminateProcess(handle, 99):
                        raise OSError("Fixture updater interruption failed")
                finally:
                    kernel.CloseHandle(handle)
                time.sleep(1)
                if hashlib.sha256((current / "PESE.dll").read_bytes()).hexdigest() != original_host_sha:
                    raise RuntimeError("The old executable changed before activation")
                drained = json.loads((root / "update-before.json").read_text(encoding="utf-8"))["canonical"]
                for name, expected in drained.items():
                    path = profile / "ManiacSoftwares/PESE/desktop-settings.json" if name == "desktop-pointer" else brain / name
                    if hashlib.sha256(path.read_bytes()).hexdigest().upper() != expected:
                        raise RuntimeError("Fixture data changed during interrupted update")
                interrupted = True
                (root / "interruption-preserved.json").write_text(json.dumps({"old_version": base_source["version"], "canonical_preserved": True}), encoding="utf-8")
                process = subprocess.Popen([str(current / "PESE.exe"), command, str(plan)], cwd=current)
                if process.wait(timeout=600):
                    raise RuntimeError("The old installation could not retry its interrupted update")
                resumed = json.loads((root / "update-before.json").read_text(encoding="utf-8"))
                if resumed["version"] != base_source["version"] or (root / "update-before.json").stat().st_mtime_ns <= first_handoff_time:
                    raise RuntimeError("A cached package bypassed the explicit native update path")
                break
            time.sleep(0.2)
        if not interrupted:
            raise RuntimeError("The safe pre-activation interruption was not exercised")
    after = root / "update-after.json"
    # The pinned updater removes the full 20k-file runtime before restart.
    # This filesystem can take several minutes; allow progress to finish honestly.
    deadline = time.monotonic() + 1800
    while not after.exists() and time.monotonic() < deadline:
        time.sleep(0.25)
    if not after.exists() or not json.loads(after.read_text(encoding="utf-8"))["passed"]:
        raise RuntimeError("The restarted target did not pass acceptance")
    if hashlib.sha256(account_sentinel.read_bytes()).hexdigest() != account_digest:
        raise RuntimeError("The synthetic account sentinel changed during update")
    after_rows = logical_rows()
    for table in ("active_preferences", "feedback_audit_events"):
        if before_rows[table] != after_rows[table]:
            raise RuntimeError("Existing feedback or audit records changed during update")
    if not before_rows["neural_shadow_observations"] <= after_rows["neural_shadow_observations"]:
        raise RuntimeError("Existing neural observation records were lost")
    if any(json.loads(row)["authority"] != "NONE" for row in after_rows["neural_shadow_observations"]):
        raise RuntimeError("Neural observations gained authority")
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
    acceptance["feedback_rows_preserved"] = True
    acceptance["neural_authority"] = "NONE"
    acceptance["expected_search_observations_appended"] = len(after_rows["neural_shadow_observations"] - before_rows["neural_shadow_observations"])
    acceptance["interrupted_update_recovered"] = interrupted
    acceptance["download_faults_checked"] = (root / "download-faults-passed.json").is_file()
    acceptance["explicit_retry_after_interruption"] = interrupted
    (root / "acceptance.json").write_text(json.dumps(acceptance, indent=2), encoding="utf-8")
    print(json.dumps(acceptance))


if __name__ == "__main__":
    main()
