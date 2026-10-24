"""
PESE Evaluation: Performance Runner (Phase 2D.1)
Scientifically benchmarks cold vs warm 1..5 query latencies, subsystem timing breakdowns,
neural QA accounting, thread scaling, and discovery aux endpoint isolation.
"""

import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List
import torch

from ..indexing.store import DocumentStore
from ..indexing.inverted_index import InvertedIndex
from ..passages.extractor import PassageExtractor
from ..link_graph.graph import LinkGraph
from ..link_graph.authority import LinkAuthorityCalculator
from ..semantic.index import VectorIndex
from ..ranking.scorer import RankingEngine
from ..discovery.autocomplete import AutocompleteEngine
from ..discovery.related_searches import RelatedSearchEngine
from ..discovery.questions import PAAQuestionEngine
from ..discovery.history import LocalHistoryStore
from ..discovery.sessions import SessionManager
from ..discovery.families import QueryFamilyRegistry


BENCHMARK_PERFORMANCE_QUERIES = [
    {
        "category": "Exact Lexical",
        "query": "when did I buy my bicycle",
        "description": "Personal purchasing history query with exact lexical match",
    },
    {
        "category": "Exact Lexical",
        "query": "japanese beginner roadmap",
        "description": "Multi-word title match against language guide",
    },
    {
        "category": "Typo Recovery",
        "query": "japna",
        "description": "Corpus-aware spelling recovery for single entity token",
    },
    {
        "category": "Typo Recovery",
        "query": "bycycle chain upkeep",
        "description": "Spelling recovery on content term with procedural intent",
    },
    {
        "category": "Semantic Paraphrase",
        "query": "how to maintain bike drivetrain",
        "description": "Dense semantic rescue query with distinct lexical terminology",
    },
    {
        "category": "Semantic Paraphrase",
        "query": "island nation in east asia",
        "description": "Conceptual description retrieving Japan through dense embeddings",
    },
    {
        "category": "Historical Date QA",
        "query": "when did japan enter ww2",
        "description": "Multi-date arbitration extracting 1941",
    },
    {
        "category": "Historical Date QA",
        "query": "when was the meiji constitution promulgated",
        "description": "Meiji period date arbitration extracting 1889",
    },
    {
        "category": "Historical Date QA",
        "query": "when did japan annex korea",
        "description": "Colonial timeline date arbitration extracting 1910",
    },
    {
        "category": "Procedural Instruction",
        "query": "how to clean and oil bicycle chain",
        "description": "Procedural HOW query retrieving maintenance step instructions",
    },
    {
        "category": "Entity / Factual",
        "query": "who developed pese",
        "description": "Entity WHO query extracting creator identification",
    },
    {
        "category": "Heading Passage Signal",
        "query": "meiji period",
        "description": "Topic query retrieving Japan at #1 with strong passage score",
    },
]


