"""Extract pinned offline runtime/model assets from the existing public Alpha.4 package.

No Brain, application source, credentials or machine-local settings are imported.
"""
import argparse
import hashlib
import shutil
import zipfile
from pathlib import Path

PACKAGE_SHA256 = "f8e7d15ff50884ffd6dc4d3109aa2f1153b36140d5cad4c9f0954359ea5853dc"
ASSET_PREFIXES = {
    "lib/app/runtime/python/": "packaging/runtime-lab/python-embed/",
    "lib/app/models/": "packaging/runtime-lab/models/",
    "lib/app/engine/neural/checkpoints/": "engine/neural/checkpoints/",
}
REPORTS = {"neural_genesis_report.json", "qa_experiment_report.json"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("destination", type=Path, help="New, empty offline-asset directory")
    args = parser.parse_args()
    with args.package.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != PACKAGE_SHA256:
            raise ValueError("The Alpha.4 asset package does not match the pinned SHA-256")
    root = args.destination.resolve()
    root.mkdir(parents=True, exist_ok=False)
    count = 0
    with zipfile.ZipFile(args.package) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            relative = None
            for prefix, mapped in ASSET_PREFIXES.items():
                if entry.filename.startswith(prefix):
                    relative = mapped + entry.filename[len(prefix):]
                    break
            if entry.filename in {"lib/app/engine/data/" + n for n in REPORTS}:
                relative = "engine/data/" + Path(entry.filename).name
            if relative is None:
                continue
            target = (root / relative).resolve()
            if root not in target.parents:
                raise ValueError("Unsafe asset package path")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, target.open("xb") as destination:
                shutil.copyfileobj(source, destination)
            count += 1
    (root / "packaging/runtime-lab/python-embed/python312._pth").write_text(
        "python312.zip\n.\nsite-packages\nimport site\n", encoding="utf-8")
    print(f"Provisioned {count} pinned offline assets; no application source or Brain imported.")


if __name__ == "__main__":
    main()
