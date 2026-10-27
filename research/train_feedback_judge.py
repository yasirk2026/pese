"""Train an advisory meaning classifier on explicit synthetic reason semantics.

No relevance scores are features, no model predictions are labels, and this
classifier cannot admit a supervised example. Synthetic test != human validation.
"""
import hashlib
import json
from pathlib import Path
import random
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine.intelligence.beta.judge import advisory_features


def main():
    import torch
    torch.set_num_threads(2);torch.manual_seed(42);rng=random.Random(42)
    reasons={0:["irrelevant","not relevant","wrong result","wrong source"],
             1:["duplicate","poor presentation","interesting","preferred layout"],
             2:["","wrong information","didn't answer my query","outdated","other","accidental feedback"]}
    rows=[]
    for label,phrases in reasons.items():
        for phrase in phrases:
            for vote in ("LIKE","DISLIKE"):
                rows.append((advisory_features({"reason":phrase,"feedback":vote}),label,phrase))
    x=torch.tensor([r[0] for r in rows]);y=torch.tensor([r[1] for r in rows])
    model=torch.nn.Linear(x.shape[1],3);optimizer=torch.optim.AdamW(model.parameters(),lr=.05)
    for _ in range(250):
        optimizer.zero_grad();loss=torch.nn.functional.cross_entropy(model(x),y);loss.backward();optimizer.step()
    # Unseen wording, some deliberately missing the trained feature vocabulary.
    heldout=[("this page is irrelevant",0),("not relevant to my question",0),("wrong source for this search",0),
             ("this is a duplicate entry",1),("the presentation is poor",1),("interesting despite no answer",1),
             ("wrong information in the answer",2),("outdated information",2),("i clicked by accident",2),
             ("not about what i asked",0),("beautiful styling",1),("unclear",2)]
    hx=torch.tensor([advisory_features({"reason":reason,"feedback":"DISLIKE"}) for reason,label in heldout])
    with torch.inference_mode():prob=torch.softmax(model(hx),dim=-1);pred=prob.argmax(-1).tolist()
    report={"version":1,"architecture":"15-feature three-class learned linear softmax","seed":42,"steps":250,
            "labels":"explicit_synthetic_reason_semantics_not_human_independent_review","admission_authority":"NONE",
            "train_examples":len(rows),"unseen_wording_examples":len(heldout),
            "unseen_wording_accuracy":sum(p==label for p,(_,label) in zip(pred,heldout))/len(heldout),
            "errors":[{"reason":reason,"expected":label,"predicted":p} for p,(reason,label) in zip(pred,heldout) if p!=label],
            "trusted_label_false_acceptances":0,"false_acceptance_scope":"structural admission guard; classifier cannot grant labels",
            "independent_human_evaluation":False,"weights":model.weight.detach().tolist(),"bias":model.bias.detach().tolist(),
            "code_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    target=ROOT/"engine/neural/assets/feedback_judge_beta_v1.json";target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("weights","bias")},indent=2))


if __name__=="__main__":main()
