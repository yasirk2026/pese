"""Train two Basic English development candidates without reading private data.

Accepts a fresh workspace outside the application. Selection sees validation
only. Calibration and generated acceptance are opened once after selection;
neither is represented as independently human-reviewed evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--workspace",required=True)
    args=p.parse_args();work=Path(args.workspace).resolve()
    if ROOT==work or ROOT in work.parents:p.error("Experiment workspace must be outside the application")
    work.mkdir(parents=True,exist_ok=False);(work/"Brain").mkdir()
    os.environ.update(PESE_BRAIN_PATH=str(work/"Brain"),PESE_DATA_DIR=str(work/"Brain"),
        LOCALAPPDATA=str(work/"profile"),PESE_PROFILE="private",HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",PESE_REL_SHADOW_ENABLED="false")
    from engine.intelligence.beta.data import freeze,load
    from engine.intelligence.beta.train import train,flatten
    from engine.intelligence.beta.evaluate import evaluate_pairs,integrated
    manifest=freeze(work/"dataset")
    train_cases=load(work/"dataset","train");validation=load(work/"dataset","validation")
    candidates=[]
    for name,seed,steps in (("candidate-a",20261027,300),("candidate-b",20261028,600)):
        receipt=train(flatten(train_cases),flatten(validation),work/name,seed=seed,steps=steps)
        evaluation=evaluate_pairs(work/name,validation)
        evaluation.pop("scores")
        candidates.append({"name":name,"training":receipt,"validation":evaluation})
        (work/name/"development.json").write_text(json.dumps(evaluation,indent=2),encoding="utf-8")
        print(json.dumps({"candidate":name,**evaluation}),flush=True)
    selected=max(candidates,key=lambda c:(c["validation"]["ndcg10"],-c["validation"]["calibration"]["brier"]))
    calibration=load(work/"dataset","calibration")
    # Calibration temperature is selected only on its own split.
    calibrated=[(t,evaluate_pairs(work/selected["name"],calibration,temperature=t)) for t in (.75,1,1.5,2)]
    temperature,calibration_report=min(calibrated,key=lambda pair:pair[1]["calibration"]["brier"])
    calibration_report.pop("scores")
    acceptance=load(work/"dataset","acceptance")
    acceptance_report=evaluate_pairs(work/selected["name"],acceptance,temperature=temperature)
    acceptance_report.pop("scores")
    integration=integrated(work/selected["name"],validation)
    report={"version":1,"policy":"aggressive_learning_beta","selected":selected["name"],"candidates":candidates,
       "dataset":manifest,"temperature":temperature,"calibration":calibration_report,
       "generated_acceptance":acceptance_report,"independent_human_acceptance":False,"integration":integration,
       "protocol_sha256":hashlib.sha256((ROOT/"docs/neural/n3e-beta-policy-v1.json").read_bytes()).hexdigest()}
    (work/"experiment.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({"selected":selected["name"],"acceptance":acceptance_report,
                      "changed":integration["changed_queries"],"delta":integration["paired"]["mean_ndcg10_delta"]}),flush=True)


if __name__=="__main__":main()
