"""Fixed CPU worker; no desktop/Brain imports, network access or arbitrary code."""
import hashlib
import json
import os
from pathlib import Path
import sys


def main():
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    from engine.desktop.offline import install_offline_boundary
    install_offline_boundary()
    import torch
    torch.set_num_threads(2)
    from engine.intelligence.beta.neural import load_model,predict
    if sys.argv[1] in ("training","evaluation"):
        from engine.intelligence.beta.train import train
        payload=json.loads(sys.stdin.buffer.read(65537))
        data=json.loads(Path(payload["dataset"]).read_text(encoding="utf-8"))
        if sys.argv[1]=="evaluation":
            scratch=Path(payload["dataset"]).parent/"evaluation-runtime";scratch.mkdir(exist_ok=True)
            os.environ.update(PESE_BRAIN_PATH=str(scratch),PESE_DATA_DIR=str(scratch),PESE_INTELLIGENCE_CHANNEL="stable",PESE_REL_SHADOW_ENABLED="false")
            from engine.intelligence.beta.lifecycle import evaluate_local
            decision=evaluate_local(payload["candidate"],payload["current"],payload["base"],data)
            print(json.dumps(decision,allow_nan=False),flush=True);return
        receipt=train(data["train"],data["validation"],payload["output"],steps=payload.get("steps",100),base=payload.get("base"))
        print(json.dumps({"checkpoint_sha256":receipt["checkpoint_sha256"],"seconds":receipt["seconds"]}),flush=True)
        return
    model=tokenizer=None;key=None
    for line in sys.stdin.buffer:
        if len(line)>65536:raise ValueError("Input budget")
        p=json.loads(line);directory=Path(p["directory"])
        identity=(p["checkpoint_hash"],p["tokenizer_hash"])
        for filename,expected in (("weights.pt",identity[0]),("tokenizer.json",identity[1])):
            f=directory/filename
            if f.stat().st_size>16*1024*1024 or hashlib.sha256(f.read_bytes()).hexdigest()!=expected:
                raise ValueError("Artifact integrity failure")
        if identity!=key:model,tokenizer=load_model(directory);key=identity
        evidence=p["evidence"]
        if not 1<=len(evidence)<=6 or any(len(e)>8000 for e in evidence):raise ValueError("Candidate budget")
        values=predict(model,tokenizer,[(p["query"],e) for e in evidence])
        print(json.dumps({"request_id":p["request_id"],"scores":values},allow_nan=False),flush=True)


if __name__=="__main__":main()
