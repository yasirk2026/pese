import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from engine.intelligence.evidence import digest
from engine.intelligence.research import curate, freeze
from engine.intelligence.model_release import canonical, verify_bundle, ModelStore, ARCHITECTURE
from engine.tests.test_n3_evidence import record


def reviewed(split="train", number=1):
    r = record()
    r.update(split=split, source_kind="synthetic", query_family=f"q{number}", source_family=f"s{number}",
             document_lineage=f"d{number}", template_family=f"t{number}", question=f"clock {number}", evidence=f"synthetic evidence {number}")
    r["provenance"].update(target_id=f"d{number}", effective_query=r["question"], evidence_hash=digest(r["evidence"]))
    r["adjudication"] = {"objective":"retrieval_relevance", "label":1,"reviewer":"editor",
        "receipt_hash":digest(r["provenance"]), "reviewed_at":"2026-10-27T00:00:00Z", "rationale":"Synthetic fixture"}
    return r


def test_curation_weak_feedback_duplicates_conflicts_and_leakage(tmp_path):
    r = reviewed()
    kwargs = {"trusted_reviewers":{"editor"}, "verified_contexts":{digest(r["provenance"])}}
    accepted, quarantine = curate([r,r,{"feedback":"LIKE"}],**kwargs)
    assert len(accepted) == 1 and len(quarantine) == 1
    bad = deepcopy(r); bad["adjudication"]["label"] = 0
    with pytest.raises(ValueError, match="Contradictory"):
        curate([r,bad],**kwargs)
    other = reviewed("validation",2); other["template_family"] = r["template_family"]
    kwargs["verified_contexts"].add(digest(other["provenance"]))
    with pytest.raises(ValueError, match="leakage"):
        curate([r,other],**kwargs)
    records = [reviewed(split,i) for i,split in enumerate(("train","validation","calibration","test"))]
    kwargs["verified_contexts"] = {digest(r["provenance"]) for r in records}
    manifest = freeze(records,tmp_path/"dataset",**kwargs)
    assert manifest["records"] == 4 and not manifest["independent_test"]
    with pytest.raises(FileExistsError):
        freeze(records,tmp_path/"dataset",**kwargs)


def bundle(root, key, number=1):
    root.mkdir()
    (root/"weights.pt").write_bytes(b"fixture-weights-"+str(number).encode())
    (root/"tokenizer.json").write_text("{}")
    m = {"version":1,"key_id":"test","model_id":"PESE-Rel-1","model_version":str(number),
         "architecture":ARCHITECTURE,"tokenizer_id":"test-tokenizer1","min_app_version":"0.1.0-alpha.6",
         "files":{f:{"sha256":hashlib.sha256((root/f).read_bytes()).hexdigest(),"bytes":(root/f).stat().st_size} for f in ("weights.pt","tokenizer.json")},
         "acceptance":{"independent":True,"queries":300,"query_families":30,"ndcg10_delta":.03,"paired_lower95":.01,
                       "critical_regression":0,"new_wrong_promotions":0,"gate_violations":0,"warm_added_p95_ms":20,"cold_load_ms":100,"worker_peak_mb":200},
         "provenance":{"dataset_sha256":"a"*64,"code_sha256":"b"*64,"environment_sha256":"c"*64,"protocol_sha256":"d"*64},
         "rollback_contract":1,"relative_cap":.03,"gap_cap":.75}
    m["signature"] = base64.b64encode(key.sign(canonical(m))).decode()
    (root/"manifest.json").write_text(json.dumps(m))
    return root


def test_signed_integrity_healthcheck_and_rollback(tmp_path):
    # These ephemeral keys and fabricated metric fixtures test the gate only;
    # they are never installed as production trust or acceptance evidence.
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    keys = {"test":public}
    one,two = bundle(tmp_path/"one",key),bundle(tmp_path/"two",key,2)
    with pytest.raises(ValueError,match="No approved"):
        verify_bundle(one)
    store = ModelStore(tmp_path/"installed",keys)
    a = store.activate(one,lambda _:True)
    prior = (store.root/"active.json").read_bytes()
    with pytest.raises(ValueError):
        store.activate(two,lambda _:False)
    assert (store.root/"active.json").read_bytes() == prior
    b = store.activate(two,lambda _:True)
    assert b.identity != a.identity
    assert store.rollback().identity == a.identity
    (one/"weights.pt").write_bytes(b"tampered")
    with pytest.raises(ValueError):
        verify_bundle(one,trusted_keys=keys)
    m=json.loads((two/"manifest.json").read_text()); m["acceptance"]["independent"]=False
    signature=m.pop("signature"); m["signature"]=base64.b64encode(key.sign(canonical(m))).decode()
    (two/"manifest.json").write_text(json.dumps(m))
    with pytest.raises(ValueError,match="acceptance"):
        verify_bundle(two,trusted_keys=keys)


def test_trainer_smoke_preserves_holdout_and_never_activates(tmp_path):
    from engine.intelligence.training import train_candidate
    records=[]
    for i,split in enumerate(("train","validation","calibration","test")):
        for label in (0,1):
            r=reviewed(split,i*2+label)
            r["adjudication"]["label"]=label
            records.append(r)
    freeze(records,tmp_path/"data",trusted_reviewers={"editor"},
           verified_contexts={digest(r["provenance"]) for r in records})
    # Test/calibration can be unavailable: candidate training must not read them.
    (tmp_path/"data/test.json").unlink()
    (tmp_path/"data/calibration.json").unlink()
    receipt=train_candidate(tmp_path/"data",tmp_path/"candidate",epochs=1)
    assert not receipt["test_opened"] and not receipt["calibration_opened"]
    assert receipt["status"]=="development_candidate_no_ranking_authority"
    with pytest.raises(ValueError):
        verify_bundle(tmp_path/"candidate")
    from research.package_model import package_candidate
    with pytest.raises(ValueError,match="Independent"):
        package_candidate(tmp_path/"candidate",tmp_path/"release",evaluation_report={},
            signing_key=Ed25519PrivateKey.generate(),key_id="test",model_version="test-only",
            protocol_path=Path(__file__).resolve().parents[2]/"docs/neural/n3-acceptance-v1.json")
    # Fabricated acceptance values exercise packaging, never measure quality or
    # grant production trust. These keys/reports exist only in this fixture.
    key=Ed25519PrivateKey.generate()
    protocol=Path(__file__).resolve().parents[2]/"docs/neural/n3-acceptance-v1.json"
    report={"dataset_sha256":receipt["dataset_sha256"],"protocol_sha256":hashlib.sha256(protocol.read_bytes()).hexdigest(),
        "checkpoint_sha256":receipt["checkpoint_sha256"],"environment_sha256":receipt["environment_sha256"],
        "sealed_test_manifest_sha256":"d"*64,"reviewer_attestation_sha256":"e"*64,
        "acceptance":{"independent":True,"queries":300,"query_families":30,"ndcg10_delta":.03,"paired_lower95":.01,
                      "critical_regression":0,"new_wrong_promotions":0,"gate_violations":0,
                      "warm_added_p95_ms":20,"cold_load_ms":100,"worker_peak_mb":200}}
    package_candidate(tmp_path/"candidate",tmp_path/"test-only-bundle",evaluation_report=report,
        signing_key=key,key_id="test",model_version="fixture",protocol_path=protocol)
    public=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    assert verify_bundle(tmp_path/"test-only-bundle",trusted_keys={"test":public}).identity=="PESE-Rel-1:fixture"
    with pytest.raises(ValueError,match="No approved"):
        verify_bundle(tmp_path/"test-only-bundle")
