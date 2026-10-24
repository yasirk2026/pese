"""
PESE-QA-0 Scientific Reading Evaluation Runner
Evaluates Exact Match, Token F1, Answerability Accuracy, No-Answer Precision/Recall/F1,
Multi-Fact Disambiguation, and Historical Regression Tests.
"""

import json
import collections
import string
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

from ..neural.training.checkpoint import load_checkpoint, DEFAULT_QA_CHECKPOINT_DIR
from ..neural.tokenization.bpe_tokenizer import BPETokenizer
from ..neural.inference.qa_reader import PESEQAInferenceReader, QAResult
from .qa_reader_dataset import BENCHMARK_QA_ITEMS, QABenchmarkItem


def normalize_answer(s: str) -> str:
    """Lower text and remove punctuation, articles and extra whitespace."""
    def remove_articles(text):
        return re.sub(r"\b(a|an|the)\b", " ", text)

    def white_space_fix(text):
        return " ".join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        return "".join(ch for ch in text if ch not in exclude)

    def lower(text):
        return text.lower()

    return white_space_fix(remove_articles(remove_punc(lower(s))))


def compute_exact_match(prediction: Optional[str], ground_truth: Optional[str]) -> bool:
    if prediction is None and ground_truth is None:
        return True
    if prediction is None or ground_truth is None:
        return False
    return normalize_answer(prediction) == normalize_answer(ground_truth)


def compute_token_f1(prediction: Optional[str], ground_truth: Optional[str]) -> float:
    if prediction is None and ground_truth is None:
        return 1.0
    if prediction is None or ground_truth is None:
        return 0.0

    pred_tokens = normalize_answer(prediction).split()
    gt_tokens = normalize_answer(ground_truth).split()

    common = collections.Counter(pred_tokens) & collections.Counter(gt_tokens)
    num_same = sum(common.values())
    if len(pred_tokens) == 0 or len(gt_tokens) == 0:
        return 1.0 if pred_tokens == gt_tokens else 0.0
    if num_same == 0:
        return 0.0
    precision = 1.0 * num_same / len(pred_tokens)
    recall = 1.0 * num_same / len(gt_tokens)
    return (2 * precision * recall) / (precision + recall)


def run_qa_benchmark(reader: Optional[PESEQAInferenceReader] = None) -> Dict[str, Any]:
    """Execute complete PESE-QA benchmark suite."""
    if reader is None:
        chk_file = DEFAULT_QA_CHECKPOINT_DIR / "peseqa0_baseline_final.pt"
        vocab_file = DEFAULT_QA_CHECKPOINT_DIR / "peseqa0_tokenizer.json"
        if not chk_file.exists() or not vocab_file.exists():
            return {"error": "PESE-QA-0 checkpoint not found"}

        model, _ = load_checkpoint(chk_file, device="cpu")
        with open(vocab_file, "r", encoding="utf-8") as f:
            vdata = json.load(f)
        tok = BPETokenizer(vocab=vdata["vocab"], merges=[tuple(m) for m in vdata["merges"]])
        reader = PESEQAInferenceReader(model, tok, answerability_threshold=0.50)

    total = len(BENCHMARK_QA_ITEMS)
    exact_matches = 0
    total_f1 = 0.0

    # Answerability confusion matrix
    tp = 0  # Answerable & Answered
    fp = 0  # Unanswerable but Answered (Hallucination)
    fn = 0  # Answerable but Abstained
    tn = 0  # Unanswerable & Abstained

    category_results: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)

    for item in BENCHMARK_QA_ITEMS:
        res: QAResult = reader.read_passage(item.question, item.context)

        em = compute_exact_match(res.answer, item.ground_truth_answer)
        f1 = compute_token_f1(res.answer, item.ground_truth_answer)

        if em:
            exact_matches += 1
        total_f1 += f1

        if item.is_answerable:
            if res.answerable and res.answer:
                tp += 1
            else:
                fn += 1
        else:
            if res.answerable and res.answer:
                fp += 1
            else:
                tn += 1

        record = {
            "id": item.id,
            "category": item.category,
            "question": item.question,
            "predicted": res.answer,
            "ground_truth": item.ground_truth_answer,
            "exact_match": em,
            "token_f1": round(f1, 4),
            "answerable": res.answerable,
            "confidence": res.answer_confidence,
            "abstention_reason": res.abstention_reason
        }
        category_results[item.category].append(record)

    # Compute aggregate metrics
    mean_em = round(exact_matches / total * 100.0, 2)
    mean_f1 = round(total_f1 / total * 100.0, 2)

    ans_acc = round((tp + tn) / total * 100.0, 2)
    no_ans_p = round(tn / max(1, tn + fn) * 100.0, 2)
    no_ans_r = round(tn / max(1, tn + fp) * 100.0, 2)
    no_ans_f1 = round(2 * no_ans_p * no_ans_r / max(1e-5, no_ans_p + no_ans_r), 2)
    hallucination_rate = round(fp / max(1, fp + tn) * 100.0, 2)

    # Category accuracies
    cat_summary = {}
    for cat, records in category_results.items():
        cat_em = sum(1 for r in records if r["exact_match"]) / len(records) * 100.0
        cat_f1 = sum(r["token_f1"] for r in records) / len(records) * 100.0
        cat_summary[cat] = {
            "count": len(records),
            "em": round(cat_em, 2),
            "f1": round(cat_f1, 2)
        }

    return {
        "suite": "PESE-QA-0 Reading Comprehension Benchmark",
        "total_evaluated": total,
        "exact_match_pct": mean_em,
        "token_f1_pct": mean_f1,
        "answerability_accuracy_pct": ans_acc,
        "no_answer_precision_pct": no_ans_p,
        "no_answer_recall_pct": no_ans_r,
        "no_answer_f1_pct": no_ans_f1,
        "hallucinated_answer_rate_pct": hallucination_rate,
        "categories": cat_summary,
        "detailed_results": category_results
    }


