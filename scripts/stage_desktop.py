"""Stage only application assets; never include the development Brain or secrets."""
import argparse
import importlib.metadata
import json
import re
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=Path)
    parser.add_argument("--asset-source", type=Path, help="Prepared offline asset checkout (excluded from Git)")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    stage = args.stage.resolve()
    assets = (args.asset_source or source).resolve()
    lab = assets / "packaging/runtime-lab"
    expected = {}
    for line in (source / "requirements.lock.txt").read_text().splitlines():
        match = re.fullmatch(r"([\w.-]+)==(.+)", line.strip())
        if match:
            name, version = match.groups()
            actual = importlib.metadata.version(name)
            if actual != version:
                raise RuntimeError(f"Locked distribution mismatch: {name} {actual} != {version}")
            expected[name] = actual
    # Fresh stage subfolders, owned solely by this build. Host publish is separate.
    for folder in ("engine", "runtime", "models", "ui"):
        target = stage / folder
        if target.exists():
            if stage not in target.resolve().parents:
                raise RuntimeError("Unsafe staging destination")
            shutil.rmtree(target)
        target.mkdir(parents=True)
    shutil.copytree(lab / "python-embed", stage / "runtime/python", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (stage / "runtime/python/python312._pth").write_text(
        "python312.zip\n.\nsite-packages\n..\\..\nimport site\n", encoding="utf-8")
    for path in (source / "engine").rglob("*.py"):
        relative = path.relative_to(source)
        if any(part in (".venv", "tests", "__pycache__", "private", "demo_runtime") for part in relative.parts):
            continue
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    # Preserve existing base-checkpoint paths to avoid changing neural loaders.
    shutil.copytree(assets / "engine/neural/checkpoints", stage / "engine/neural/checkpoints",
                    ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
    shutil.copytree(source / "engine/neural/data/pese_rel_data_0", stage / "engine/neural/data/pese_rel_data_0")
    shutil.copytree(lab / "models", stage / "models", dirs_exist_ok=True)
    shutil.copytree(source / "web/out", stage / "ui", dirs_exist_ok=True)
    # Product laboratory views read these reports from the application, never the Brain.
    for name in ("neural_genesis_report.json", "qa_experiment_report.json"):
        shutil.copy2(assets / "engine/data" / name, stage / "engine/data" / name)
    shutil.copy2(source / "requirements.lock.txt", stage / "requirements.lock.txt")
    (stage / "runtime-manifest.json").write_text(json.dumps({"locked_distributions": expected,
        "python": "3.12.10", "architecture": "win-x64", "brain_included": False}, indent=2), encoding="utf-8")
    forbidden = ("firestore_documents.json", "desktop-settings.json", "pese-brain.json", "node.exe")
    for name in forbidden:
        if list(stage.rglob(name)):
            raise RuntimeError(f"Forbidden user/development asset in stage: {name}")
    if list(stage.rglob("node_modules")):
        raise RuntimeError("Node modules must never ship")
    print(f"Staged {len(expected)} locked distributions; no development Brain.")


if __name__ == "__main__":
    main()
