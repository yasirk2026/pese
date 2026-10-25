"""Explicit recovery of a local downloaded archive into a new inactive Brain."""
import argparse
import json
from .restore import restore_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive")
    parser.add_argument("new_target")
    parser.add_argument("--brain-id", required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--sha256", required=True, help="Digest from the selected authenticated Drive metadata")
    args = parser.parse_args()
    result = restore_snapshot(args.archive, args.new_target, expected_brain_id=args.brain_id,
                              expected_snapshot_id=args.snapshot_id, expected_zip_sha256=args.sha256)
    print(json.dumps({"success": result.success, "snapshot_id": result.snapshot_id, "message": result.message}))


if __name__ == "__main__":
    main()
