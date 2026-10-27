"""Freeze and compare FIRST CONTACT packets. No fitting, label generation or Brain access.

Protected runs require complete human judgments and answer/abstention review.
--diagnostic uses explicit author proposals and can NEVER count as human evidence.
All output directories are fresh and immutable; runs preserve every query outcome.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate(packet, diagnostic=False):
    if packet.get("format") != "pese-first-contact-evaluation" or packet.get("version") != 1:
        raise ValueError("Unsupported evaluation packet")
    docs = packet["documents"]
    ids = {d["id"] for d in docs}
    if len(ids) != len(docs) or not docs or not packet["questions"]:
        raise ValueError("Unique documents and questions required")
    questions = packet["questions"]
    if len({q["id"] for q in questions}) != len(questions):
        raise ValueError("Duplicate question identity")
    if not diagnostic:
        review = packet.get("human_review") or {}
        if packet.get("role") != "protected_evaluation_never_train" or review.get("approved") is not True:
            raise ValueError("Protected evaluation requires explicit human review")
        reviewer = review.get("reviewer", "").strip()
        if not reviewer or reviewer.casefold() in {"model", "assistant", "neural genesis", "codex", "ai"}:
            raise ValueError("A named human reviewer is required")
        if not review.get("reviewed_at") or review.get("basis") != "human_checked_source_evidence_and_all_labels":
            raise ValueError("Human source and complete-label attestation required")
    for q in questions:
        grades = q.get("proposed_grades") if diagnostic else q.get("grades")
        if not isinstance(grades, dict) or set(grades) != ids or any(type(g) is not int or g not in (0, 1, 2) for g in grades.values()):
            raise ValueError("Every corpus document needs an explicit 0/1/2 judgment; unjudged is not irrelevant")
        if not diagnostic and q.get("answer_reviewed") is not True:
            raise ValueError("Every answer or abstention requires human review")
        if not q.get("group") or not q.get("question"):
            raise ValueError("Question family and wording required")
    # Reject exposure to the base model's known development partitions.
    from engine.intelligence.beta.data import build_splits
    old = build_splits()
    known_questions = {c["question"].casefold() for rows in old.values() for c in rows}
    known_passages = {p["text"] for rows in old.values() for c in rows for p in c["candidates"]}
    if any(q["question"].casefold() in known_questions for q in questions) or any(d["content"] in known_passages for d in docs):
        raise ValueError("Evaluation overlaps exposed model development data")
    return True


def run(packet_path, output, model_path, diagnostic=False):
    packet_path, output, model_path = (Path(os.path.abspath(p)).resolve() for p in (packet_path, output, model_path))
    packet = json.loads(packet_path.read_bytes())
    validate(packet, diagnostic)
    if output.exists() or output == ROOT or output.is_relative_to(ROOT):
        raise ValueError("Fresh output outside checkout required")
    output.mkdir(parents=True)
    # Isolate configuration BEFORE importing any engine module that binds storage.
    (output / "isolated-runtime").mkdir()
    os.environ.update(PESE_BRAIN_PATH=str(output / "isolated-runtime"), PESE_DATA_DIR=str(output / "isolated-runtime"),
                      LOCALAPPDATA=str(output / "profile"), PESE_INTELLIGENCE_CHANNEL="stable",
                      PESE_REL_SHADOW_ENABLED="false", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    if not (model_path / "model_optimized.onnx").is_file():
        raise ValueError("Pinned local BGE model required")
    os.environ["PESE_FASTEMBED_MODEL_PATH"] = str(model_path)
    from engine.intelligence.beta.base_lock import BASE_FILES
    base = ROOT / "engine/neural/assets/basic_english_beta_v1"
    from engine.intelligence.beta.artifacts import bundle
    artifact = bundle(base, base_pin=BASE_FILES)
    frozen = {"version": 1, "packet_sha256": digest(packet), "model_files": BASE_FILES,
              "ranking_source_sha256": hashlib.sha256((ROOT / "engine/ranking/scorer.py").read_bytes()).hexdigest(),
              "diagnostic_only": diagnostic, "human_reviewed": not diagnostic,
              "frozen_at": datetime.now(timezone.utc).isoformat(), "retuning_permitted": False,
              "comparison": "same_corpus_hybrid_MAAE_vs_bounded_Neural_Genesis",
              "preregistered": {"min_reviewed_families_for_quality_claim": 12, "ndcg_gain": 0.01,
                                "new_wrong_answers": 0, "membership_violations": 0,
                                "latency": "report_cold_and_p50_p95_of_three_uncached_warm_pairs"}}
    (output / "frozen.json").write_text(json.dumps(frozen, indent=2), encoding="utf-8")
    (output / "packet.json").write_text(json.dumps(packet, indent=2), encoding="utf-8")
    from engine.evaluation.phase2f_support import build_engine, document
    from engine.search_sync.feedback_store import SearchSyncFeedbackStore
    from engine.search_sync.preference_signal import SearchSyncPreferenceSignal
    from engine.intelligence.reranking import NeuralReranker
    from engine.intelligence.beta.processes import ResidentInference
    from engine.intelligence.evaluation import ranking_metrics, paired_report
    import torch
    torch.set_num_threads(2)
    docs = [document(d["id"], d["title"], d["content"], created_at="2026-10-01T00:00:00Z", updated_at="2026-10-01T00:00:00Z") for d in packet["documents"]]
    engine = build_engine(docs, output, semantic=True)
    print("Built isolated 24-document hybrid diagnostic" if diagnostic else "Built isolated protected corpus", flush=True)
    engine.search_sync = SearchSyncPreferenceSignal(SearchSyncFeedbackStore(":memory:"))
    worker = ResidentInference()
    engine.neural_ranker = NeuralReranker(artifact, predictor=worker)
    mode = False
    engine._neural_search_enabled = lambda: mode
    records = []
    try:
        for q in packet["questions"]:
            print("Evaluating " + q["id"], flush=True)
            grades = q["proposed_grades"] if diagnostic else q["grades"]
            runs = {False: [], True: []}
            results = {}
            traces = []
            for repeat in range(3):
                for mode in ((False, True) if repeat % 2 == 0 else (True, False)):
                    engine.invalidate_query_cache()
                    start = time.perf_counter()
                    result = engine.search(q["question"], skip_qa=True)
                    runs[mode].append((time.perf_counter() - start) * 1000)
                    results[mode] = result
                    if mode:
                        traces.append(result.hybrid_trace.get("neural_ranking"))
            baseline, neural = results[False], results[True]
            b, n = ([r.doc_id for r in result] for result in (baseline, neural))
            answers = {key: next((r.featured_answer for r in result if r.is_featured and r.featured_answer), None)
                       for key, result in (("maae", baseline), ("neural", neural))}
            expected = q.get("proposed_expected_answer") if diagnostic else q.get("expected_answer")
            def answer_proxy(answer):
                return answer is None if expected is None else bool(answer and expected.casefold() in answer.casefold())
            bm, nm = ranking_metrics(b, grades), ranking_metrics(n, grades)
            records.append({"id": q["id"], "question": q["question"], "group": q["group"], "category": q["category"],
                            "baseline": b, "candidate": n, "judgments": grades,
                            "delta_ndcg10": nm["ndcg10"] - bm["ndcg10"], "answers": answers,
                            "metrics": {"maae": bm, "neural": nm},
                            "answer_proxy_pass": {k: answer_proxy(v) for k, v in answers.items()},
                            "unanswered": {k: v is None for k, v in answers.items()},
                            "membership_violations": sorted(set(n) ^ set(b)),
                            "latency_ms": {"maae": runs[False], "neural": runs[True]}, "neural_traces": traces})
    finally:
        worker.close()
    paired = paired_report(records)
    paired.pop("rows")
    def latency(key):
        values = sorted(v for r in records for v in r["latency_ms"][key][1:])
        return {"first_query_first_ms": records[0]["latency_ms"][key][0], "warm_p50_ms": statistics.median(values),
                "warm_p95_ms": values[min(len(values) - 1, int(.95 * len(values)))]}
    result = {"version": 1, "status": "unreviewed_diagnostic_no_quality_claim" if diagnostic else "human_reviewed_protected_run_no_retuning",
              "independent_human_review": not diagnostic, "training_performed": False, "owner_brain_accessed": False,
              "frozen": frozen, "paired": paired, "improvements": sum(r["delta_ndcg10"] > 1e-9 for r in records),
              "regressions": sum(r["delta_ndcg10"] < -1e-9 for r in records), "order_changes": sum(r["baseline"] != r["candidate"] for r in records),
              "membership_violations": sum(bool(r["membership_violations"]) for r in records),
              "model_attempts_applied": sum(t is not None and t.get("authority") == "BOUNDED_RANKING_ONLY" for r in records for t in r["neural_traces"]),
              "model_attempts_fallback": sum(t is not None and "FALLBACK" in t.get("status", "") for r in records for t in r["neural_traces"]),
              "unanswered": {k: sum(r["unanswered"][k] for r in records) for k in ("maae", "neural")},
              "answer_assessment": "literal_expected_extract_proxy_requires_blind_human_output_review",
              "latency": {k: latency(k) for k in ("maae", "neural")}, "records": records,
              "mean_metrics": {k: {m: statistics.mean(r["metrics"][k][m] for r in records)
                                    for m in ("ndcg10", "mrr", "recall")} for k in ("maae", "neural")},
              "promotion_authority": "NONE", "protected_set_must_be_replaced_if_used_to_change_the_model_or_ranker": True}
    (output / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in {"records", "frozen"}}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("output")
    evaluate = sub.add_parser("run")
    evaluate.add_argument("packet")
    evaluate.add_argument("output")
    evaluate.add_argument("--model-path", required=True)
    evaluate.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare":
        from research.first_contact_english import draft
        with Path(args.output).open("x", encoding="utf-8") as stream:
            json.dump(draft(), stream, indent=2)
    else:
        run(args.packet, args.output, args.model_path, args.diagnostic)
