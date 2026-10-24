"""
PESE Evaluation: Adversarial Benchmark Runner
Executes independent adversarial regression suite measuring resilience across:
Clean Queries, Typo Queries, Intent Queries, Weak Evidence Queries, Featured Answer Queries, and No-Result Queries.
"""

import json
from pathlib import Path
from typing import Dict, Any, List

from ..indexing.store import DocumentStore
from ..indexing.inverted_index import InvertedIndex
from ..passages.extractor import PassageExtractor
from ..link_graph.graph import LinkGraph
from ..link_graph.authority import LinkAuthorityCalculator
from ..ranking.scorer import RankingEngine
from .adversarial_queries import ADVERSARIAL_DATASET
from .metrics import reciprocal_rank, precision_at_k, hit_at_k


def run_adversarial_evaluation(
    engine: RankingEngine = None,
    dataset: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute adversarial benchmark suite and return structured category summary."""
    if engine is None:
        store = DocumentStore()
        docs = store.list_documents(status="published")
        index = InvertedIndex()
        extractor = PassageExtractor()
        for d in docs:
            passages = extractor.extract_passages(d)
            index.index_document(d, passages)

        graph = LinkGraph()
        graph.build_from_documents(docs)
        link_auth = LinkAuthorityCalculator(graph)
        link_auth.compute_scores()

        engine = RankingEngine(index, link_auth)

    dataset = dataset or ADVERSARIAL_DATASET
    total_queries = len(dataset)

    # Metric accumulators
    intent_correct = 0
    top1_correct = 0
    top3_hit = 0
    no_result_correct = 0
    no_result_total = 0

    expected_corrections_total = 0
    correct_corrections_count = 0
    false_corrections_count = 0

    answer_expected_count = 0
    answer_correct_count = 0

    category_stats: Dict[str, Dict[str, Any]] = {}
    detailed_results = []

    for item in dataset:
        query = item["query"]
        category = item["category"]
        expected_intent = item["expected_intent"]
        expected_corrections = item.get("expected_corrections", [])
        expected_top = item.get("expected_top_slug")
        relevant = item.get("relevant_slugs", [])
        expected_no_result = item.get("expected_no_result", False)
        expected_answer = item.get("expected_answer_contains")

        search_results = engine.search(query, limit=5)
        ranked_slugs = [r.slug for r in search_results]
        qa = getattr(search_results, "query_analysis", None)

        # 1. Intent Accuracy
        actual_intent = qa.intent.value if qa else "GENERAL"
        intent_match = actual_intent == expected_intent
        if intent_match:
            intent_correct += 1

        # 2. Correction Accuracy
        actual_corrections = [(c.original_token, c.corrected_token) for c in qa.corrections] if qa else []
        for orig, corr in expected_corrections:
            expected_corrections_total += 1
            if (orig, corr) in actual_corrections:
                correct_corrections_count += 1

        # Check for false corrections (corrections applied that were not expected)
        for act_orig, act_corr in actual_corrections:
            if (act_orig, act_corr) not in expected_corrections:
                false_corrections_count += 1

        # 3. No-Result Handling
        is_empty = len(search_results) == 0
        if expected_no_result:
            no_result_total += 1
            if is_empty:
                no_result_correct += 1

        # 4. Top 1 & Top 3
        hit1 = False
        hit3 = False
        if not expected_no_result:
            hit1 = bool(ranked_slugs and (ranked_slugs[0] == expected_top or ranked_slugs[0] in relevant))
            hit3 = hit_at_k(ranked_slugs, relevant, 3)
            if hit1:
                top1_correct += 1
            if hit3:
                top3_hit += 1

        # 5. Answer Extraction Accuracy
        answer_hit = None
        if expected_answer:
            answer_expected_count += 1
            top_answer = search_results[0].featured_answer if search_results else None
            top_snippet = search_results[0].snippet_text if search_results else ""
            if top_answer and expected_answer.lower() in top_answer.lower():
                answer_correct_count += 1
                answer_hit = True
            elif top_snippet and expected_answer.lower() in top_snippet.lower():
                answer_correct_count += 1
                answer_hit = True
            else:
                answer_hit = False

        # Category rollup
        if category not in category_stats:
            category_stats[category] = {"total": 0, "passed": 0}
        category_stats[category]["total"] += 1
        is_passed = (is_empty if expected_no_result else hit1)
        if is_passed:
            category_stats[category]["passed"] += 1

        detailed_results.append({
            "query": query,
            "category": category,
            "intent": actual_intent,
            "intent_match": intent_match,
            "corrections": actual_corrections,
            "top_result": ranked_slugs[0] if ranked_slugs else None,
            "hit_at_1": hit1,
            "hit_at_3": hit3,
            "no_result_correct": is_empty == expected_no_result,
            "featured_answer": search_results[0].featured_answer if search_results else None,
            "answer_hit": answer_hit,
        })

    # Summary metrics
    applicable_ranking_queries = total_queries - no_result_total
    summary = {
        "total_queries": total_queries,
        "intent_accuracy": round(intent_correct / total_queries, 4),
        "top1_accuracy": round(top1_correct / applicable_ranking_queries, 4) if applicable_ranking_queries else 1.0,
        "top3_hit_rate": round(top3_hit / applicable_ranking_queries, 4) if applicable_ranking_queries else 1.0,
        "correction_accuracy": round(correct_corrections_count / expected_corrections_total, 4) if expected_corrections_total else 1.0,
        "false_corrections_count": false_corrections_count,
        "no_result_precision": round(no_result_correct / no_result_total, 4) if no_result_total else 1.0,
        "featured_answer_accuracy": round(answer_correct_count / answer_expected_count, 4) if answer_expected_count else 1.0,
        "category_summary": {
            cat: f"{stat['passed']}/{stat['total']} ({round((stat['passed']/stat['total'])*100, 1)}%)"
            for cat, stat in category_stats.items()
        },
        "detailed_results": detailed_results,
    }

    # Save report
    report_path = Path(__file__).resolve().parent.parent / "data" / "adversarial_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


def print_adversarial_summary(summary: Dict[str, Any]) -> None:
    """Print readable benchmark results to console."""
    print("=" * 65)
    print(" [PESE PHASE 1.5 ADVERSARIAL BENCHMARK REPORT] ")
    print("=" * 65)
    print(f"Total Adversarial Queries:        {summary['total_queries']}")
    print(f"Intent Classification Accuracy:   {summary['intent_accuracy'] * 100:.1f}%")
    print(f"Top-1 Accuracy (Ranking queries): {summary['top1_accuracy'] * 100:.1f}%")
    print(f"Top-3 Hit Rate:                   {summary['top3_hit_rate'] * 100:.1f}%")
    print(f"Typo Correction Accuracy:         {summary['correction_accuracy'] * 100:.1f}%")
    print(f"False Corrections Count:          {summary['false_corrections_count']} (Target: 0)")
    print(f"No-Result Gate Precision:         {summary['no_result_precision'] * 100:.1f}% (Zero random leaks)")
    print(f"Featured Answer Accuracy:         {summary['featured_answer_accuracy'] * 100:.1f}%")
    print("-" * 65)
    print("Category Breakdown:")
    for cat, text in summary["category_summary"].items():
        print(f"  * {cat.ljust(26)}: {text}")
    print("=" * 65)


if __name__ == "__main__":
    summary = run_adversarial_evaluation()
    print_adversarial_summary(summary)