def run_historical_regressions(engine=None) -> Dict[str, Any]:
    """
    Execute the previously exposed development regressions:
      Historical Regression A: 'when did yasir dream pese'
      Historical Regression B: 'when did islamic golden age end'
    """
    print("\n=======================================================")
    print(" [EXECUTING HISTORICAL DEVELOPMENT REGRESSION TESTS]")
    print("=======================================================")

    if engine is None:
        from ..api.main import engine as prod_engine, reload_search_pipeline
        if prod_engine is None:
            reload_search_pipeline()
            from ..api.main import engine as prod_engine
        engine = prod_engine

    # HISTORICAL REGRESSION A
    q_a = "when did yasir dream pese"
    results_a = engine.search(q_a, limit=3)
    top_a = results_a[0] if results_a else None
    qa_trace_a = getattr(results_a, "qa_trace", {}) or {}

    # Expected: 2023, NOT October 2026
    det_ans_a = top_a.featured_answer if top_a else None
    qa_ans_a = qa_trace_a.get("shadow_answer")
    test_a_passed = bool(qa_ans_a and "2023" in qa_ans_a and "October 2026" not in qa_ans_a)

    print(f"\n--- HISTORICAL REGRESSION A: {q_a!r} ---")
    print(f"Retrieved Doc #1:      {top_a.title if top_a else 'None'}")
    print(f"Deterministic Answer:  {det_ans_a}")
    print(f"PESE-QA Shadow Answer: {qa_ans_a}")
    print(f"QA Confidence:         {qa_trace_a.get('confidence')}")
    print(f"Agreement:             {qa_trace_a.get('agreement')}")
    print(f"Status:                {'PASSED (Extracted 2023)' if test_a_passed else 'FAILED'}")

    # HISTORICAL REGRESSION B
    q_b = "when did islamic golden age end"
    results_b = engine.search(q_b, limit=3)
    top_b = results_b[0] if results_b else None
    qa_trace_b = getattr(results_b, "qa_trace", {}) or {}

    det_ans_b = top_b.featured_answer if top_b else None
    qa_ans_b = qa_trace_b.get("shadow_answer")
    is_ans_b = qa_trace_b.get("is_answerable")
    
    # Expected: extracts evidence-supported span (e.g. 13th or 14th century / 1258 CE) or abstains
    test_b_passed = bool(
        (qa_ans_b and any(term in qa_ans_b for term in ["13th", "14th", "1258", "Mongol"]))
        or (not is_ans_b and qa_ans_b is None)
    )

    print(f"\n--- HISTORICAL REGRESSION B: {q_b!r} ---")
    print(f"Retrieved Doc #1:      {top_b.title if top_b else 'None'}")
    print(f"Deterministic Answer:  {det_ans_b}")
    print(f"PESE-QA Shadow Answer: {qa_ans_b}")
    print(f"Answerable:            {is_ans_b}")
    print(f"QA Confidence:         {qa_trace_b.get('confidence')}")
    print(f"Status:                {'PASSED (Evidence-Supported)' if test_b_passed else 'FAILED'}")

    return {
        "regression_a": {
            "query": q_a,
            "retrieved_doc": top_a.title if top_a else None,
            "deterministic_answer": det_ans_a,
            "qa_shadow_answer": qa_ans_a,
            "qa_confidence": qa_trace_a.get("confidence"),
            "agreement": qa_trace_a.get("agreement"),
            "passed": test_a_passed
        },
        "regression_b": {
            "query": q_b,
            "retrieved_doc": top_b.title if top_b else None,
            "deterministic_answer": det_ans_b,
            "qa_shadow_answer": qa_ans_b,
            "is_answerable": is_ans_b,
            "qa_confidence": qa_trace_b.get("confidence"),
            "passed": test_b_passed
        }
    }


if __name__ == "__main__":
    benchmark_res = run_qa_benchmark()
    print("\n=======================================================")
    print(" [PESE-QA-0 BENCHMARK SUMMARY REPORT]")
    print("=======================================================")
    print(f"Total Evaluated:              {benchmark_res['total_evaluated']}")
    print(f"Exact Match (EM):             {benchmark_res['exact_match_pct']}%")
    print(f"Token F1:                     {benchmark_res['token_f1_pct']}%")
    print(f"Answerability Accuracy:       {benchmark_res['answerability_accuracy_pct']}%")
    print(f"No-Answer F1:                 {benchmark_res['no_answer_f1_pct']}%")
    print(f"Hallucinated Answer Rate:     {benchmark_res['hallucinated_answer_rate_pct']}%")

    regression_res = run_historical_regressions()

    # Persist benchmark evaluation and blind test telemetry to report
    report_path = Path(__file__).resolve().parent.parent / "data" / "qa_experiment_report.json"
    if report_path.exists():
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                rep_data = json.load(f)
            rep_data["evaluation"] = benchmark_res
            rep_data["historical_regressions"] = regression_res
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(rep_data, f, indent=2)
            print(f"\n[REPORT UPDATED] Successfully wrote evaluation metrics & blind test results to {report_path.name}")
        except Exception as e:
            print(f"Failed to update report: {e}")
