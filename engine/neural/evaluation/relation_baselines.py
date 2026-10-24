"""
PESE Neural Genesis: Baseline Evaluation Harness
Phase N1: PESE-REL-DATA-0

Evaluates non-neural and deterministic heuristic baselines against the
relational dataset to establish benchmark difficulty and highlight failure spaces.

Baselines:
1. Majority Class (Baseline Sanity)
2. Lexical Jaccard Overlap
3. Keyword / Content Term Overlap
4. Deterministic Rule Engine (AnswerRelevanceGate)
5. Dense Semantic Similarity (BGE small v1.5 Cosine)

ZERO neural training. Evaluates how existing methods struggle with:
'SAME TOPIC != ANSWERS THE QUESTION'.
"""

import re
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict

from ..data.relation_contracts import RelationExample, RelationLabel, NegativeReason, ContrastType
from ..data.manifest import load_frozen_dataset


def extract_content_tokens(text: str) -> List[str]:
    """Tokenize and remove basic English stop words."""
    stopwords = {
        "what", "when", "who", "where", "why", "how", "which", "whose", "whom",
        "does", "do", "did", "is", "are", "was", "were", "can", "could", "will",
        "would", "shall", "should", "the", "a", "an", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "and", "or", "but", "it", "its", "this", "that"
    }
    tokens = re.findall(r"\w+", text.lower())
    return [t for t in tokens if t not in stopwords and len(t) > 1]


def compute_metrics(
    y_true: List[str],
    y_pred: List[str]
) -> Dict[str, Any]:
    """
    Computes Accuracy, Precision, Recall, F1 for the ANSWERS class,
    along with the confusion matrix (TP, FP, TN, FN).
    """
    assert len(y_true) == len(y_pred)
    tp = fp = tn = fn = 0

    for true_lbl, pred_lbl in zip(y_true, y_pred):
        if true_lbl == RelationLabel.ANSWERS.value:
            if pred_lbl == RelationLabel.ANSWERS.value:
                tp += 1
            else:
                fn += 1
        else:
            if pred_lbl == RelationLabel.ANSWERS.value:
                fp += 1
            else:
                tn += 1

    total = len(y_true)
    accuracy = (tp + tn) / total if total > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "total": total
    }


class MajorityBaseline:
    """Always predicts the majority class observed on the training split."""
    def __init__(self):
        self.majority_label = RelationLabel.ANSWERS.value

    def fit(self, train_examples: List[RelationExample]):
        counts = defaultdict(int)
        for ex in train_examples:
            counts[ex.label.value] += 1
        self.majority_label = max(counts.keys(), key=lambda k: counts[k])

    def predict(self, example: RelationExample) -> str:
        return self.majority_label


class JaccardOverlapBaseline:
    """Predicts ANSWERS if token Jaccard similarity exceeds a calibrated threshold."""
    def __init__(self, threshold: float = 0.25):
        self.threshold = threshold

    def _sim(self, q: str, e: str) -> float:
        set_q = set(re.findall(r"\w+", q.lower()))
        set_e = set(re.findall(r"\w+", e.lower()))
        if not set_q or not set_e:
            return 0.0
        return len(set_q & set_e) / len(set_q | set_e)

    def fit(self, train_examples: List[RelationExample]):
        # Search for threshold that maximizes F1 on train
        best_f1 = -1.0
        best_thresh = 0.20
        scores = [self._sim(ex.question, ex.evidence) for ex in train_examples]
        y_true = [ex.label.value for ex in train_examples]

        for t in np.linspace(0.05, 0.60, 25):
            preds = [RelationLabel.ANSWERS.value if s >= t else RelationLabel.DOES_NOT_ANSWER.value for s in scores]
            m = compute_metrics(y_true, preds)
            if m["f1"] > best_f1:
                best_f1 = m["f1"]
                best_thresh = float(t)
        self.threshold = best_thresh

    def predict(self, example: RelationExample) -> str:
        s = self._sim(example.question, example.evidence)
        return RelationLabel.ANSWERS.value if s >= self.threshold else RelationLabel.DOES_NOT_ANSWER.value


