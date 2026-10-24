"""
PESE Semantic: Evaluation Benchmark Runner (Phase 2B)
Executes ablation benchmarks comparing Lexical-only (BM25F), Semantic-only (Dense),
and Hybrid (PESE Phase 2B) retrieval pipelines. Computes MRR@10, Top-1 accuracy,
Paraphrase Recovery Rate, and Drift Resistance Rate.
"""

import time
import json
from pathlib import Path
from typing import Dict, Any, List

from .semantic_dataset import SEMANTIC_BENCHMARK_CASES
from ..indexing.store import DocumentStore
from ..indexing.inverted_index import InvertedIndex
from ..passages.extractor import PassageExtractor
from ..link_graph.graph import LinkGraph
from ..link_graph.authority import LinkAuthorityCalculator
from ..ranking.scorer import RankingEngine
from ..semantic.index import VectorIndex

REPORT_PATH = Path(__file__).resolve().parent.parent / "data" / "semantic_report.json"


def evaluate_mode(
    engine: RankingEngine,
    mode: str,
    test_cases: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Execute evaluation for a specific retrieval mode (hybrid, lexical_only, semantic_only)."""
    detailed_results = []
    reciprocal_ranks = []
    top_1_hits = 0
    paraphrase_hits = 0
    total_paraphrases = 0
    drift_resisted = 0
    total_drift_cases = 0
    total_latency_ms = 0.0

    for case in test_cases:
        query = case["query"]
        target = case.get("target_slug")
        incomp = case.get("incompatible_slug")
        cat = case["category"]

        start = time.perf_counter()
        results = engine.search(query, limit=10, retrieval_mode=mode)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        total_latency_ms += elapsed_ms

        top_result = results[0] if results else None
        top_slug = top_result.slug if top_result else None
        top_score = top_result.final_score if top_result else 0.0

        # Calculate reciprocal rank for target
        target_rank = None
        rr = 0.0
        if target:
            for rank_idx, r in enumerate(results, start=1):
                if r.slug == target:
                    target_rank = rank_idx
                    rr = 1.0 / rank_idx
                    break
            reciprocal_ranks.append(rr)
            if target_rank == 1:
                top_1_hits += 1

        # Check paraphrase recovery (in Top 3)
        if cat == "paraphrase_rescue":
            total_paraphrases += 1
            if target_rank is not None and target_rank <= 3:
                paraphrase_hits += 1

        # Check drift resistance
        if cat == "drift_protection":
            total_drift_cases += 1
            # Pass if no results OR if top result is NOT the incompatible domain slug
            if not results:
                drift_resisted += 1
            elif incomp and not any(r.slug == incomp for r in results[:3]):
                drift_resisted += 1

        is_rescue = getattr(top_result, "is_semantic_rescue", False) if top_result else False
        sem_sim = getattr(top_result, "semantic_similarity", 0.0) if top_result else 0.0

        detailed_results.append({
            "id": case["id"],
            "category": cat,
            "query": query,
            "target": target,
            "top_slug": top_slug,
            "top_score": round(top_score, 4),
            "target_rank": target_rank,
            "reciprocal_rank": round(rr, 4),
            "is_semantic_rescue": is_rescue,
            "semantic_similarity": round(sem_sim, 4),
            "latency_ms": round(elapsed_ms, 2),
        })

    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0
    queries_with_targets = [c for c in test_cases if c.get("target_slug")]
    top_1_rate = top_1_hits / len(queries_with_targets) if queries_with_targets else 0.0
    para_rate = paraphrase_hits / total_paraphrases if total_paraphrases else 0.0
    drift_rate = drift_resisted / total_drift_cases if total_drift_cases else 0.0
    avg_latency = total_latency_ms / len(test_cases) if test_cases else 0.0

    return {
        "mode": mode,
        "mrr_at_10": round(mrr, 4),
        "top_1_accuracy": round(top_1_rate * 100, 2),
        "paraphrase_recovery_rate": round(para_rate * 100, 2),
        "drift_resistance_rate": round(drift_rate * 100, 2),
        "avg_latency_ms": round(avg_latency, 2),
        "total_queries_evaluated": len(test_cases),
        "detailed_results": detailed_results,
    }


def run_semantic_evaluation() -> Dict[str, Any]:
    """Orchestrates end-to-end Phase 2B semantic retrieval ablation evaluation."""
    # 1. Initialize store & build pipeline
    store = DocumentStore()
    docs = store.list_documents(status="published")
    if not docs:
        from ..data.seed_corpus import seed_corpus
        docs = seed_corpus(store)

    extractor = PassageExtractor()
    index = InvertedIndex()
    passages_by_doc = {}
    for doc in docs:
        passages = extractor.extract_passages(doc)
        passages_by_doc[doc.id] = passages
        index.index_document(doc, passages)

    vec_index = VectorIndex()
    vec_index.build_index(docs, passages_by_doc)

    graph = LinkGraph()
    graph.build_from_documents(docs)
    auth = LinkAuthorityCalculator(graph)
    auth.compute_scores()

    engine = RankingEngine(index, auth, vector_index=vec_index, doc_store=store)

    # 2. Run ablations: Lexical Only, Semantic Only, Hybrid
    print("\n=======================================================")
    print("  PESE PHASE 2B: SEMANTIC RETRIEVAL EVALUATION SUITE  ")
    print("=======================================================")

    lexical_report = evaluate_mode(engine, "lexical_only", SEMANTIC_BENCHMARK_CASES)
    semantic_report = evaluate_mode(engine, "semantic_only", SEMANTIC_BENCHMARK_CASES)
    hybrid_report = evaluate_mode(engine, "hybrid", SEMANTIC_BENCHMARK_CASES)

    # 3. Compile comparative report
    final_report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_test_cases": len(SEMANTIC_BENCHMARK_CASES),
        "corpus_documents": len(docs),
        "corpus_passages": len(index.passages),
        "vector_index_diagnostics": vec_index.get_diagnostics().model_dump(),
        "ablation_summary": {
            "lexical_only": {
                "top_1_accuracy": lexical_report["top_1_accuracy"],
                "mrr_at_10": lexical_report["mrr_at_10"],
                "paraphrase_recovery_rate": lexical_report["paraphrase_recovery_rate"],
                "drift_resistance_rate": lexical_report["drift_resistance_rate"],
                "avg_latency_ms": lexical_report["avg_latency_ms"],
            },
            "semantic_only": {
                "top_1_accuracy": semantic_report["top_1_accuracy"],
                "mrr_at_10": semantic_report["mrr_at_10"],
                "paraphrase_recovery_rate": semantic_report["paraphrase_recovery_rate"],
                "drift_resistance_rate": semantic_report["drift_resistance_rate"],
                "avg_latency_ms": semantic_report["avg_latency_ms"],
            },
            "hybrid_peseb2": {
                "top_1_accuracy": hybrid_report["top_1_accuracy"],
                "mrr_at_10": hybrid_report["mrr_at_10"],
                "paraphrase_recovery_rate": hybrid_report["paraphrase_recovery_rate"],
                "drift_resistance_rate": hybrid_report["drift_resistance_rate"],
                "avg_latency_ms": hybrid_report["avg_latency_ms"],
            },
            "hybrid_vs_lexical_paraphrase_delta": f"+{hybrid_report['paraphrase_recovery_rate'] - lexical_report['paraphrase_recovery_rate']:.1f}%",
            "hybrid_vs_semantic_drift_delta": f"+{hybrid_report['drift_resistance_rate'] - semantic_report['drift_resistance_rate']:.1f}%",
        },
        "detailed_runs": {
            "lexical_only": lexical_report["detailed_results"],
            "semantic_only": semantic_report["detailed_results"],
            "hybrid": hybrid_report["detailed_results"],
        },
    }

    # Save to disk
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2)

    # CLI Output
    print(f"\nComparative Retrieval Ablations ({len(SEMANTIC_BENCHMARK_CASES)} queries):")
    print(f"{'Metric':<30} | {'Lexical (BM25F)':<16} | {'Semantic (Dense)':<16} | {'Hybrid (PESE 2B)':<16}")
    print("-" * 86)
    print(f"{'Top-1 Accuracy':<30} | {lexical_report['top_1_accuracy']:>15.1f}% | {semantic_report['top_1_accuracy']:>15.1f}% | {hybrid_report['top_1_accuracy']:>15.1f}%")
    print(f"{'Mean Reciprocal Rank (MRR@10)':<30} | {lexical_report['mrr_at_10']:>16.4f} | {semantic_report['mrr_at_10']:>16.4f} | {hybrid_report['mrr_at_10']:>16.4f}")
    print(f"{'Paraphrase Recovery Rate':<30} | {lexical_report['paraphrase_recovery_rate']:>15.1f}% | {semantic_report['paraphrase_recovery_rate']:>15.1f}% | {hybrid_report['paraphrase_recovery_rate']:>15.1f}%")
    print(f"{'Drift Resistance Rate':<30} | {lexical_report['drift_resistance_rate']:>15.1f}% | {semantic_report['drift_resistance_rate']:>15.1f}% | {hybrid_report['drift_resistance_rate']:>15.1f}%")
    print(f"{'Average Latency':<30} | {lexical_report['avg_latency_ms']:>14.2f}ms | {semantic_report['avg_latency_ms']:>14.2f}ms | {hybrid_report['avg_latency_ms']:>14.2f}ms")
    print("-" * 86)
    print(f"Paraphrase Recovery Gain: {final_report['ablation_summary']['hybrid_vs_lexical_paraphrase_delta']}")
    print(f"Report written to: {REPORT_PATH}\n")

    return final_report


if __name__ == "__main__":
    run_semantic_evaluation()
