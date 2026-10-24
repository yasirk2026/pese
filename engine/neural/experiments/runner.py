"""
PESE Neural Genesis: Experiment Runner
Executes micro-overfit validation, small-scale baseline training on public synthetic corpus,
measures convergence, generates sample outputs, and persists results to neural_genesis_report.json.
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import torch

from ..configs.model_config import TransformerConfig, TrainingConfig
from ..tokenization.char_tokenizer import CharTokenizer
from ..tokenization.bpe_tokenizer import BPETokenizer
from ..models.transformer import PESETransformer
from ..models.registry import registry, ModelCard, ModelStatus
from ..data.dataset import MICRO_OVERFIT_TEXTS, SYNTHETIC_PUBLIC_CORPUS, CausalLMDataset
from ..training.trainer import NeuralTrainer
from ..training.checkpoint import save_checkpoint, load_checkpoint, list_checkpoints, DEFAULT_CHECKPOINT_DIR
from ..inference.generator import NeuralGenerator


REPORT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "neural_genesis_report.json"


def run_micro_overfit_experiment() -> Dict[str, Any]:
    """
    Mandatory Micro-Overfit Test:
    Proves that PESE-NG-0 model architecture can learn, backpropagate, and reduce loss
    by at least 70% on a fixed micro-corpus without exploding or vanishing gradients.
    """
    print("--- [EXPERIMENT 1] Running Micro-Overfit Test ---")
    tok = CharTokenizer()
    tok.train(MICRO_OVERFIT_TEXTS)

    cfg = TransformerConfig(
        model_name="PESE-NG-0-micro",
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

    train_cfg = TrainingConfig(
        experiment_name="micro-overfit-validation",
        batch_size=len(MICRO_OVERFIT_TEXTS),
        learning_rate=3e-3,
        epochs=80,
        max_steps=80,
        warmup_steps=5,
        checkpoint_interval_steps=40,
        device="cpu"
    )

    trainer = NeuralTrainer(
        model=model,
        train_dataset=ds,
        config=train_cfg,
        checkpoint_dir=DEFAULT_CHECKPOINT_DIR
    )
    results = trainer.train()

    passed = results["loss_reduction_pct"] >= 70.0
    print(f"Micro-Overfit Result: Initial={results['initial_loss']}, Final={results['final_loss']}, "
          f"Reduction={results['loss_reduction_pct']}%, Passed={passed}")

    return {
        "status": "passed" if passed else "failed",
        "initial_loss": results["initial_loss"],
        "final_loss": results["final_loss"],
        "loss_reduction_pct": results["loss_reduction_pct"],
        "steps_completed": results["steps_completed"],
        "threshold_pct": 70.0,
        "history": results["history"]
    }


def run_baseline_training_experiment() -> Dict[str, Any]:
    """
    Small-Scale Baseline Experiment:
    Trains PESE-BPE-0 tokenizer and full PESE-NG-0 Transformer on the public synthetic corpus.
    Evaluates loss convergence, saves checkpoint, and performs sample generation.
    """
    print("--- [EXPERIMENT 2] Running Baseline PESE-NG-0 Training ---")
    
    # 1. Train BPE Tokenizer
    bpe_tok = BPETokenizer()
    bpe_tok.train(SYNTHETIC_PUBLIC_CORPUS, target_vocab_size=256, min_frequency=2)
    vocab_size = bpe_tok.vocab_size

    # Split corpus into 80% train, 20% validation
    split_idx = int(len(SYNTHETIC_PUBLIC_CORPUS) * 0.8)
    train_texts = SYNTHETIC_PUBLIC_CORPUS[:split_idx]
    val_texts = SYNTHETIC_PUBLIC_CORPUS[split_idx:]

    train_ds = CausalLMDataset(train_texts, bpe_tok, max_seq_len=64)
    val_ds = CausalLMDataset(val_texts, bpe_tok, max_seq_len=64)

    # 2. Configure PESE-NG-0 model (~1.0M parameters)
    model_cfg = TransformerConfig(
        model_name="PESE-NG-0",
        vocab_size=vocab_size,
        d_model=128,
        n_layers=4,
        n_heads=4,
        d_ff=512,
        max_seq_len=128,
        dropout=0.1
    )
    model = PESETransformer(model_cfg)
    summary = model.get_summary()

    # 3. Configure and run training
    train_cfg = TrainingConfig(
        experiment_name="peseng0-synthetic-baseline",
        batch_size=8,
        learning_rate=1e-3,
        epochs=30,
        max_steps=100,
        warmup_steps=10,
        eval_interval_steps=20,
        checkpoint_interval_steps=50,
        device="cpu"
    )

    trainer = NeuralTrainer(
        model=model,
        train_dataset=train_ds,
        val_dataset=val_ds,
        config=train_cfg,
        checkpoint_dir=DEFAULT_CHECKPOINT_DIR
    )
    train_results = trainer.train()

    # 4. Save definitive baseline checkpoint
    final_chk_path = save_checkpoint(
        model=model,
        optimizer=trainer.optimizer,
        config=model_cfg.model_dump(),
        step=train_results["steps_completed"],
        loss=train_results["final_loss"],
        metrics={"experiment": "peseng0-synthetic-baseline"},
        checkpoint_dir=DEFAULT_CHECKPOINT_DIR,
        filename="peseng0_baseline_final.pt"
    )

    # 5. Run sample generations
    gen = NeuralGenerator(model, bpe_tok)
    prompt_1 = "Information retrieval systems"
    sample_1 = gen.generate(prompt_1, max_new_tokens=15, temperature=0.7)
    
    prompt_2 = "Transformer decoders use"
    sample_2 = gen.generate(prompt_2, max_new_tokens=15, temperature=0.7)

    # 6. Update Model Registry
    registry.register(
        ModelCard(
            model_id="PESE-NG-0",
            architecture="Decoder-Only Causal Transformer (Pre-LayerNorm)",
            status=ModelStatus.EXPERIMENT,
            description="PESE Neural Genesis baseline trained on synthetic public technical corpus.",
            config=model_cfg.model_dump(),
            total_parameters=summary["total_parameters"],
            allowed_for_ranking=False,
            allowed_for_answers=False,
            registered_at=datetime.utcnow().isoformat() + "Z",
            checkpoint_path=str(final_chk_path),
            notes=[
                "Trained with AdamW on CPU with public synthetic corpus (zero user data).",
                f"Achieved {train_results['loss_reduction_pct']}% loss reduction over {train_results['steps_completed']} steps.",
                "Strictly isolated from production ranking and answers."
            ]
        )
    )

    return {
        "model_summary": summary,
        "tokenizer": {
            "name": "PESE-BPE-0",
            "vocab_size": vocab_size,
            "merges_count": len(bpe_tok.merges)
        },
        "train_results": train_results,
        "sample_generations": [sample_1, sample_2],
        "checkpoint": str(final_chk_path)
    }


def run_all_experiments() -> Dict[str, Any]:
    """Execute complete Neural Genesis laboratory evaluation suite."""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    micro_results = run_micro_overfit_experiment()
    baseline_results = run_baseline_training_experiment()

    # Catalog documented weaknesses honestly
    documented_weaknesses = [
        {
            "id": "W1-Small-Capacity",
            "title": "Limited Model Parameter Capacity (~1M parameters)",
            "description": "At ~1M parameters with small embedding and hidden dimensions, PESE-NG-0 is an educational laboratory prototype designed for fast CPU training rather than open-ended natural language reasoning."
        },
        {
            "id": "W2-Hallucination-Without-Grounding",
            "title": "Autoregressive Hallucination / Unsupported Generation",
            "description": "Causal language generation predicts the next most probable token statistically. Without passage grounding (PESE-QA span extraction), it may generate plausible-sounding falsehoods not supported by corpus evidence."
        },
        {
            "id": "W3-No-Extractive-Supervision",
            "title": "Absence of Extractive Span Supervision (PESE-QA-0 Future Work)",
            "description": "PESE-NG-0 was trained solely on next-token prediction, not extractive answer localization or abstention. It cannot reliably determine whether a passage answers a user query without Phase 2D extractive QA heads."
        }
    ]

    report = {
        "title": "PESE Phase 2C Neural Genesis Scientific Report",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "device": "cpu",
        "pytorch_version": torch.__version__,
        "privacy_guarantee": "ZERO private user documents, ZERO search queries, ZERO user history were included in training datasets.",
        "micro_overfit_experiment": micro_results,
        "baseline_experiment": baseline_results,
        "documented_weaknesses": documented_weaknesses,
        "checkpoints": [c["filename"] for c in list_checkpoints()]
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Neural Genesis report written to {REPORT_PATH}")
    return report


if __name__ == "__main__":
    run_all_experiments()
