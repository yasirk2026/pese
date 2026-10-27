"""Bounded, reproducible candidate training. No active checkpoint is mutated."""
import hashlib
import json
from pathlib import Path
import platform
import random
import time
from types import SimpleNamespace
from .neural import tensors, predict


def train(rows,validation,output,*,seed=20261027,steps=300,base=None,cancel=None):
    import torch
    from ...neural.configs.model_config import RelationConfig
    from ...neural.models.relation_classifier import PESERelationClassifier
    from ...neural.tokenization.relation_tokenizer import RelationTokenizer
    from .neural import load_model
    if not rows or not validation or not 1<=steps<=600 or len(rows)>2000:
        raise ValueError("Invalid training budget")
    if {int(r["grade"]==2) for r in rows if r["grade"]!=1}!={0,1}:
        raise ValueError("Positive and negative diversity required")
    torch.set_num_threads(2)
    torch.manual_seed(seed)
    random.seed(seed)
    torch.use_deterministic_algorithms(True)
    if base:
        model,tokenizer=load_model(base)
        config=model.config if hasattr(model,"config") else RelationConfig(**torch.load(Path(base)/"weights.pt",weights_only=True)["config"])
        model.train()
    else:
        tokenizer=RelationTokenizer()
        tokenizer.train_on_split([SimpleNamespace(question=r["question"].casefold(),evidence=r["text"].casefold()) for r in rows],target_vocab_size=768)
        config=RelationConfig(model_name="PESE-English-Beta-1",d_model=64,n_layers=2,n_heads=4,d_ff=128,
                              vocab_size=tokenizer.vocab_size,max_seq_len=128,dropout=.1)
        model=PESERelationClassifier(config)
    target=Path(output)
    target.mkdir(parents=True,exist_ok=False)
    tokenizer.save(str(target/"tokenizer.json"))
    # Pre-tokenization saves repeated Python BPE work and cannot see evaluation.
    x=tensors(tokenizer,[(r["question"],r["text"]) for r in rows])
    y=torch.tensor([r["grade"]/2 for r in rows],dtype=torch.float32)
    vx=tensors(tokenizer,[(r["question"],r["text"]) for r in validation])
    vy=torch.tensor([r["grade"]/2 for r in validation],dtype=torch.float32)
    optimizer=torch.optim.AdamW(model.parameters(),lr=.001 if not base else .0002,weight_decay=.01)
    history=[]; best=float("inf"); started=time.monotonic()
    for step in range(steps):
        if cancel and cancel(): raise InterruptedError("Training cancelled; active checkpoint preserved")
        if time.monotonic()-started>180: raise TimeoutError("Training wall budget exceeded")
        model.train()
        indices=torch.randperm(len(rows))[:32]
        logits=model(*(v[indices] for v in x))
        loss=torch.nn.functional.binary_cross_entropy_with_logits(logits[:,1]-logits[:,0],y[indices])
        optimizer.zero_grad(set_to_none=True); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1); optimizer.step()
        if (step+1)%25==0 or step==steps-1:
            model.eval()
            with torch.inference_mode():
                losses=[]
                for offset in range(0,len(validation),32):
                    v=model(*(t[offset:offset+32] for t in vx))
                    losses.append(torch.nn.functional.binary_cross_entropy_with_logits(v[:,1]-v[:,0],vy[offset:offset+32],reduction="sum").item())
                validation_loss=sum(losses)/len(validation)
            history.append({"step":step+1,"validation_loss":validation_loss,"train_batch_loss":loss.item()})
            if validation_loss<best:
                best=validation_loss
                torch.save({"config":config.model_dump(),"model_state_dict":model.state_dict(),
                            "objective":"retrieval_relevance","label_scale":"graded_utility_0_1_2"},target/"weights.pt")
    receipt={"version":1,"objective":"retrieval_relevance","seed":seed,"steps":steps,"batch_size":32,
             "learning_rate":.001 if not base else .0002,"seconds":time.monotonic()-started,
             "parameters":sum(p.numel() for p in model.parameters()),"architecture":config.model_dump(),
             "training_pairs":len(rows),"validation_pairs":len(validation),"history":history,
             "checkpoint_sha256":hashlib.sha256((target/"weights.pt").read_bytes()).hexdigest(),
             "tokenizer_sha256":hashlib.sha256((target/"tokenizer.json").read_bytes()).hexdigest(),
             "code_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             "environment":{"python":platform.python_version(),"torch":torch.__version__,"threads":2},
             "calibration_opened":False,"acceptance_opened":False,"source":"synthetic_or_explicit_local_review",
             "base_checkpoint":str(base) if base else None}
    (target/"training.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    return receipt


def flatten(cases):
    return [{"question":c["question"],"text":p["text"],"grade":p["grade"],"group":c["group"],
             "document_family":c["document_family"]} for c in cases for p in c["candidates"]]
