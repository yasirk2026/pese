"""Recover and interrupt only a marked disposable Brain using a staged Windows app."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import threading
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", type=Path)
    p.add_argument("source_fixture", type=Path)
    p.add_argument("case", type=Path, help="A new, nonexistent disposable directory")
    args = p.parse_args()
    source = args.source_fixture.resolve()
    if not (source / ".pese-disposable-fixture").is_file():
        raise ValueError("The source must be a marked disposable Brain")
    root = args.case.resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / ".pese-disposable-fixture").touch()
    os.environ["LOCALAPPDATA"] = str(root / "profile")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from engine.sync.snapshot import create_snapshot, canonical_state_digest
    from engine.sync.restore import restore_snapshot
    before = canonical_state_digest(source)
    bundle = create_snapshot(source, root / "archive")
    brain = root / "Recovered Brain"
    restore_snapshot(bundle.zip_path, brain, expected_brain_id=bundle.brain_id,
        expected_snapshot_id=bundle.snapshot_id, expected_zip_sha256=bundle.zip_sha256)
    (brain / ".pese-disposable-fixture").touch()
    assert not (brain / "semantic_index/cache_store.npz").exists()
    stage = args.stage.resolve()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PESE_", "PYTHON"))}
    child = subprocess.Popen([str(stage / "runtime/python/python.exe"), "-B", "-u", "-m", "engine.desktop.launcher"],
        cwd=stage, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8")
    child.stdin.write(json.dumps({"action": "serve", "brainPath": str(brain), "token": secrets.token_hex(32)}) + "\n")
    child.stdin.close()
    events = queue.Queue()
    def read():
        for line in child.stdout:
            if line.startswith("PESE_STARTUP "):
                events.put(json.loads(line.removeprefix("PESE_STARTUP ")))
    threading.Thread(target=read, daemon=True).start()
    interrupted = False
    started = time.monotonic()
    try:
        while time.monotonic() - started < 900 and child.poll() is None:
            try:
                event = events.get(timeout=.5)
            except queue.Empty:
                continue
            if event["stage"] == "passages" and 0 < event["completed"] < event["total"]:
                # This is the exact child handle created above, never an account process.
                child.terminate()
                child.wait(timeout=15)
                interrupted = True
                break
        if not interrupted:
            raise RuntimeError("Cold rebuild did not reach the interruption checkpoint")
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=15)
    assert canonical_state_digest(brain) == before, "Interrupted rebuild changed canonical data"
    assert not (brain / "semantic_index/cache_store.npz").exists()
    report = root / "native-cold-warm.json"
    subprocess.run([str(stage / "PESE.exe"), "--self-test", str(brain), str(report), "2"],
        cwd=stage, check=True, timeout=1800)
    native = json.loads(report.read_text(encoding="utf-8"))
    assert native["passed"]
    cycles = [x for x in native["results"] if "cycle" in x]
    search = next(x["search"] for x in native["results"] if "search" in x)
    docs = json.loads((brain / "firestore_documents.json").read_text(encoding="utf-8"))
    featured = [x for x in search["results"] if x.get("is_featured")]
    def grounded(item):
        text = item.get("featured_answer") or item.get("snippet") or ""
        if isinstance(text, dict):
            text = text.get("text", "")
        doc = docs.get(item.get("doc_id") or item.get("id"), {})
        return bool(text) and text in doc.get("content", "")
    assert featured and all(grounded(x) for x in featured), "Featured answer is not grounded in its source"
    assert all(x["health"]["documents_indexed"] == len(docs) for x in cycles)
    assert (brain / "semantic_index/cache_store.npz").is_file()
    assert canonical_state_digest(source) == before, "Source fixture changed"
    result = {"passed": True, "synthetic_data_only": True, "interrupted_rebuild_preserved_canonical": True,
        "source_preserved": True, "writer_lock_reacquired_after_interruption": True,
        "grounded_featured_answer": True, "cache_created": True,
        "cycles": [{k: v for k, v in x.items() if k in ("cycle", "startupSeconds", "peakWorkingSetBytes", "health", "readinessEvents", "phaseTimings")} for x in cycles],
        "archive_sha256": hashlib.sha256(bundle.zip_path.read_bytes()).hexdigest()}
    (root / "recovery-acceptance.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "cycles"}))


if __name__ == "__main__":
    main()