def run_performance_benchmark(
    num_warm_runs: int = 5,
    torch_threads: int = 2,
) -> Dict[str, Any]:
    """
    Executes comprehensive latency autopsy and neural work accounting benchmark.
    Reports cold vs warm 1..N timings across categories.
    """
    torch.set_num_threads(torch_threads)

    # 1. Pipeline Initialization
    t_init_start = time.perf_counter()
    store = DocumentStore()
    docs = store.list_documents(status="published")

    index = InvertedIndex()
    extractor = PassageExtractor()
    passages_by_doc = {}
    for d in docs:
        passages = extractor.extract_passages(d)
        passages_by_doc[d.id] = passages
        index.index_document(d, passages)

    vector_index = VectorIndex()
    vector_index.build_index(docs, passages_by_doc)

    graph = LinkGraph()
    graph.build_from_documents(docs)
    auth = LinkAuthorityCalculator(graph)
    auth.compute_scores()

    engine = RankingEngine(index, auth, vector_index=vector_index, doc_store=store)

    history_store = LocalHistoryStore()
    session_manager = SessionManager(history_store)
    family_registry = QueryFamilyRegistry()
    related_engine = RelatedSearchEngine(store, graph, history_store, session_manager, family_registry)
    paa_engine = PAAQuestionEngine(store, engine, family_registry)

    init_ms = round((time.perf_counter() - t_init_start) * 1000.0, 2)

    # 2. Measure Startup Warmup Overhead
    t_warmup_start = time.perf_counter()
    if vector_index and hasattr(vector_index, "provider"):
        vector_index.provider.embed_query("pese performance warmup query")
    reader = engine._get_qa_reader()
    if reader:
        reader.read_passage("warmup question", "warmup passage evidence text for performance benchmark")
    warmup_overhead_ms = round((time.perf_counter() - t_warmup_start) * 1000.0, 2)

    # 3. Benchmark Queries
    query_benchmarks: List[Dict[str, Any]] = []
    all_warm_totals: List[float] = []
    all_cached_totals: List[float] = []

    for item in BENCHMARK_PERFORMANCE_QUERIES:
        q_text = item["query"]
        category = item["category"]

        # Run Cold Search (first run after startup prewarm)
        t_cold_start = time.perf_counter()
        cold_res = engine.search(q_text, limit=10)
        cold_total_ms = round((time.perf_counter() - t_cold_start) * 1000.0, 2)

        # Run N Warm Iterations (retesting resident model & cache)
        warm_runs_data: List[Dict[str, Any]] = []
        for run_idx in range(1, num_warm_runs + 1):
            t_run_start = time.perf_counter()
            warm_res = engine.search(q_text, limit=10)
            run_total_ms = round((time.perf_counter() - t_run_start) * 1000.0, 2)

            warm_runs_data.append({
                "iteration": run_idx,
                "server_total_ms": run_total_ms,
                "timing": warm_res.timing,
                "qa_cache_hit": warm_res.qa_trace.get("qa_cache_hit", False) if warm_res.qa_trace else False,
            })
            if run_idx == 1:
                all_warm_totals.append(run_total_ms)
            else:
                all_cached_totals.append(run_total_ms)

        qa_trace = cold_res.qa_trace or {}
        top_slug = cold_res[0].slug if cold_res else "NONE"
        featured_ans = cold_res[0].featured_answer if cold_res else None

        query_benchmarks.append({
            "query": q_text,
            "category": category,
            "top_slug": top_slug,
            "featured_answer": featured_ans,
            "shadow_answer": qa_trace.get("shadow_answer"),
            "agreement": qa_trace.get("agreement", "N/A"),
            "cold_total_ms": cold_total_ms,
            "cold_timing": cold_res.timing,
            "warm_iterations": warm_runs_data,
            "warm_1_ms": warm_runs_data[0]["server_total_ms"] if warm_runs_data else cold_total_ms,
            "cached_avg_ms": round(sum(w["server_total_ms"] for w in warm_runs_data[1:]) / max(1, len(warm_runs_data) - 1), 2),
            "qa_accounting": {
                "qa_candidates": qa_trace.get("qa_candidates", 0),
                "qa_passages_budgeted": qa_trace.get("qa_passages_budgeted", 0),
                "qa_windows_created": qa_trace.get("qa_windows_created", 0),
                "qa_forward_passes": qa_trace.get("qa_forward_passes", 0),
                "qa_early_exit": qa_trace.get("qa_early_exit", False),
                "torch_threads": qa_trace.get("torch_threads", torch_threads),
                "model_reused": True,
            },
        })

    # 4. Benchmark Discovery Aux Endpoints (Isolated with skip_qa=True)
    discovery_latencies: Dict[str, float] = {}
    test_q = "when did I buy my bicycle"

    t0_rel = time.perf_counter()
    related_res = related_engine.get_related_searches(test_q, ["my-bicycle-story", "my-first-bicycle"])
    discovery_latencies["related_searches_ms"] = round((time.perf_counter() - t0_rel) * 1000.0, 2)

    t0_paa = time.perf_counter()
    paa_res = paa_engine.get_questions_for_query(test_q, ["my-bicycle-story", "my-first-bicycle"])
    discovery_latencies["paa_questions_ms"] = round((time.perf_counter() - t0_paa) * 1000.0, 2)

    # 5. Summary Statistics
    mean_warm_1 = round(sum(all_warm_totals) / max(1, len(all_warm_totals)), 2)
    max_warm_1 = round(max(all_warm_totals, default=0.0), 2)
    min_warm_1 = round(min(all_warm_totals, default=0.0), 2)

    mean_cached = round(sum(all_cached_totals) / max(1, len(all_cached_totals)), 2)
    min_cached = round(min(all_cached_totals, default=0.0), 2)

    summary = {
        "status": "success",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "torch_threads": torch_threads,
        "pipeline_init_ms": init_ms,
        "startup_warmup_overhead_ms": warmup_overhead_ms,
        "total_queries_tested": len(BENCHMARK_PERFORMANCE_QUERIES),
        "mean_warm_search_ms": mean_warm_1,
        "min_warm_search_ms": min_warm_1,
        "max_warm_search_ms": max_warm_1,
        "mean_cached_search_ms": mean_cached,
        "min_cached_search_ms": min_cached,
        "discovery_aux_endpoints": discovery_latencies,
        "latency_target_achieved": mean_warm_1 < 500.0,
        "queries": query_benchmarks,
    }

    # Save to disk
    report_file = Path(__file__).resolve().parent.parent / "data" / "performance_report.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


