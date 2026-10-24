"""Observe the held-out pack through existing PESE pipelines without tuning them.

The engine receives only the query string. Gold answers and evidence remain in this
observer. Reference-key matches are diagnostics, not a substitute for semantic QA
grading, especially for explanations, negation and multi-part comparisons.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "engine/data/knowledge_corpus"


def run(with_qa):
    import torch
    torch.set_num_threads(2)  # Same resident inference thread count as API startup.
    from engine.indexing.store import DocumentStore
    from engine.indexing.inverted_index import InvertedIndex
    from engine.passages.extractor import PassageExtractor
    from engine.link_graph.graph import LinkGraph
    from engine.link_graph.authority import LinkAuthorityCalculator
    from engine.semantic.index import VectorIndex
    from engine.ranking.scorer import RankingEngine

    pack = json.loads((DATA / "queries.json").read_text(encoding="utf-8"))
    baseline = json.loads((DATA / "baseline.json").read_text(encoding="utf-8"))
    protected = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in baseline["protected_files"]}
    store = DocumentStore()
    assert not store.use_firestore, "Benchmark is local-only"
    docs = store.list_documents(status="published")
    index, extractor = InvertedIndex(), PassageExtractor()
    for doc in docs:
        index.index_document(doc, extractor.extract_passages(doc))
    graph = LinkGraph()
    graph.build_from_documents(docs)
    auth = LinkAuthorityCalculator(graph)
    auth.compute_scores()
    vector = VectorIndex()
    assert vector.load_from_disk(), "Run dense corpus indexing first"
    assert {d.id for d in docs} == {m.doc_id for m in vector.doc_meta}, "Dense index is stale"
    engine = RankingEngine(index, auth, vector_index=vector, doc_store=store)
    # Prewarm before measuring queries; no training, threshold edits or substitutions.
    vector.provider.embed_query("warmup")
    reader = engine._get_qa_reader() if with_qa else None
    if with_qa:
        assert reader is not None, "Actual PESE-QA-0 checkpoint could not be loaded"
    rows, summary = [], {}
    started = time.perf_counter()
    for mode in ("lexical_only", "semantic_only", "hybrid"):
        mode_rows = []
        for i, case in enumerate(pack["queries"]):
            begin = time.perf_counter()
            results = engine.search(case["query"], limit=10, retrieval_mode=mode,
                                    skip_qa=not (with_qa and mode == "hybrid"))
            ranking = [result.doc_id for result in results]
            acceptable = set(case["acceptable_documents"])
            relevant_rank = next((rank+1 for rank, key in enumerate(ranking) if key in acceptable), None)
            deterministic = next((r.featured_answer for r in results if r.featured_answer), None)
            trace = getattr(results, "qa_trace", None)
            gold = case["expected_answer"]
            neural = trace.get("shadow_answer") if trace else None
            row = dict(case_id=case["id"], query=case["query"], query_type=case["query_type"],
                       mode=mode, expected_behavior=case["expected_behavior"],
                       ranked_documents=ranking, first_acceptable_rank=relevant_rank,
                       deterministic_answer=deterministic, neural_answer=neural,
                       neural_ran=trace is not None,
                       neural_reference_key_match=bool(gold and neural and gold.casefold() in neural.casefold()),
                       deterministic_reference_key_match=bool(gold and deterministic and gold.casefold() in deterministic.casefold()),
                       qa_trace=trace, elapsed_ms=round((time.perf_counter()-begin)*1000, 2))
            rows.append(row)
            mode_rows.append(row)
            if (i+1) % 40 == 0:
                print(f"{mode}: {i+1}/{len(pack['queries'])}", flush=True)
        positives = [r for r in mode_rows if r["expected_behavior"] == "answer"]
        negatives = [r for r in mode_rows if r["expected_behavior"] == "abstain"]
        summary[mode] = dict(queries=len(mode_rows), positive_queries=len(positives),
                             acceptable_hit_at_1=round(sum(r["first_acceptable_rank"] == 1 for r in positives)/len(positives),4),
                             acceptable_hit_at_5=round(sum(r["first_acceptable_rank"] is not None and r["first_acceptable_rank"] <= 5 for r in positives)/len(positives),4),
                             mrr_at_10=round(sum(1/r["first_acceptable_rank"] if r["first_acceptable_rank"] else 0 for r in positives)/len(positives),4),
                             median_ms=round(statistics.median(r["elapsed_ms"] for r in mode_rows),2),
                             deterministic_answers_on_abstentions=sum(bool(r["deterministic_answer"]) for r in negatives),
                             neural_answers_on_abstentions=sum(bool(r["neural_answer"]) for r in negatives),
                             neural_invocations=sum(r["neural_ran"] for r in mode_rows))
    changed = [name for name, digest in protected.items() if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    report = dict(created_on="2026-10-22", documents=len(docs), passages=len(index.passages),
                  model=vector.provider.get_metadata(), qa_checkpoint_loaded=reader is not None,
                  summary=summary, elapsed_seconds=round(time.perf_counter()-started,2),
                  preexisting_files_changed_during_benchmark=changed,
                  source_hashes=protected, query_pack_sha256=hashlib.sha256((DATA / "queries.json").read_bytes()).hexdigest(),
                  limitations=["Gold is external to the engine and is never used to adjust ranking.",
                               "Hit rates use curated acceptable documents; the list may omit another defensible document.",
                               "QA is recorded from the real shadow reader and deterministic featured-answer path separately.",
                               "Key-phrase containment is not full answer correctness; review context, negation and multi-part answers.",
                               "Unsupported answers on abstention cases are observed failures, not instructions to add rules."],
                  results=rows)
    (DATA / "retrieval_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    assert not changed, f"Other work changed source during benchmark; rerun for a stable snapshot: {changed}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qa", action="store_true", help="Run actual resident PESE-QA-0 in hybrid mode")
    run(parser.parse_args().qa)
