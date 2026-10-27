"""Fixed local CPU inference entry point. Receives no executable model code."""
import hashlib
import json
from pathlib import Path
import sys


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    payload = json.loads(sys.stdin.buffer.read(65537))
    directory = Path(payload["directory"])
    for filename, field in (("weights.pt", "checkpoint_hash"), ("tokenizer.json", "tokenizer_hash")):
        p = directory / filename
        if p.stat().st_size > 16*1024*1024 or hashlib.sha256(p.read_bytes()).hexdigest() != payload[field]:
            raise ValueError("Artifact changed after verification")
    import torch
    torch.set_num_threads(2)
    from engine.neural.configs.model_config import RelationConfig
    from engine.neural.models.relation_classifier import PESERelationClassifier
    from engine.neural.tokenization.relation_tokenizer import RelationTokenizer
    ckpt = torch.load(directory / "weights.pt", map_location="cpu", weights_only=True)
    if ckpt.get("objective") != "retrieval_relevance":
        raise ValueError("Answer-support/preference weights cannot rank for relevance")
    config = RelationConfig(**ckpt["config"])
    if (not 1 <= config.d_model <= 128 or not 1 <= config.n_layers <= 4 or
            not 4 <= config.vocab_size <= 4096 or config.max_seq_len != 128 or config.d_ff > 512 or
            config.n_heads not in (1,2,4) or config.d_model % config.n_heads or
            config.num_classes != 2 or config.type_vocab_size != 2):
        raise ValueError("Architecture/resource incompatibility")
    model = PESERelationClassifier(config).eval()
    model.load_state_dict(ckpt["model_state_dict"])
    tokenizer = RelationTokenizer.load(str(directory / "tokenizer.json"))
    evidence = payload["evidence"]
    if not 1 <= len(evidence) <= 6:
        raise ValueError("Candidate budget exceeded")
    features = [tokenizer.build_cross_encoder_inputs(payload["query"], e, max_seq_len=128) for e in evidence]
    tensors = [torch.tensor([f[key] for f in features], dtype=torch.long) for key in
               ("input_ids", "token_type_ids", "attention_mask")]
    with torch.inference_mode():
        scores = torch.softmax(model(*tensors), dim=-1)[:,1].tolist()
    sys.stdout.write(json.dumps(scores, allow_nan=False))


if __name__ == "__main__":
    main()
