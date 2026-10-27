"""Reproducible *development candidate* training, never release activation.

Requires a frozen, independently curated four-split manifest. Does not open test
or calibration examples. Tokenizer and optimization see train/validation only.
Training private journal text is not implemented or invoked by the desktop.
"""
import hashlib
import json
from pathlib import Path
import random
from types import SimpleNamespace


def train_candidate(dataset, output, *, seed=20261027, epochs=10):
    import torch
    from ..neural.configs.model_config import RelationConfig
    from ..neural.models.relation_classifier import PESERelationClassifier
    from ..neural.tokenization.relation_tokenizer import RelationTokenizer
    root = Path(dataset)
    manifest_bytes = (root / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("version") != 1 or manifest.get("objective") != "retrieval_relevance":
        raise ValueError("Not a reviewed relevance dataset")
    if type(epochs) is not int or not 1 <= epochs <= 20:
        raise ValueError("Bounded CPU experiment: 1..20 epochs")
    splits = {}
    for split in ("train", "validation"):
        data = (root / f"{split}.json").read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest["files"][f"{split}.json"]:
            raise ValueError("Dataset changed after curation")
        splits[split] = json.loads(data)
        if not splits[split] or any(not r.get("question") or not r.get("evidence") for r in splits[split]):
            raise ValueError("Explicitly reviewed example text required")
    random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    tokenizer = RelationTokenizer()
    tokenizer.train_on_split([SimpleNamespace(question=r["question"], evidence=r["evidence"]) for r in splits["train"]],
                             target_vocab_size=512)
    config = RelationConfig(vocab_size=tokenizer.vocab_size, d_model=64, n_layers=2, n_heads=4,
                            d_ff=128, max_seq_len=128, dropout=.1, model_name="PESE-Rel-1-relevance-dev")
    model = PESERelationClassifier(config)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=.01)
    def batches(rows):
        for offset in range(0, len(rows), 16):
            batch = rows[offset:offset+16]
            features = [tokenizer.build_cross_encoder_inputs(r["question"], r["evidence"], max_seq_len=128) for r in batch]
            inputs = [torch.tensor([f[k] for f in features], dtype=torch.long) for k in
                      ("input_ids", "token_type_ids", "attention_mask")]
            labels = torch.tensor([r["adjudication"]["label"] for r in batch], dtype=torch.long)
            yield inputs, labels
    target = Path(output)
    target.mkdir(parents=True, exist_ok=False)
    tokenizer.save(str(target / "tokenizer.json"))
    best, history = float("inf"), []
    for epoch in range(epochs):
        model.train()
        rows = list(splits["train"])
        random.shuffle(rows)
        for inputs, labels in batches(rows):
            optimizer.zero_grad(set_to_none=True)
            loss = torch.nn.functional.cross_entropy(model(*inputs), labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        model.eval()
        total_loss, count = 0.0, 0
        with torch.inference_mode():
            for inputs, labels in batches(splits["validation"]):
                total_loss += torch.nn.functional.cross_entropy(model(*inputs), labels, reduction="sum").item()
                count += len(labels)
        validation_loss = total_loss/count
        history.append({"epoch": epoch+1, "validation_loss": validation_loss})
        if validation_loss < best:
            best = validation_loss
            torch.save({"config": config.__dict__, "model_state_dict": model.state_dict(),
                        "objective": "retrieval_relevance"}, target / "weights.pt")
    receipt = {"version": 1, "status": "development_candidate_no_ranking_authority", "seed": seed,
               "epochs": epochs, "batch_size": 16, "learning_rate": .0003, "optimizer": "AdamW",
               "dataset_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
               "training_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "torch": torch.__version__, "history": history,
               "checkpoint_sha256": hashlib.sha256((target / "weights.pt").read_bytes()).hexdigest(),
               "test_opened": False, "calibration_opened": False}
    (target / "training-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt
