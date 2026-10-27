"""Small fixed relevance cross-encoder; no training or IO during import."""
import json
from pathlib import Path


def load_model(directory):
    import torch
    from ...neural.configs.model_config import RelationConfig
    from ...neural.models.relation_classifier import PESERelationClassifier
    from ...neural.tokenization.relation_tokenizer import RelationTokenizer
    root=Path(directory)
    checkpoint=torch.load(root/"weights.pt",map_location="cpu",weights_only=True)
    if checkpoint.get("objective")!="retrieval_relevance":
        raise ValueError("Relevance objective required")
    config=RelationConfig(**checkpoint["config"])
    if not (config.d_model<=128 and 1<=config.n_layers<=4 and config.max_seq_len==128 and
            config.vocab_size<=2048 and config.d_ff<=512 and config.num_classes==2):
        raise ValueError("Unsupported fixed architecture")
    model=PESERelationClassifier(config).eval()
    model.load_state_dict(checkpoint["model_state_dict"])
    tokenizer=RelationTokenizer.load(str(root/"tokenizer.json"))
    return model,tokenizer


def tensors(tokenizer,pairs):
    import torch
    features=[tokenizer.build_cross_encoder_inputs(q.casefold(),p.casefold(),max_seq_len=128) for q,p in pairs]
    return [torch.tensor([f[k] for f in features],dtype=torch.long) for k in ("input_ids","token_type_ids","attention_mask")]


def predict(model,tokenizer,pairs,batch_size=32,temperature=1.0):
    import torch
    result=[]
    with torch.inference_mode():
        for offset in range(0,len(pairs),batch_size):
            logits=model(*tensors(tokenizer,pairs[offset:offset+batch_size]))
            result.extend(torch.softmax(logits/temperature,dim=-1)[:,1].tolist())
    return result
