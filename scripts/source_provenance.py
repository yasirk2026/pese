"""Stamp a staged application with the exact source state used for its build."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("stage", type=Path)
    p.add_argument("version")
    p.add_argument("--acceptance-only", action="store_true")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    git = ["git", "-c", "safe.directory=" + root.as_posix(), "-C", str(root)]
    commit = subprocess.check_output(git + ["rev-parse", "HEAD"], text=True).strip()
    status = subprocess.check_output(git + ["status", "--porcelain"], text=True)
    if status and not args.acceptance_only:
        raise ValueError("Release source is not clean; commit the reviewed implementation first")
    tracked = subprocess.check_output(git + ["ls-files", "-z"]).decode("utf-8").split("\0")
    hashes = {n: hashlib.sha256((root / n).read_bytes()).hexdigest() for n in tracked if n and (root / n).is_file()}
    payload = {"commit": commit, "version": args.version, "acceptance_only": args.acceptance_only,
               "source_clean": not bool(status), "tracked_files_sha256": hashes}
    (args.stage / "source-provenance.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Stamped {len(hashes)} source hashes at {commit}")


if __name__ == "__main__":
    main()
