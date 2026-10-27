"""Reproduce exposed Rel-0 diagnostics; never creates labels or loads a Brain.

Run from repository root: python scripts/n3_rel0_audit.py --output report.json
All data are the frozen synthetic DATA-0 and previously exposed prospective set.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(output):
    import torch
    torch.set_num_threads(2)
    from engine.neural.evaluation.relation_eval import RelationEvaluator
    from engine.neural.evaluation.diagnostic_probes import build_prospective_dataset
    from engine.neural.data.manifest import load_frozen_dataset
    from engine.intelligence.evaluation import calibration
    from engine.intelligence.evidence import digest
    splits = load_frozen_dataset()
    start = time.perf_counter()
    evaluator = RelationEvaluator()
    load_ms = (time.perf_counter()-start)*1000
    reports = {}
    for name, examples in (("frozen_test", splits["test"]), ("exposed_prospective", build_prospective_dataset())):
        predictions = evaluator.predict_examples(examples)
        latency = []
        for _ in range(20):
            start = time.perf_counter()
            evaluator.predict_examples(examples[:1])
            latency.append((time.perf_counter()-start)*1000)
        cal = calibration([p["prob_answers"] for p in predictions], [p["true_class"] for p in predictions])
        mistakes = [p for p in predictions if not p["is_correct"]]
        reports[name] = {"count": len(examples), "correct": sum(p["is_correct"] for p in predictions),
             "false_positives": sum(p["predicted_class"]==1 and p["true_class"]==0 for p in predictions),
             "errors_by_category": dict(Counter(p["negative_reason"] or p["contrast_type"] or "positive" for p in mistakes)),
             "calibration": cal, "saturated_ge_099": sum(p["confidence"]>=.99 for p in predictions),
             "input_fingerprint": digest([e.model_dump(mode="json") for e in examples]),
             "warm_batch1_p50_ms": statistics.median(latency), "warm_batch1_p95_ms": sorted(latency)[18]}
    # Family/entity disjointness is necessary, but does not remove shared relation
    # templates. Report overlap in predicate/contrast vocabulary separately.
    train_rel = {e.relation_family for e in splits["train"]}
    test_rel = {e.relation_family for e in splits["test"]}
    report = {"version": 1, "status": "EXPOSED_REGRESSION_NOT_BLIND_ACCEPTANCE",
              "python": platform.python_version(), "torch": torch.__version__, "threads": torch.get_num_threads(),
              "parameters": sum(p.numel() for p in evaluator.model.parameters()), "cold_load_ms": load_ms,
              "weight_bytes": sum(p.numel()*p.element_size() for p in evaluator.model.parameters()),
              "checkpoint_sha256": hashlib.sha256(evaluator.checkpoint_path.read_bytes()).hexdigest(),
              "tokenizer_sha256": hashlib.sha256(evaluator.tokenizer_path.read_bytes()).hexdigest(),
              "tokenizer_vocab_size": evaluator.tokenizer.vocab_size,
              "shared_train_test_relation_families": sorted(train_rel & test_rel),
              "independent_relevance_labels_available": 0, "rel1_training_executed": False, "reports": reports}
    Path(output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report,indent=2))
    return report


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True)
    run(parser.parse_args().output)