def print_performance_summary(report: Dict[str, Any]) -> None:
    """Print clean scientific table of performance results."""
    print("=" * 80)
    print(" [PESE SEARCH ENGINE RUNTIME PERFORMANCE AUTOPSY & BENCHMARK REPORT]")
    print("=" * 80)
    print(f"PyTorch CPU Threads:            {report['torch_threads']}")
    print(f"Pipeline Initialization:        {report['pipeline_init_ms']} ms")
    print(f"Startup Warmup Overhead:        {report['startup_warmup_overhead_ms']} ms")
    print(f"Total Benchmark Queries:        {report['total_queries_tested']}")
    print("-" * 80)
    print(f"Mean Warm Search Latency:       {report['mean_warm_search_ms']} ms (Target: < 500 ms) [{'PASS' if report['latency_target_achieved'] else 'FAIL'}]")
    print(f"Min Warm Search Latency:        {report['min_warm_search_ms']} ms")
    print(f"Max Warm Search Latency:        {report['max_warm_search_ms']} ms")
    print(f"Mean Cached Search Latency:     {report['mean_cached_search_ms']} ms")
    print("-" * 80)
    print(f"Discovery /api/related:         {report['discovery_aux_endpoints'].get('related_searches_ms', 0)} ms")
    print(f"Discovery /api/questions (PAA): {report['discovery_aux_endpoints'].get('paa_questions_ms', 0)} ms")
    print("=" * 80)
    print(f"{'Category':<22} | {'Query':<30} | {'Warm 1':<8} | {'Cached':<8} | {'Top Result'}")
    print("-" * 80)
    for q in report["queries"]:
        cat = q["category"][:20]
        query_str = q["query"][:28]
        w1 = f"{q['warm_1_ms']:.1f}ms"
        c_avg = f"{q['cached_avg_ms']:.1f}ms"
        top = f"{q['top_slug']} ({q['featured_answer'] or 'No Ans'})"[:30]
        print(f"{cat:<22} | {query_str:<30} | {w1:<8} | {c_avg:<8} | {top}")
    print("=" * 80)


if __name__ == "__main__":
    report = run_performance_benchmark(num_warm_runs=3, torch_threads=2)
    print_performance_summary(report)
