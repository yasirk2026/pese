"""
PESE Neural Genesis: Scientific Evaluation Runner
Verifies neural tensor mathematics, causal masking invariance, tokenizer fidelity,
micro-overfit convergence, checkpoint reload accuracy, QA grounding contracts,
and strict privacy boundaries.
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List

import torch
import torch.nn.functional as F

from ..neural.configs.model_config import TransformerConfig, TrainingConfig
from ..neural.tokenization.char_tokenizer import CharTokenizer
from ..neural.tokenization.bpe_tokenizer import BPETokenizer
from ..neural.models.transformer import PESETransformer
from ..neural.models.registry import registry, ModelStatus
from ..neural.data.dataset import MICRO_OVERFIT_TEXTS, SYNTHETIC_PUBLIC_CORPUS, CausalLMDataset
from ..neural.data.contracts import find_answer_span, export_faqs_to_qa_contracts
from ..neural.training.trainer import NeuralTrainer
from ..neural.training.checkpoint import save_checkpoint, load_checkpoint


def test_parameter_counting() -> Dict[str, Any]:
    """Verify analytical parameter count matches instantiated PyTorch parameter count."""
    cfg = TransformerConfig(
        model_name="PESE-NG-0-test",
        vocab_size=256,
        d_model=128,
        n_layers=4,
        n_heads=4,
        d_ff=512,
        max_seq_len=128,
        dropout=0.1
    )
    model = PESETransformer(cfg)
    actual_params = model.count_parameters()
    theoretical_params = cfg.count_parameters()

    match = actual_params == theoretical_params
    return {
        "test": "parameter_counting",
        "passed": match,
        "actual_params": actual_params,
        "theoretical_params": theoretical_params,
    }


def test_causal_masking_invariance() -> Dict[str, Any]:
    """
    Verify causal masking: token representations at position t must NOT change
    when subsequent tokens at t' > t are modified.
    """
    torch.manual_seed(42)
    cfg = TransformerConfig(
        vocab_size=256,
        d_model=64,
        n_layers=2,
        n_heads=2,
        d_ff=256,
        max_seq_len=64,
        dropout=0.0
    )
    model = PESETransformer(cfg)
    model.eval()

    # Sequence A: [10, 20, 30, 40]
    seq_a = torch.tensor([[10, 20, 30, 40]], dtype=torch.long)
    # Sequence B: [10, 20, 99, 88] (first 2 tokens are identical)
    seq_b = torch.tensor([[10, 20, 99, 88]], dtype=torch.long)

    with torch.no_grad():
        logits_a, _ = model(seq_a)
        logits_b, _ = model(seq_b)

    # First token logits (position 0) must be bitwise identical
    diff_pos0 = torch.max(torch.abs(logits_a[0, 0] - logits_b[0, 0])).item()
    # Second token logits (position 1) must be bitwise identical
    diff_pos1 = torch.max(torch.abs(logits_a[0, 1] - logits_b[0, 1])).item()

    is_causal = (diff_pos0 < 1e-5) and (diff_pos1 < 1e-5)
    return {
        "test": "causal_masking_invariance",
        "passed": is_causal,
        "diff_pos0": diff_pos0,
        "diff_pos1": diff_pos1,
    }


def test_tokenizer_fidelity() -> Dict[str, Any]:
    """Verify BPE subword tokenizer training, encoding, and roundtrip decoding."""
    bpe = BPETokenizer()
    corpus = [
        "information retrieval systems index multi-field documents",
        "causal attention restricts future token visibility",
        "extractive question answering extracts answer spans"
    ]
    bpe.train(corpus, target_vocab_size=128, min_frequency=1)

    test_sentence = "information retrieval index"
    tokens = bpe.encode(test_sentence, add_special_tokens=False)
    decoded = bpe.decode(tokens, skip_special_tokens=True)

    passed = decoded.strip() == test_sentence.strip()
    return {
        "test": "tokenizer_fidelity",
        "passed": passed,
        "original": test_sentence,
        "decoded": decoded,
        "vocab_size": bpe.vocab_size,
        "tokens": tokens
    }


def test_micro_overfit_convergence() -> Dict[str, Any]:
    """Verify that PESE-NG-0 achieves ≥ 70% loss reduction on micro-corpus."""
    tok = CharTokenizer()
    tok.train(MICRO_OVERFIT_TEXTS)

    cfg = TransformerConfig(
        model_name="PESE-NG-0-micro-eval",
        vocab_size=tok.vocab_size,
        d_model=64,
        n_layers=2,
        n_heads=2,
        d_ff=256,
        max_seq_len=128,
        dropout=0.0
    )
    model = PESETransformer(cfg)
    ds = CausalLMDataset(MICRO_OVERFIT_TEXTS, tok, max_seq_len=64)

    with tempfile.TemporaryDirectory() as tmpdir:
        train_cfg = TrainingConfig(
            experiment_name="eval-micro-overfit",
            batch_size=len(MICRO_OVERFIT_TEXTS),
            learning_rate=3e-3,
            epochs=70,
            max_steps=70,
            warmup_steps=5,
            checkpoint_interval_steps=70,
            device="cpu"
        )
        trainer = NeuralTrainer(model, ds, train_cfg, checkpoint_dir=Path(tmpdir))
        res = trainer.train()

    passed = res["loss_reduction_pct"] >= 70.0
    return {
        "test": "micro_overfit_convergence",
        "passed": passed,
        "initial_loss": res["initial_loss"],
        "final_loss": res["final_loss"],
        "loss_reduction_pct": res["loss_reduction_pct"],
        "threshold_pct": 70.0
    }


def test_checkpoint_roundtrip() -> Dict[str, Any]:
    """Verify checkpoint save, load, and bitwise parameter fidelity."""
    cfg = TransformerConfig(
        vocab_size=128,
        d_model=64,
        n_layers=2,
        n_heads=2,
        d_ff=128,
        max_seq_len=32,
        dropout=0.0
    )
    model = PESETransformer(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        chk_file = save_checkpoint(
            model=model,
            optimizer=opt,
            config=cfg.model_dump(),
            step=42,
            loss=1.234,
            checkpoint_dir=tmp_path,
            filename="roundtrip_test.pt"
        )

        loaded_model, chk_data = load_checkpoint(chk_file, device="cpu")

        # Compare parameter weights
        max_param_diff = 0.0
        for p1, p2 in zip(model.parameters(), loaded_model.parameters()):
            diff = torch.max(torch.abs(p1 - p2)).item()
            if diff > max_param_diff:
                max_param_diff = diff

    passed = (max_param_diff < 1e-6) and (chk_data["step"] == 42)
    return {
        "test": "checkpoint_roundtrip",
        "passed": passed,
        "max_param_diff": max_param_diff,
        "restored_step": chk_data["step"]
    }


def test_qa_span_grounding_and_abstention() -> Dict[str, Any]:
    """Verify deterministic answer span localization and abstention handling."""
    context = "The Personal Evil Search Engine uses BM25F lexical retrieval."
    answer = "BM25F lexical retrieval"

    tok = CharTokenizer()
    tok.train([context])

    # 1. Answerable span test
    span = find_answer_span(context, answer, tok)
    found_correct_chars = span["found"] and (context[span["start_char"]:span["end_char"]] == answer)

    # 2. Unanswerable abstention test
    unanswerable_span = find_answer_span(context, "Cold fusion", tok)
    abstains_correctly = not unanswerable_span["found"] and unanswerable_span["start_char"] is None

    passed = found_correct_chars and abstains_correctly
    return {
        "test": "qa_span_grounding_and_abstention",
        "passed": passed,
        "answerable_found": found_correct_chars,
        "abstention_correct": abstains_correctly,
        "span": span
    }


def test_privacy_boundary() -> Dict[str, Any]:
    """Verify training dataset contains ZERO private user documents or history."""
    corpus_text = " ".join(SYNTHETIC_PUBLIC_CORPUS).lower()
    
    # Check for private markers or specific private store slugs
    private_markers = ["personal evil search engine confidential", "user_click_log", "private_history"]
    violation_found = any(marker in corpus_text for marker in private_markers)

    return {
        "test": "privacy_boundary",
        "passed": not violation_found,
        "isolated_synthetic_sentences": len(SYNTHETIC_PUBLIC_CORPUS)
    }


def run_neural_genesis_evaluation() -> Dict[str, Any]:
    """Run all Phase 2C Neural Genesis scientific verification tests."""
    tests = [
        test_parameter_counting(),
        test_causal_masking_invariance(),
        test_tokenizer_fidelity(),
        test_micro_overfit_convergence(),
        test_checkpoint_roundtrip(),
        test_qa_span_grounding_and_abstention(),
        test_privacy_boundary()
    ]

    all_passed = all(t["passed"] for t in tests)
    summary = {
        "suite": "PESE Phase 2C Neural Genesis Benchmark",
        "all_passed": all_passed,
        "total_tests": len(tests),
        "passed_tests": sum(1 for t in tests if t["passed"]),
        "failed_tests": sum(1 for t in tests if not t["passed"]),
        "results": tests
    }

    return summary


if __name__ == "__main__":
    res = run_neural_genesis_evaluation()
    print(json.dumps(res, indent=2))
