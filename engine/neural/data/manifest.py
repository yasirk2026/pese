"""
PESE Neural Genesis: PESE-REL-DATA-0 Manifest & Persistence Engine
Phase N1: Build the Learning Contract Before Training the Brain

Serializes canonical relation dataset splits to disk with cryptographic SHA-256
manifests for absolute reproducibility and provenance auditing.
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from .relation_contracts import RelationExample
from .generator import generate_pese_rel_data_0
from .validator import validate_dataset, audit_near_duplicates

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "pese_rel_data_0"


def compute_sha256(content_bytes: bytes) -> str:
    """Computes SHA-256 hex digest for given bytes."""
    return hashlib.sha256(content_bytes).hexdigest()


def export_and_freeze_dataset(
    target_dir: Path = DEFAULT_DATA_DIR
) -> Dict[str, Any]:
    """
    Generates, validates, serializes, and hashes PESE-REL-DATA-0.
    Produces train.json, validation.json, test.json, and manifest.json.
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate dataset
    splits: Dict[str, List[RelationExample]] = generate_pese_rel_data_0()

    # 2. Strict validation
    val_report = validate_dataset(splits, check_entity_disjointness=True)
    near_dups = audit_near_duplicates(splits, jaccard_threshold=0.85)

    # 3. Serialize split files
    file_hashes: Dict[str, str] = {}
    file_paths: Dict[str, str] = {}

    for split_name in ["train", "validation", "test"]:
        examples = splits[split_name]
        data = [ex.model_dump_clean() for ex in examples]
        json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        
        file_path = target_dir / f"{split_name}.json"
        with open(file_path, "wb") as f:
            f.write(json_bytes)
            
        file_hashes[f"{split_name}.json"] = compute_sha256(json_bytes)
        file_paths[split_name] = str(file_path)

    # 4. Generate manifest
    manifest: Dict[str, Any] = {
        "dataset_name": "PESE-REL-DATA-0",
        "dataset_version": "1.0.0",
        "phase": "Neural Genesis N1",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_examples": val_report["total_examples"],
        "split_counts": val_report["split_counts"],
        "label_counts": val_report["label_counts"],
        "challenge_counts": val_report["challenge_counts"],
        "scenario_family_counts": val_report["scenario_family_counts"],
        "source_id_counts": val_report["source_id_counts"],
        "entity_counts": val_report["entity_counts"],
        "negative_reasons": val_report["negative_reasons"],
        "contrast_types": val_report["contrast_types"],
        "file_hashes": file_hashes,
        "near_duplicate_audit": {
            "threshold": 0.85,
            "flagged_count": len(near_dups),
            "flagged_items": near_dups
        },
        "privacy_compliance": {
            "zero_private_corpus": True,
            "zero_search_logs": True,
            "zero_user_documents": True,
            "synthetic_public_safe": True
        },
        "holdout_integrity": {
            "zero_old_holdout_leakage": True,
            "scenario_disjoint": True,
            "entity_disjoint": True
        }
    }

    manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
    manifest_path = target_dir / "manifest.json"
    with open(manifest_path, "wb") as f:
        f.write(manifest_bytes)

    manifest["manifest_sha256"] = compute_sha256(manifest_bytes)
    return manifest


def load_frozen_dataset(
    target_dir: Path = DEFAULT_DATA_DIR
) -> Dict[str, List[RelationExample]]:
    """
    Loads and re-validates the frozen dataset from disk against its manifest.
    """
    manifest_path = target_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found at {manifest_path}. Run export_and_freeze_dataset first.")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    splits: Dict[str, List[RelationExample]] = {}
    for split_name in ["train", "validation", "test"]:
        file_path = target_dir / f"{split_name}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Split file not found at {file_path}")

        with open(file_path, "rb") as f:
            raw_bytes = f.read()

        curr_hash = compute_sha256(raw_bytes)
        expected_hash = manifest["file_hashes"].get(f"{split_name}.json")
        if curr_hash != expected_hash:
            raise ValueError(
                f"Hash mismatch for {split_name}.json! Expected {expected_hash}, got {curr_hash}."
            )

        data = json.loads(raw_bytes.decode("utf-8"))
        splits[split_name] = [RelationExample(**item) for item in data]

    # Validate loaded split objects
    validate_dataset(splits, check_entity_disjointness=True)
    return splits


if __name__ == "__main__":
    manifest = export_and_freeze_dataset()
    print("PESE-REL-DATA-0 frozen successfully!")
    print(f"Total examples: {manifest['total_examples']}")
    print(f"Hashes: {manifest['file_hashes']}")
