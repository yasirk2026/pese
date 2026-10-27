"""Offline curation and immutable manifests; independent of desktop/Brain IO.

No preference or community package is directly eligible for this pipeline.
Reviewers and verified receipts must be supplied from a trusted curation process.
"""
import json
from pathlib import Path
from .evidence import validate, Readiness, digest

SPLITS = ("train", "validation", "calibration", "test")
GROUPS = ("query_family", "source_family", "document_lineage", "template_family")


def curate(records, *, trusted_reviewers, verified_contexts):
    accepted, quarantine, seen, groups = [], [], {}, {}
    for r in records:
        verdict = validate(r, trusted_reviewers=trusted_reviewers, verified_contexts=verified_contexts)
        if verdict.classification != Readiness.ADJUDICATED:
            quarantine.append({"record_hash": digest(r), "reason": verdict.reason})
            continue
        if r["adjudication"]["objective"] != "retrieval_relevance":
            quarantine.append({"record_hash": digest(r), "reason": "Answer support is a separate objective"})
            continue
        if r.get("split") not in SPLITS or any(not r.get(g) for g in GROUPS):
            raise ValueError("Explicit split and all leakage groups are required")
        if (r.get("question") != r["provenance"]["effective_query"] or
                not isinstance(r.get("evidence"), str) or digest(r["evidence"]) != r["provenance"]["evidence_hash"]):
            raise ValueError("Reviewed example text does not match receipt")
        if r.get("source_kind") not in ("public", "synthetic"):
            raise ValueError("Central text training accepts explicitly reviewed public/synthetic sources only")
        identity = digest((r["question"].strip().casefold(), r["evidence"].strip()))
        label = r["adjudication"]["label"]
        if identity in seen:
            if seen[identity]["adjudication"]["label"] != label:
                raise ValueError("Contradictory judgments require adjudication; no majority voting")
            if seen[identity]["split"] != r["split"]:
                raise ValueError("Duplicate observation across splits")
            continue
        for group in GROUPS:
            key = (group, r[group])
            if key in groups and groups[key] != r["split"]:
                raise ValueError(f"Cross-split leakage in {group}")
            groups[key] = r["split"]
        for kind, content in (("exact_query",r["question"].strip().casefold()), ("exact_evidence",r["evidence"].strip())):
            key = (kind,digest(content))
            if key in groups and groups[key] != r["split"]:
                raise ValueError(f"Cross-split leakage in {kind}")
            groups[key] = r["split"]
        seen[identity] = r
        accepted.append(r)
    return accepted, quarantine


def freeze(records, directory, *, trusted_reviewers, verified_contexts):
    accepted, quarantine = curate(records, trusted_reviewers=trusted_reviewers, verified_contexts=verified_contexts)
    if not accepted or set(r["split"] for r in accepted) != set(SPLITS):
        raise ValueError("Four nonempty reviewed splits required; no automatic label creation")
    target = Path(directory)
    # Never overwrite an existing dataset, even if only a partial prior run exists.
    target.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for split in SPLITS:
        blob = (json.dumps([r for r in accepted if r["split"] == split], sort_keys=True,
                           ensure_ascii=False, allow_nan=False, indent=2)+"\n").encode()
        (target / f"{split}.json").write_bytes(blob)
        import hashlib
        hashes[f"{split}.json"] = hashlib.sha256(blob).hexdigest()
    manifest = {"version": 1, "objective": "retrieval_relevance", "files": hashes,
                "records": len(accepted), "quarantined": len(quarantine),
                "sampling_bias": "Uncorrected explicit-feedback/position bias; do not infer population quality",
                "independent_test": False}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