class KeywordCoverageBaseline:
    """Predicts ANSWERS if query content word coverage exceeds a calibrated threshold."""
    def __init__(self, threshold: float = 0.50):
        self.threshold = threshold

    def _sim(self, q: str, e: str) -> float:
        q_tokens = extract_content_tokens(q)
        if not q_tokens:
            return 0.0
        e_tokens = set(re.findall(r"\w+", e.lower()))
        matched = sum(1 for t in q_tokens if t in e_tokens)
        return matched / len(q_tokens)

    def fit(self, train_examples: List[RelationExample]):
        best_f1 = -1.0
        best_thresh = 0.50
        scores = [self._sim(ex.question, ex.evidence) for ex in train_examples]
        y_true = [ex.label.value for ex in train_examples]

        for t in np.linspace(0.1, 0.9, 17):
            preds = [RelationLabel.ANSWERS.value if s >= t else RelationLabel.DOES_NOT_ANSWER.value for s in scores]
            m = compute_metrics(y_true, preds)
            if m["f1"] > best_f1:
                best_f1 = m["f1"]
                best_thresh = float(t)
        self.threshold = best_thresh

    def predict(self, example: RelationExample) -> str:
        s = self._sim(example.question, example.evidence)
        return RelationLabel.ANSWERS.value if s >= self.threshold else RelationLabel.DOES_NOT_ANSWER.value


class AnswerRelevanceGateBaseline:
    """
    Evaluates PESE's deterministic production AnswerRelevanceGate rule engine.
    """
    def __init__(self):
        from ...query_analysis.analyzer import QueryAnalyzer
        from ...query_analysis.spelling import CorpusSpellingCorrector
        from ...passages.answer_relevance import AnswerRelevanceGate
        corrector = CorpusSpellingCorrector()
        self.analyzer = QueryAnalyzer(spelling_corrector=corrector)
        self.gate = AnswerRelevanceGate()

    def predict(self, example: RelationExample) -> str:
        analyzed = self.analyzer.analyze_query(example.question)
        # In this task, candidate and evidence are the candidate passage sentence
        result = self.gate.evaluate(
            query=example.question,
            candidate=example.evidence,
            passage_text=example.evidence,
            analyzed_query=analyzed
        )
        if result.decision == "PASS":
            return RelationLabel.ANSWERS.value
        else:
            return RelationLabel.DOES_NOT_ANSWER.value


class DenseSemanticBaseline:
    """
    Dense cosine similarity baseline using BGE (or local fastembed / mock).
    """
    def __init__(self, threshold: float = 0.70):
        self.threshold = threshold
        from ...semantic.provider import FastembedProvider, DeterministicMockProvider
        try:
            self.provider = FastembedProvider()
            # Warm up
            self.provider.embed_query("warmup query")
        except Exception:
            self.provider = DeterministicMockProvider()

    def _sim(self, q: str, e: str) -> float:
        v_q = self.provider.embed_query(q)
        v_e = self.provider.embed_query(e)
        dot = float(np.dot(v_q, v_e))
        norm_q = float(np.linalg.norm(v_q))
        norm_e = float(np.linalg.norm(v_e))
        denom = max(1e-9, norm_q * norm_e)
        return dot / denom

    def fit(self, train_examples: List[RelationExample]):
        scores = [self._sim(ex.question, ex.evidence) for ex in train_examples]
        y_true = [ex.label.value for ex in train_examples]

        best_f1 = -1.0
        best_thresh = 0.70
        for t in np.linspace(0.40, 0.90, 26):
            preds = [RelationLabel.ANSWERS.value if s >= t else RelationLabel.DOES_NOT_ANSWER.value for s in scores]
            m = compute_metrics(y_true, preds)
            if m["f1"] > best_f1:
                best_f1 = m["f1"]
                best_thresh = float(t)
        self.threshold = best_thresh

    def predict(self, example: RelationExample) -> str:
        s = self._sim(example.question, example.evidence)
        return RelationLabel.ANSWERS.value if s >= self.threshold else RelationLabel.DOES_NOT_ANSWER.value


