"""
PESE Evaluation: Runner
Executes benchmark suite against the search engine and reports scientific IR metrics.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List

from ..indexing.store import DocumentStore
from ..indexing.inverted_index import InvertedIndex
from ..passages.extractor import PassageExtractor
from ..link_graph.graph import LinkGraph
from ..link_graph.authority import LinkAuthorityCalculator
from ..ranking.scorer import RankingEngine
from .dataset import EVALUATION_DATASET
from .metrics import (
    reciprocal_rank,
    precision_at_k,
    recall_at_k,
    hit_at_k,
    passage_match_hit,
)


def run_evaluation(
    engine: RankingEngine = None,
    dataset: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute evaluation benchmark and return structured summary."""
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

    dataset = dataset or EVALUATION_DATASET
    total_queries = len(dataset)

    rr_scores = []
    p1_scores = []
    p3_scores = []
    r3_scores = []
    hit1_counts = 0
    hit3_counts = 0
    hit5_counts = 0

    passage_queries_count = 0
    passage_hits_count = 0

    detailed_results = []
    spam_violations = 0

    for item in dataset:
        query = item["query"]
        relevant = item["relevant_slugs"]
        irrelevant = item.get("irrelevant_slugs", [])
        expected_passage = item.get("expected_passage_contains")

        search_results = engine.search(query, limit=10)
        ranked_slugs = [r.slug for r in search_results]

        rr = reciprocal_rank(ranked_slugs, relevant)
        p1 = precision_at_k(ranked_slugs, relevant, 1)
        p3 = precision_at_k(ranked_slugs, relevant, 3)
        r3 = recall_at_k(ranked_slugs, relevant, 3)
        h1 = hit_at_k(ranked_slugs, relevant, 1)
        h3 = hit_at_k(ranked_slugs, relevant, 3)
        h5 = hit_at_k(ranked_slugs, relevant, 5)

        rr_scores.append(rr)
        p1_scores.append(p1)
        p3_scores.append(p3)
        r3_scores.append(r3)

        if h1:
            hit1_counts += 1
        if h3:
            hit3_counts += 1
        if h5:
            hit5_counts += 1

        # Check passage match on top result
        passage_hit = None
        if expected_passage and search_results:
            passage_queries_count += 1
            top_snippet = search_results[0].snippet_text
            passage_hit = passage_match_hit(top_snippet, expected_passage)
            if passage_hit:
                passage_hits_count += 1

        # Check if spam document erroneously won #1
        if ranked_slugs and ranked_slugs[0] == "best-bicycle-deals-cheap-bicycle":
            spam_violations += 1

        detailed_results.append({
            "query": query,
            "cluster": item.get("cluster", ""),
            "top_result": ranked_slugs[0] if ranked_slugs else None,
            "top_score": search_results[0].final_score if search_results else 0.0,
            "reciprocal_rank": round(rr, 4),
            "precision_at_1": round(p1, 4),
            "precision_at_3": round(p3, 4),
            "recall_at_3": round(r3, 4),
            "hit_at_1": h1,
            "hit_at_3": h3,
            "hit_at_5": h5,
            "passage_hit": passage_hit,
        })

    mrr = sum(rr_scores) / total_queries if total_queries else 0.0
    mean_p1 = sum(p1_scores) / total_queries if total_queries else 0.0
    mean_p3 = sum(p3_scores) / total_queries if total_queries else 0.0
    mean_r3 = sum(r3_scores) / total_queries if total_queries else 0.0

    hit1_rate = hit1_counts / total_queries if total_queries else 0.0
    hit3_rate = hit3_counts / total_queries if total_queries else 0.0
    hit5_rate = hit5_counts / total_queries if total_queries else 0.0

    passage_accuracy = (passage_hits_count / passage_queries_count) if passage_queries_count else 0.0

    summary = {
        "total_queries": total_queries,
        "mrr": round(mrr, 4),
        "mean_precision_at_1": round(mean_p1, 4),
        "mean_precision_at_3": round(mean_p3, 4),
        "mean_recall_at_3": round(mean_r3, 4),
        "hit_at_1_rate": round(hit1_rate, 4),
        "hit_at_3_rate": round(hit3_rate, 4),
        "hit_at_5_rate": round(hit5_rate, 4),
        "passage_extraction_accuracy": round(passage_accuracy, 4),
        "passage_evaluated_queries": passage_queries_count,
        "spam_violations": spam_violations,
        "detailed_results": detailed_results,
    }

    # Save to disk
    report_path = Path(__file__).resolve().parent.parent / "data" / "evaluation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


def print_evaluation_summary(summary: Dict[str, Any]) -> None:
    """Print readable benchmark results to console."""
    print("=" * 65)
    print(" [PESE SEARCH ENGINE BENCHMARK REPORT]")
    print("=" * 65)
    print(f"Total Test Queries Evaluated:    {summary['total_queries']}")
    print(f"Mean Reciprocal Rank (MRR):      {summary['mrr']:.4f}")
    print(f"Mean Precision@1:                {summary['mean_precision_at_1']:.4f}")
    print(f"Mean Precision@3:                {summary['mean_precision_at_3']:.4f}")
    print(f"Mean Recall@3:                   {summary['mean_recall_at_3']:.4f}")
    print(f"Hit Rate @ 1:                    {summary['hit_at_1_rate'] * 100:.1f}%")
    print(f"Hit Rate @ 3:                    {summary['hit_at_3_rate'] * 100:.1f}%")
    print(f"Hit Rate @ 5:                    {summary['hit_at_5_rate'] * 100:.1f}%")
    print(f"Passage Extraction Accuracy:     {summary['passage_extraction_accuracy'] * 100:.1f}% ({summary['passage_evaluated_queries']} queries with passage assertions)")
    print(f"Spam Violations (Spam ranked #1): {summary['spam_violations']}")
    print("=" * 65)


if __name__ == "__main__":
    summary = run_evaluation()
    print_evaluation_summary(summary)
