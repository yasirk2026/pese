"""
PESE-QA-0: Experiment Runner & Training Curriculum
Executes Stage A (Sanity), Stage B (Micro-Overfit), and Stage C (Public QA Training).
Persists scientific telemetry and checkpoint to checkpoints/qa/peseqa0_baseline_final.pt.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import torch

from ..configs.model_config import QAConfig, QATrainingConfig
from ..tokenization.bpe_tokenizer import BPETokenizer
from ..tokenization.char_tokenizer import CharTokenizer
from ..models.qa_reader import PESEQAReader
from ..models.registry import registry, ModelCard, ModelStatus
from ..data.contracts import QAExample
from ..data.qa_dataset import (
    build_qa_features,
    ExtractiveQADataset,
    STAGE_A_SANITY_EXAMPLES,
    STAGE_B_MICRO_OVERFIT_EXAMPLES,
    STAGE_C_PUBLIC_QA_CORPUS
)
from ..training.qa_trainer import QATrainer, DEFAULT_QA_CHECKPOINT_DIR
from ..training.checkpoint import save_checkpoint
from ..inference.qa_reader import PESEQAInferenceReader
from ..data.grouped_split import grouped_split, manifest


QA_REPORT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "qa_experiment_report.json"


def run_stage_a_sanity() -> Dict[str, Any]:
    """Stage A: Synthetic Sanity Check."""
    print("--- [STAGE A] Running QA Synthetic Sanity Check ---")
    tok = CharTokenizer()
    texts = [ex.question + " " + ex.context for ex in STAGE_A_SANITY_EXAMPLES]
    tok.train(texts)

    cfg = QAConfig(
        model_name="PESE-QA-0-sanity",
        vocab_size=tok.vocab_size,
        d_model=64,
        n_layers=2,
        n_heads=2,
        d_ff=256,
        max_seq_len=96,
        dropout=0.0
    )
    model = PESEQAReader(cfg)

    features = []
    for ex in STAGE_A_SANITY_EXAMPLES:
        features.extend(build_qa_features(ex, tok, max_seq_len=96))

    ds = ExtractiveQADataset(features)
    train_cfg = QATrainingConfig(
        experiment_name="qa-stage-a-sanity",
        batch_size=len(features),
        learning_rate=3e-3,
        epochs=30,
        max_steps=30,
        warmup_steps=2,
        checkpoint_interval_steps=30,
        device="cpu"
    )

    trainer = QATrainer(model, ds, train_cfg, checkpoint_dir=DEFAULT_QA_CHECKPOINT_DIR)
    results = trainer.train()

    print(f"Stage A Initial Loss: {results['initial_loss']} -> Final: {results['final_loss']} "
          f"(-{results['loss_reduction_pct']}%)")
    return results


def run_stage_b_micro_overfit() -> Dict[str, Any]:
    """Stage B: Micro-Overfit QA Test (Mandatory Gate)."""
    print("--- [STAGE B] Running QA Micro-Overfit Test ---")
    tok = CharTokenizer()
    texts = [ex.question + " " + ex.context for ex in STAGE_B_MICRO_OVERFIT_EXAMPLES]
    tok.train(texts)

    cfg = QAConfig(
        model_name="PESE-QA-0-micro",
        vocab_size=tok.vocab_size,
        d_model=96,
        n_layers=3,
        n_heads=3,
        d_ff=384,
        max_seq_len=128,
        dropout=0.0
    )
    model = PESEQAReader(cfg)

    features = []
    for ex in STAGE_B_MICRO_OVERFIT_EXAMPLES:
        features.extend(build_qa_features(ex, tok, max_seq_len=128))

    ds = ExtractiveQADataset(features)
    train_cfg = QATrainingConfig(
        experiment_name="qa-stage-b-micro-overfit",
        batch_size=len(features),
        learning_rate=3e-3,
        epochs=80,
        max_steps=80,
        warmup_steps=5,
        checkpoint_interval_steps=80,
        device="cpu"
    )

    trainer = QATrainer(model, ds, train_cfg, checkpoint_dir=DEFAULT_QA_CHECKPOINT_DIR)
    results = trainer.train()

    # Verify memorization
    reader = PESEQAInferenceReader(model, tok, answerability_threshold=0.45)
    correct_answers = 0
    correct_abstentions = 0
    total_eval = len(STAGE_B_MICRO_OVERFIT_EXAMPLES)

    for ex in STAGE_B_MICRO_OVERFIT_EXAMPLES:
        res = reader.read_passage(ex.question, ex.context)
        if ex.is_answerable:
            if res.answerable and res.answer and ex.answer_text and (ex.answer_text in res.answer or res.answer in ex.answer_text):
                correct_answers += 1
        else:
            if not res.answerable:
                correct_abstentions += 1

    accuracy = (correct_answers + correct_abstentions) / total_eval * 100.0
    passed = results["loss_reduction_pct"] >= 75.0 and accuracy >= 80.0

    print(f"Stage B Overfit Result: Loss Drop={results['loss_reduction_pct']}%, Memorization Accuracy={accuracy:.1f}%, Passed={passed}")
    return {
        "status": "passed" if passed else "failed",
        "loss_reduction_pct": results["loss_reduction_pct"],
        "initial_loss": results["initial_loss"],
        "final_loss": results["final_loss"],
        "memorization_accuracy": round(accuracy, 2),
        "steps_completed": results["steps_completed"],
        "history": results["history"]
    }


def run_stage_c_baseline_training() -> Dict[str, Any]:
    """Stage C: Public QA Training with BPE Tokenizer."""
    print("--- [STAGE C] Running Baseline PESE-QA-0 Public Training ---")
    
    # 1. Train Subword Tokenizer on Public QA Corpus + Synthetic CS Data
    all_public_examples = STAGE_B_MICRO_OVERFIT_EXAMPLES + STAGE_C_PUBLIC_QA_CORPUS
    from ...evaluation.qa_reader_dataset import BENCHMARK_QA_ITEMS
    split_examples = grouped_split(all_public_examples, forbidden_contexts=[ex.context for ex in BENCHMARK_QA_ITEMS])
    split_manifest = manifest(split_examples)
    training_texts = [ex.question + " " + ex.context for ex in split_examples["train"]]

    bpe = BPETokenizer()
    bpe.train(training_texts, target_vocab_size=450, min_frequency=1)

    # 2. Configure PESE-QA-0 Architecture (~850k parameters)
    cfg = QAConfig(
        model_name="PESE-QA-0",
        vocab_size=bpe.vocab_size,
        d_model=128,
        n_layers=4,
        n_heads=4,
        d_ff=512,
        max_seq_len=128,
        dropout=0.05
    )
    model = PESEQAReader(cfg)
    summary = model.get_summary()

    # 3. Build features
    features: List[Any] = []
    train_feats = [f for ex in split_examples["train"] for f in build_qa_features(ex, bpe, max_seq_len=128)]
    val_feats = [f for ex in split_examples["validation"] for f in build_qa_features(ex, bpe, max_seq_len=128)]
    DEFAULT_QA_CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    (DEFAULT_QA_CHECKPOINT_DIR / "source-split-manifest.json").write_text(json.dumps(split_manifest, indent=2), encoding="utf-8")

    train_ds = ExtractiveQADataset(train_feats)
    val_ds = ExtractiveQADataset(val_feats) if val_feats else None

    # 4. Train Model
    train_cfg = QATrainingConfig(
        experiment_name="peseqa0-public-baseline",
        batch_size=8,
        learning_rate=2e-3,
        min_learning_rate=1e-4,
        epochs=60,
        max_steps=300,
        warmup_steps=20,
        eval_interval_steps=25,
        checkpoint_interval_steps=100,
        device="cpu"
    )

    trainer = QATrainer(
        model=model,
        train_dataset=train_ds,
        val_dataset=val_ds,
        config=train_cfg,
        checkpoint_dir=DEFAULT_QA_CHECKPOINT_DIR
    )
    train_results = trainer.train()

    # 5. Save Final Checkpoint
    final_chk_path = save_checkpoint(
        model=model,
        optimizer=trainer.optimizer,
        config=cfg.model_dump(),
        step=train_results["steps_completed"],
        loss=train_results["final_loss"],
        metrics={"experiment": "peseqa0-public-baseline", "loss_reduction": train_results["loss_reduction_pct"]},
        checkpoint_dir=DEFAULT_QA_CHECKPOINT_DIR,
        filename="peseqa0_baseline_final.pt"
    )

    # Save tokenizer vocabulary alongside checkpoint
    vocab_path = DEFAULT_QA_CHECKPOINT_DIR / "peseqa0_tokenizer.json"
    with open(vocab_path, "w", encoding="utf-8") as f:
        json.dump({
            "vocab": bpe.vocab,
            "merges": [list(m) for m in bpe.merges]
        }, f, indent=2)

    # 6. Sample Inference
    reader = PESEQAInferenceReader(model, bpe, answerability_threshold=0.45)
    sample_q = "What does BM25F stand for?"
    sample_c = "BM25F stands for Best Matching 25 with Fields, an extension of the Okapi BM25 ranking function."
    sample_res = reader.read_passage(sample_q, sample_c)

    sample_unans_q = "Who is the king of Mars?"
    sample_unans_res = reader.read_passage(sample_unans_q, sample_c)

    # 7. Update Model Registry
    registry.register(
        ModelCard(
            model_id="PESE-QA-0",
            architecture="Bidirectional Transformer Reader (Pre-LayerNorm)",
            status=ModelStatus.EXPERIMENT,
            description="PESE-QA-0 foundational extractive reading comprehension reader (~860k parameters). Extracts exact answer spans with abstention support.",
            config=cfg.model_dump(),
            total_parameters=summary["total_parameters"],
            allowed_for_ranking=False,
            allowed_for_answers=False,
            registered_at=datetime.utcnow().isoformat() + "Z",
            checkpoint_path=str(final_chk_path),
            notes=[
                "Bidirectional attention over [CLS] Question [SEP] Passage [SEP] without causal masking.",
                f"Achieved {train_results['loss_reduction_pct']}% loss reduction over {train_results['steps_completed']} steps.",
                "Trained on public synthetic corpus with zero private user data.",
                "Supports abstention ('NO EVIDENCE = NO ANSWER'). Runs in shadow mode."
            ]
        )
    )

    return {
        "model_summary": summary,
        "train_results": train_results,
        "checkpoint": str(final_chk_path),
        "tokenizer_vocab_path": str(vocab_path),
        "sample_extractions": [
            {
                "question": sample_q,
                "answer": sample_res.answer,
                "answerable": sample_res.answerable,
                "confidence": sample_res.answer_confidence,
            },
            {
                "question": sample_unans_q,
                "answer": sample_unans_res.answer,
                "answerable": sample_unans_res.answerable,
                "confidence": sample_unans_res.answer_confidence,
            }
        ]
    }


def run_all_qa_experiments() -> Dict[str, Any]:
    """Execute complete Phase 2D QA training pipeline."""
    QA_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    stage_a = run_stage_a_sanity()
    stage_b = run_stage_b_micro_overfit()
    stage_c = run_stage_c_baseline_training()

    report = {
        "title": "PESE-QA-0 Scientific Reading Comprehension Report",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "device": "cpu",
        "pytorch_version": torch.__version__,
        "privacy_guarantee": "ZERO private user documents, ZERO search queries, ZERO user history were included in training datasets.",
        "stage_a_sanity": stage_a,
        "stage_b_micro_overfit": stage_b,
        "stage_c_baseline": stage_c,
    }

    with open(QA_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"QA experiment report written to {QA_REPORT_PATH}")
    return report


if __name__ == "__main__":
    run_all_qa_experiments()