def evaluate_baseline_on_split(
    model: Any,
    examples: List[RelationExample]
) -> Dict[str, Any]:
    """Runs a baseline model on a list of examples and analyzes failure classes."""
    y_true = [ex.label.value for ex in examples]
    y_pred = [model.predict(ex) for ex in examples]

    overall_metrics = compute_metrics(y_true, y_pred)

    # Detailed breakdown on Hard Negatives
    hard_neg_fp = defaultdict(int)
    hard_neg_total = defaultdict(int)

    # Detailed breakdown on Low-Overlap Positives
    low_overlap_fn = 0
    low_overlap_total = 0

    # Challenge subset breakdown
    chal_true = []
    chal_pred = []

    for ex, true_lbl, pred_lbl in zip(examples, y_true, y_pred):
        if ex.is_challenge:
            chal_true.append(true_lbl)
            chal_pred.append(pred_lbl)

        if true_lbl == RelationLabel.DOES_NOT_ANSWER.value:
            reason = ex.negative_reason.value if ex.negative_reason else "UNKNOWN"
            hard_neg_total[reason] += 1
            if pred_lbl == RelationLabel.ANSWERS.value:
                hard_neg_fp[reason] += 1

        if true_lbl == RelationLabel.ANSWERS.value:
            if ex.contrast_type == ContrastType.PARAPHRASE_LOW_OVERLAP:
                low_overlap_total += 1
                if pred_lbl == RelationLabel.DOES_NOT_ANSWER.value:
                    low_overlap_fn += 1

    challenge_metrics = compute_metrics(chal_true, chal_pred) if chal_true else {}

    # False Positive Rates on Hard Negatives
    hard_neg_rates = {}
    for r, total in hard_neg_total.items():
        fp = hard_neg_fp[r]
        hard_neg_rates[r] = {
            "fp_count": fp,
            "total": total,
            "fp_rate": round(fp / total, 4) if total > 0 else 0.0
        }

    return {
        "overall": overall_metrics,
        "challenge_subset": challenge_metrics,
        "hard_negatives": hard_neg_rates,
        "low_overlap_recall": {
            "fn_count": low_overlap_fn,
            "total": low_overlap_total,
            "recall": round((low_overlap_total - low_overlap_fn) / low_overlap_total, 4) if low_overlap_total > 0 else 0.0
        }
    }


def run_all_baselines(splits: Optional[Dict[str, List[RelationExample]]] = None) -> Dict[str, Any]:
    """
    Runs full benchmark evaluation across all baselines on validation and test sets.
    """
    if splits is None:
        splits = load_frozen_dataset()

    train_data = splits["train"]
    val_data = splits["validation"]
    test_data = splits["test"]

    baselines = {
        "majority": MajorityBaseline(),
        "jaccard_overlap": JaccardOverlapBaseline(),
        "keyword_coverage": KeywordCoverageBaseline(),
        "rule_gate": AnswerRelevanceGateBaseline(),
        "bge_cosine": DenseSemanticBaseline(),
    }

    # Fit baselines with tunable thresholds on train
    for name, b in baselines.items():
        if hasattr(b, "fit"):
            b.fit(train_data)

    results = {}
    for name, b in baselines.items():
        val_eval = evaluate_baseline_on_split(b, val_data)
        test_eval = evaluate_baseline_on_split(b, test_data)
        
        results[name] = {
            "validation": val_eval,
            "test": test_eval,
            "parameters": {
                "threshold": getattr(b, "threshold", None),
                "majority_label": getattr(b, "majority_label", None)
            }
        }

    return results


if __name__ == "__main__":
    import pprint
    print("Executing baseline benchmark evaluation on PESE-REL-DATA-0...")
    benchmark_results = run_all_baselines()
    for b_name, data in benchmark_results.items():
        print(f"\n==================== BASELINE: {b_name} ====================")
        print("Validation Overall:", data["validation"]["overall"])
        print("Validation Challenge:", data["validation"]["challenge_subset"])
        print("Test Overall:", data["test"]["overall"])
        print("Test Challenge:", data["test"]["challenge_subset"])
