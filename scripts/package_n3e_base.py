"""Package only the selected, gate-passing original synthetic BETA model."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("experiment");args=p.parse_args()
    experiment=Path(args.experiment);report=json.loads((experiment/"experiment.json").read_text())
    policy=json.loads((ROOT/"docs/neural/n3e-beta-policy-v1.json").read_text())
    limits=policy["initial_candidate"]
    selected=next(c for c in report["candidates"] if c["name"]==report["selected"])
    if (selected["validation"]["balanced_accuracy"]<limits["minimum_validation_balanced_accuracy"] or
        selected["validation"]["ndcg10"]<limits["minimum_validation_ndcg10"] or
        report["integration"]["paired"]["mean_ndcg10_delta"]<limits["minimum_mean_integrated_ndcg10_delta"] or
        report["integration"]["new_wrong_promotions_proxy"] or report["integration"]["gate_violations"]):
        raise ValueError("Initial closed-BETA development gate failed")
    target=ROOT/"engine/neural/assets/basic_english_beta_v1"
    target.mkdir(parents=True,exist_ok=False)
    for name in ("weights.pt","tokenizer.json"):
        shutil.copyfile(experiment/report["selected"]/name,target/name)
    shutil.copyfile(experiment/"dataset/validation.json",target/"regression.json")
    shutil.copyfile(experiment/"dataset/manifest.json",target/"dataset-manifest.json")
    from engine.intelligence.beta.artifacts import write_manifest
    from engine.intelligence.beta.data import load
    from engine.intelligence.beta.train import flatten
    from engine.intelligence.beta.lifecycle import lineage
    manifest=write_manifest(target,identity="PESE-English-Beta-1:a300",origin="public_synthetic_base",evaluation={
        "initial_gate_passed":True,"independent_human_acceptance":False,"protocol_sha256":report["protocol_sha256"],
        "validation":selected["validation"],"integration_delta":report["integration"]["paired"]["mean_ndcg10_delta"]},training=selected["training"],
        lineage=lineage(flatten(load(experiment/"dataset","train")+load(experiment/"dataset","validation"))))
    (ROOT/"engine/intelligence/beta/base_lock.py").write_text('"""Application pin for the original synthetic BETA base; no production signing key."""\nBASE_FILES = '+repr(manifest["files"])+"\n",encoding="utf-8")
    shutil.copyfile(experiment/"experiment.json",ROOT/"docs/neural/n3e-english-experiment-v1.json")
    print(json.dumps(manifest,indent=2))
