"""Offline publisher-side bundle packaging. Never imported by desktop startup.

The caller supplies an offline signing key and an independently reviewed report.
This tool does not create acceptance metrics, install a trust key, publish, upload,
or activate the resulting artifact. Signature trust is a separate release action.
"""
import base64
import hashlib
import json
from pathlib import Path
import shutil
from cryptography.hazmat.primitives import serialization
from engine.intelligence.model_release import ARCHITECTURE, canonical, verify_bundle


def package_candidate(candidate, destination, *, evaluation_report, signing_key, key_id,
                      model_version, protocol_path, relative_cap=.03, gap_cap=.75):
    candidate=Path(candidate)
    receipt=json.loads((candidate/"training-receipt.json").read_text(encoding="utf-8"))
    protocol_hash=hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest()
    if (evaluation_report.get("dataset_sha256") != receipt["dataset_sha256"] or
            evaluation_report.get("protocol_sha256") != protocol_hash or
            not evaluation_report.get("sealed_test_manifest_sha256") or
            not evaluation_report.get("environment_sha256") or
            not evaluation_report.get("reviewer_attestation_sha256")):
        raise ValueError("Independent dataset/protocol/environment/review receipts required")
    weights_hash=hashlib.sha256((candidate/"weights.pt").read_bytes()).hexdigest()
    if weights_hash != receipt["checkpoint_sha256"] or weights_hash != evaluation_report.get("checkpoint_sha256"):
        raise ValueError("Evaluation and training must bind the same checkpoint")
    # Create only a fresh staging directory. A failed gate leaves it reviewable;
    # there is no current-model pointer mutation and no automatic release.
    target=Path(destination)
    target.mkdir(parents=True,exist_ok=False)
    for name in ("weights.pt","tokenizer.json"):
        shutil.copyfile(candidate/name,target/name)
    files={name:{"bytes":(target/name).stat().st_size,"sha256":hashlib.sha256((target/name).read_bytes()).hexdigest()}
           for name in ("weights.pt","tokenizer.json")}
    manifest={"version":1,"key_id":key_id,"model_id":"PESE-Rel-1","model_version":model_version,
       "architecture":ARCHITECTURE,"tokenizer_id":"pese-relevance-bpe1:"+files["tokenizer.json"]["sha256"],
       "min_app_version":"0.1.0-alpha.6","files":files,"acceptance":evaluation_report["acceptance"],
       "provenance":{"dataset_sha256":receipt["dataset_sha256"],"code_sha256":receipt["training_code_sha256"],
                     "environment_sha256":evaluation_report["environment_sha256"],"protocol_sha256":protocol_hash,
                     "evaluation_sha256":hashlib.sha256(canonical(evaluation_report)).hexdigest(),
                     "reviewer_attestation_sha256":evaluation_report["reviewer_attestation_sha256"],
                     "sealed_test_manifest_sha256":evaluation_report["sealed_test_manifest_sha256"]},
       "rollback_contract":1,"relative_cap":relative_cap,"gap_cap":gap_cap}
    manifest["signature"]=base64.b64encode(signing_key.sign(canonical(manifest))).decode()
    (target/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    public=signing_key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    verify_bundle(target,trusted_keys={key_id:public})
    return target
