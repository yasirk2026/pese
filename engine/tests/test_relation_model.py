"""
PESE Neural Genesis: Test Suite for Relation Reasoning Architecture
Phase N2: PESE-Rel-0 Verification & Invariant Tests
"""

import pytest
import torch
from pathlib import Path

from engine.neural.configs.model_config import RelationConfig, RelationTrainingConfig
from engine.neural.models.relation_classifier import PESERelationClassifier
from engine.neural.tokenization.relation_tokenizer import RelationTokenizer
from engine.neural.data.relation_contracts import RelationExample, RelationLabel
from engine.neural.data.relation_dataset import RelationDataset
from engine.neural.evaluation.relation_eval import compute_binary_metrics
from engine.neural.models.registry import registry, ModelStatus
from engine.neural.data.manifest import load_frozen_dataset


CHECKPOINT_DIR = Path(__file__).resolve().parent.parent / "neural" / "checkpoints" / "relation"
BEST_CHECKPOINT_PATH = CHECKPOINT_DIR / "peserel0_best.pt"
TOKENIZER_PATH = CHECKPOINT_DIR / "peserel0_tokenizer.json"


def test_relation_config_and_parameters():
    config = RelationConfig(
        model_name="PESE-Rel-0",
        vocab_size=512,
        d_model=128,
        n_layers=4,
        n_heads=4,
        d_ff=512,
        max_seq_len=128,
        dropout=0.1
    )
    assert config.count_parameters() == 892290
    model = PESERelationClassifier(config)
    total_params = sum(p.numel() for p in model.parameters())
    assert total_params == 892290


def test_relation_forward_pass_and_shapes():
    config = RelationConfig(
        model_name="PESE-Rel-0",
        vocab_size=512,
        d_model=128,
        n_layers=4,
        n_heads=4,
        d_ff=512,
        max_seq_len=128,
        dropout=0.1
    )
    model = PESERelationClassifier(config)
    model.eval()

    batch_size = 3
    seq_len = 32
    input_ids = torch.randint(0, config.vocab_size, (batch_size, seq_len))
    token_type_ids = torch.zeros((batch_size, seq_len), dtype=torch.long)
    token_type_ids[:, 16:] = 1  # segment 1
    attention_mask = torch.ones((batch_size, seq_len), dtype=torch.long)

    with torch.no_grad():
        logits = model(input_ids, token_type_ids, attention_mask)

    assert logits.shape == (batch_size, 2)
    assert not torch.isnan(logits).any()


def test_relation_tokenizer_load_and_tokens():
    assert TOKENIZER_PATH.exists()
    tokenizer = RelationTokenizer.load(str(TOKENIZER_PATH))
    assert tokenizer.vocab_size == 512
    assert tokenizer.pad_token_id == 0
    assert tokenizer.unk_token_id == 1
    assert tokenizer.cls_token_id == 2
    assert tokenizer.sep_token_id == 3

    encoded = tokenizer.build_cross_encoder_inputs(
        question="Who repaired the clock?",
        evidence="Engineer Nadia repaired it.",
        max_seq_len=64
    )
    assert encoded["input_ids"][0] == 2  # [CLS]
    assert 3 in encoded["input_ids"]     # [SEP]
    assert len(encoded["input_ids"]) == 64
    assert len(encoded["token_type_ids"]) == 64
    assert len(encoded["attention_mask"]) == 64

    # Segment IDs: Question must be 0, Evidence must be 1
    first_sep_idx = encoded["input_ids"].index(3)
    assert all(encoded["token_type_ids"][i] == 0 for i in range(first_sep_idx + 1))
    second_sep_idx = encoded["input_ids"].index(3, first_sep_idx + 1)
    assert all(encoded["token_type_ids"][i] == 1 for i in range(first_sep_idx + 1, second_sep_idx + 1))


def test_dataset_item_generation():
    tokenizer = RelationTokenizer.load(str(TOKENIZER_PATH))
    example = RelationExample(
        id="rel-test-01",
        question="Who repaired the station clock?",
        evidence="Engineer Nadia repaired the station clock in 1998.",
        label=RelationLabel.ANSWERS,
        answer_type="PERSON",
        scenario_family="station_clock_07",
        source_id="synthetic_station_07",
        relation_family="repair_actor"
    )

    dataset = RelationDataset([example], tokenizer, max_seq_len=64)
    assert len(dataset) == 1

    input_ids, token_type_ids, attention_mask, label, ex_id = dataset[0]
    assert input_ids.shape == (64,)
    assert token_type_ids.shape == (64,)
    assert attention_mask.shape == (64,)
    assert label.item() == 1  # ANSWERS = 1
    assert ex_id == "rel-test-01"


def test_checkpoint_resume_verification():
    assert BEST_CHECKPOINT_PATH.exists()
    ckpt = torch.load(BEST_CHECKPOINT_PATH, map_location="cpu")
    assert "model_state_dict" in ckpt
    assert "optimizer_state_dict" in ckpt
    assert "config" in ckpt
    assert ckpt["epoch"] >= 1

    config = RelationConfig(**ckpt["config"])
    model = PESERelationClassifier(config)
    model.load_state_dict(ckpt["model_state_dict"])
    model.train()

    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    optimizer.load_state_dict(ckpt["optimizer_state_dict"])

    # Perform 1 training step
    input_ids = torch.randint(0, config.vocab_size, (2, 32))
    token_type_ids = torch.zeros((2, 32), dtype=torch.long)
    attention_mask = torch.ones((2, 32), dtype=torch.long)
    labels = torch.tensor([1, 0], dtype=torch.long)

    optimizer.zero_grad()
    logits = model(input_ids, token_type_ids, attention_mask)
    loss = torch.nn.functional.cross_entropy(logits, labels)
    loss.backward()
    optimizer.step()

    assert not torch.isnan(loss)
    assert float(loss.item()) > 0.0


def test_model_registry_contains_rel0():
    card = registry.get("PESE-Rel-0")
    assert card is not None
    assert card.model_id == "PESE-Rel-0"
    assert card.status == ModelStatus.EXPERIMENT
    assert card.allowed_for_ranking is False
    assert card.allowed_for_answers is False
    assert card.total_parameters == 892290
    assert "peserel0_best.pt" in (card.checkpoint_path or "")


def test_binary_metrics_calculation():
    y_true = [1, 1, 0, 0, 1]
    y_pred = [1, 0, 0, 1, 1]
    m = compute_binary_metrics(y_true, y_pred)
    # TP: 2 (idx 0, 4)
    # FN: 1 (idx 1)
    # FP: 1 (idx 3)
    # TN: 1 (idx 2)
    assert m["tp"] == 2
    assert m["fn"] == 1
    assert m["fp"] == 1
    assert m["tn"] == 1
    assert m["accuracy"] == 0.6
    assert m["precision"] == round(2 / 3, 4)
    assert m["recall"] == round(2 / 3, 4)
    assert m["f1"] == round(2 / 3, 4)


def test_frozen_data_invariants_and_integrity():
    splits = load_frozen_dataset()
    assert len(splits["train"]) == 480
    assert len(splits["validation"]) == 120
    assert len(splits["test"]) == 120

    train_families = {x.scenario_family for x in splits["train"]}
    val_families = {x.scenario_family for x in splits["validation"]}
    test_families = {x.scenario_family for x in splits["test"]}

    assert len(train_families.intersection(val_families)) == 0
    assert len(train_families.intersection(test_families)) == 0
    assert len(val_families.intersection(test_families)) == 0
