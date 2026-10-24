"""
PESE Neural Genesis: PESE-Rel-0 Evaluation & Diagnostic Engine
Phase N2: Scientific Evaluation, Error Taxonomy & Calibration Analysis

Loads frozen PESE-Rel-0 checkpoint and executes exhaustive evaluation:
1. Overall Test Split Metrics (Accuracy, Precision, Recall, F1, Confusion Matrix)
2. Challenge Subset Performance
3. Error Taxonomy Breakdown across Negative Diagnostic Classes
4. Low-Overlap Positive Recall & High-Overlap Negative Rejection
5. Confidence Calibration Buckets
6. Operating Threshold Sweep (0.50 to 0.90)
7. Comparative Baseline Benchmarks
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from ..configs.model_config import RelationConfig
from ..models.relation_classifier import PESERelationClassifier
from ..tokenization.relation_tokenizer import RelationTokenizer
from ..data.relation_contracts import RelationExample, RelationLabel, NegativeReason, ContrastType
from ..data.relation_dataset import RelationDataset
from ..data.manifest import load_frozen_dataset

CHECKPOINT_DIR = Path(__file__).resolve().parent.parent / "checkpoints" / "relation"
DEFAULT_CHECKPOINT = CHECKPOINT_DIR / "peserel0_best.pt"
DEFAULT_TOKENIZER = CHECKPOINT_DIR / "peserel0_tokenizer.json"


def compute_binary_metrics(y_true: List[int], y_pred: List[int]) -> Dict[str, Any]:
    """Computes binary classification metrics for class 1 (ANSWERS)."""
    assert len(y_true) == len(y_pred)
    tp = fp = tn = fn = 0

    for t, p in zip(y_true, y_pred):
        if t == 1:
            if p == 1:
                tp += 1
            else:
                fn += 1
        else:
            if p == 1:
                fp += 1
            else:
                tn += 1

    total = len(y_true)
    acc = (tp + tn) / total if total > 0 else 0.0
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

    return {
        "accuracy": round(float(acc), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1": round(float(f1), 4),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "total": total
    }


class RelationEvaluator:
    """
    Exhaustive scientific evaluation harness for PESE-Rel-0.
    """

    def __init__(
        self,
        checkpoint_path: Path = DEFAULT_CHECKPOINT,
        tokenizer_path: Path = DEFAULT_TOKENIZER,
        device: str = "cpu"
    ):
        self.device = torch.device(device)
        self.checkpoint_path = checkpoint_path
        self.tokenizer_path = tokenizer_path

        # 1. Load tokenizer
        self.tokenizer = RelationTokenizer.load(str(tokenizer_path))

        # 2. Load model from checkpoint
        ckpt = torch.load(checkpoint_path, map_location=self.device)
        self.config = RelationConfig(**ckpt["config"])
        self.model = PESERelationClassifier(self.config).to(self.device)
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.eval()

        self.checkpoint_metadata = {
            "epoch": ckpt.get("epoch"),
            "global_step": ckpt.get("global_step"),
            "saved_at_utc": ckpt.get("saved_at_utc"),
            "val_metrics": ckpt.get("validation_metrics"),
        }

    def predict_examples(
        self,
        examples: List[RelationExample],
        batch_size: int = 16
    ) -> List[Dict[str, Any]]:
        """
        Runs model inference across a list of examples.
        Returns prediction dicts with probabilities, logits, and predicted label.
        """
        dataset = RelationDataset(examples, self.tokenizer, self.config.max_seq_len)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)

        results = []
        example_idx = 0

        with torch.no_grad():
            for input_ids, token_type_ids, attention_mask, labels, _ in loader:
                input_ids = input_ids.to(self.device)
                token_type_ids = token_type_ids.to(self.device)
                attention_mask = attention_mask.to(self.device)

                logits = self.model(input_ids, token_type_ids, attention_mask)
                probs = F.softmax(logits, dim=-1).cpu().numpy()
                raw_logits = logits.cpu().numpy()

                for b in range(len(probs)):
                    ex = examples[example_idx]
                    p_no_ans = float(probs[b][0])
                    p_ans = float(probs[b][1])
                    pred_class = 1 if p_ans >= 0.50 else 0
                    pred_label = RelationLabel.ANSWERS.value if pred_class == 1 else RelationLabel.DOES_NOT_ANSWER.value
                    confidence = max(p_ans, p_no_ans)

                    results.append({
                        "id": ex.id,
                        "question": ex.question,
                        "evidence": ex.evidence,
                        "true_label": ex.label.value,
                        "true_class": 1 if ex.label == RelationLabel.ANSWERS else 0,
                        "predicted_label": pred_label,
                        "predicted_class": pred_class,
                        "prob_answers": round(p_ans, 4),
                        "prob_does_not_answer": round(p_no_ans, 4),
                        "confidence": round(confidence, 4),
                        "logit_no_ans": round(float(raw_logits[b][0]), 4),
                        "logit_ans": round(float(raw_logits[b][1]), 4),
                        "is_correct": bool(pred_label == ex.label.value),
                        "is_challenge": ex.is_challenge,
                        "negative_reason": ex.negative_reason.value if ex.negative_reason else None,
                        "contrast_type": ex.contrast_type.value if ex.contrast_type else None,
                        "answer_type": ex.answer_type,
                        "scenario_family": ex.scenario_family,
                    })
                    example_idx += 1

        return results

    def evaluate_split(
        self,
        examples: List[RelationExample],
        split_name: str = "test"
    ) -> Dict[str, Any]:
        """
        Computes exhaustive evaluation report on a given set of examples.
        """
        predictions = self.predict_examples(examples)

        y_true = [p["true_class"] for p in predictions]
        y_pred = [p["predicted_class"] for p in predictions]

        # 1. Overall Metrics
        overall = compute_binary_metrics(y_true, y_pred)

        # 2. Challenge Subset Metrics
        chal_preds = [p for p in predictions if p["is_challenge"]]
        chal_true = [p["true_class"] for p in chal_preds]
        chal_pred = [p["predicted_class"] for p in chal_preds]
        challenge_metrics = compute_binary_metrics(chal_true, chal_pred) if chal_true else {}

        # 3. Error Taxonomy across Diagnostic Classes
        neg_reasons = defaultdict(list)
        contrast_groups = defaultdict(list)
        for p in predictions:
            if p["true_class"] == 0:
                reason = p["negative_reason"] or "UNKNOWN"
                neg_reasons[reason].append(p)
            if p["contrast_type"]:
                contrast_groups[p["contrast_type"]].append(p)

        error_taxonomy = {}
        for reason, items in neg_reasons.items():
            total_items = len(items)
            fp_items = sum(1 for item in items if item["predicted_class"] == 1)
            correct_items = total_items - fp_items
            error_taxonomy[reason] = {
                "total": total_items,
                "false_positives": fp_items,
                "fp_rate": round(fp_items / total_items, 4) if total_items > 0 else 0.0,
                "rejection_rate": round(correct_items / total_items, 4) if total_items > 0 else 0.0
            }

        # 4. Low-Overlap Positives Recall & High-Overlap Negatives Rejection
        low_overlap_items = [p for p in predictions if p["contrast_type"] == ContrastType.PARAPHRASE_LOW_OVERLAP.value]
        low_overlap_total = len(low_overlap_items)
        low_overlap_tp = sum(1 for item in low_overlap_items if item["predicted_class"] == 1)
        low_overlap_recall = round(low_overlap_tp / low_overlap_total, 4) if low_overlap_total > 0 else 0.0

        high_overlap_items = [p for p in predictions if p["contrast_type"] == ContrastType.HIGH_OVERLAP_DISTRACTOR.value]
        high_overlap_total = len(high_overlap_items)
        high_overlap_fp = sum(1 for item in high_overlap_items if item["predicted_class"] == 1)
        high_overlap_rejection = round((high_overlap_total - high_overlap_fp) / high_overlap_total, 4) if high_overlap_total > 0 else 0.0

        # 5. Confidence Calibration Buckets
        calibration_buckets = {}
        bins = [(0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 0.90), (0.90, 1.00)]
        for low, high in bins:
            b_items = [p for p in predictions if (low <= p["confidence"] <= high if high == 1.0 else low <= p["confidence"] < high)]
            count = len(b_items)
            correct = sum(1 for item in b_items if item["is_correct"])
            acc = round(correct / count, 4) if count > 0 else 0.0
            calibration_buckets[f"{low:.2f}-{high:.2f}"] = {
                "count": count,
                "correct": correct,
                "accuracy": acc
            }

        # 6. Threshold Sweep for P(ANSWERS)
        threshold_sweep = {}
        thresholds = [0.50, 0.60, 0.70, 0.80, 0.85, 0.90]
        for t in thresholds:
            t_pred = [1 if p["prob_answers"] >= t else 0 for p in predictions]
            t_metrics = compute_binary_metrics(y_true, t_pred)
            threshold_sweep[f"{t:.2f}"] = t_metrics

        return {
            "split_name": split_name,
            "overall": overall,
            "challenge_subset": challenge_metrics,
            "error_taxonomy": error_taxonomy,
            "low_overlap_positives": {
                "total": low_overlap_total,
                "true_positives": low_overlap_tp,
                "recall": low_overlap_recall
            },
            "high_overlap_negatives": {
                "total": high_overlap_total,
                "false_positives": high_overlap_fp,
                "rejection_rate": high_overlap_rejection
            },
            "calibration_buckets": calibration_buckets,
            "threshold_sweep": threshold_sweep,
            "predictions": predictions
        }


def run_evaluation() -> Dict[str, Any]:
    """Runs evaluation on Validation and Test splits and writes summary report."""
    splits = load_frozen_dataset()
    evaluator = RelationEvaluator()

    val_report = evaluator.evaluate_split(splits["validation"], split_name="validation")
    test_report = evaluator.evaluate_split(splits["test"], split_name="test")

    summary = {
        "model_name": evaluator.config.model_name,
        "checkpoint_path": str(evaluator.checkpoint_path),
        "checkpoint_metadata": evaluator.checkpoint_metadata,
        "validation": {
            "overall": val_report["overall"],
            "challenge_subset": val_report["challenge_subset"],
            "low_overlap_positives": val_report["low_overlap_positives"],
            "high_overlap_negatives": val_report["high_overlap_negatives"],
        },
        "test": {
            "overall": test_report["overall"],
            "challenge_subset": test_report["challenge_subset"],
            "error_taxonomy": test_report["error_taxonomy"],
            "low_overlap_positives": test_report["low_overlap_positives"],
            "high_overlap_negatives": test_report["high_overlap_negatives"],
            "calibration_buckets": test_report["calibration_buckets"],
            "threshold_sweep": test_report["threshold_sweep"],
        }
    }

    report_path = CHECKPOINT_DIR / "evaluation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary, val_report, test_report


if __name__ == "__main__":
    print("Executing scientific evaluation for PESE-Rel-0...")
    summary, val_rep, test_rep = run_evaluation()
    print("\n==================== VALIDATION OVERALL ====================")
    print(val_rep["overall"])
    print("\n==================== TEST OVERALL ====================")
    print(test_rep["overall"])
    print("\n==================== TEST CHALLENGE ====================")
    print(test_rep["challenge_subset"])
    print("\n==================== ERROR TAXONOMY ====================")
    for k, v in test_rep["error_taxonomy"].items():
        print(f"{k}: {v}")
