"""
PESE Discovery: Scientific Evaluation Runner (Phase 2A)
Evaluates Autocomplete, Typo Suggestions, Related Searches,
'You Might Also Ask' (PAA) Answerability Gate, and Cold-Start vs Warm-State isolation.
"""

import time
import json
from pathlib import Path
from typing import Dict, Any, List

from ..indexing.store import DocumentStore
from ..indexing.inverted_index import InvertedIndex
from ..passages.extractor import PassageExtractor
from ..link_graph.graph import LinkGraph
from ..link_graph.authority import LinkAuthorityCalculator
from ..ranking.scorer import RankingEngine
from ..discovery.autocomplete import AutocompleteEngine
from ..discovery.related_searches import RelatedSearchEngine
from ..discovery.questions import PAAQuestionEngine
from ..discovery.history import LocalHistoryStore
from ..discovery.sessions import SessionManager
from ..discovery.families import QueryFamilyRegistry
from .synthetic_history import load_synthetic_history
from .discovery_dataset import (
    AUTOCOMPLETE_TEST_CASES,
    RELATED_SEARCHES_TEST_CASES,
    PAA_TEST_CASES,
)

REPORT_PATH = Path(__file__).resolve().parent.parent / "data" / "discovery_report.json"


def run_discovery_evaluation() -> Dict[str, Any]:
    """Execute end-to-end scientific evaluation for Phase 2A discovery features."""
    store = DocumentStore()
    docs = store.list_documents(status="published")

    extractor = PassageExtractor()
    index = InvertedIndex()
    for doc in docs:
        passages = extractor.extract_passages(doc)
        index.index_document(doc, passages)

    graph = LinkGraph()
    graph.build_from_documents(docs)
    auth = LinkAuthorityCalculator(graph)
    auth.compute_scores()

    ranking_engine = RankingEngine(index, auth)

    # Use a clean test history store for evaluation
    test_events_path = Path(__file__).resolve().parent.parent / "data" / "test_discovery_events.jsonl"
    if test_events_path.exists():
        test_events_path.unlink()

    history_store = LocalHistoryStore(events_path=test_events_path)
    session_manager = SessionManager(history_store)
    family_registry = QueryFamilyRegistry()

    autocomplete = AutocompleteEngine(
        store=store,
        spelling_corrector=ranking_engine.spelling_corrector,
        history_store=history_store,
        session_manager=session_manager,
        family_registry=family_registry,
    )

    related_engine = RelatedSearchEngine(
        store=store,
        graph=graph,
        history_store=history_store,
        session_manager=session_manager,
        family_registry=family_registry,
    )

    paa_engine = PAAQuestionEngine(
        store=store,
        ranking_engine=ranking_engine,
        family_registry=family_registry,
    )

    # ==================== 1. COLD-START AUTOCOMPLETE BENCHMARK ====================
    auto_hits_at_1 = 0
    auto_hits_at_3 = 0
    auto_reciprocal_ranks: List[float] = []
    typo_recovered_count = 0
    total_typo_cases = 0

    auto_details = []

    for case in AUTOCOMPLETE_TEST_CASES:
        prefix = case["prefix"]
        expected_top = case["expected_top_contains"].lower()
        is_typo = case["is_typo"]
        if is_typo:
            total_typo_cases += 1

        res = autocomplete.get_suggestions(prefix, limit=5)
        suggestions = [s.text.lower() for s in res.suggestions]

        hit_1 = False
        hit_3 = False
        rr = 0.0

        for rank, text in enumerate(suggestions, start=1):
            if expected_top in text or any(exp.lower() in text for exp in case.get("expected_suggestions", [])):
                if rank == 1:
                    hit_1 = True
                if rank <= 3:
                    hit_3 = True
                rr = 1.0 / rank
                break

        if hit_1:
            auto_hits_at_1 += 1
        if hit_3:
            auto_hits_at_3 += 1
        auto_reciprocal_ranks.append(rr)

        if is_typo and res.has_typo_correction:
            typo_recovered_count += 1

        auto_details.append({
            "prefix": prefix,
            "is_typo": is_typo,
            "corrected_prefix": res.corrected_prefix,
            "suggestions": [s.text for s in res.suggestions[:3]],
            "hit_at_1": hit_1,
            "hit_at_3": hit_3,
            "reciprocal_rank": rr,
        })

    total_auto = len(AUTOCOMPLETE_TEST_CASES)
    auto_mrr = sum(auto_reciprocal_ranks) / max(1, total_auto)
    auto_p_at_1 = auto_hits_at_1 / max(1, total_auto)
    auto_p_at_3 = auto_hits_at_3 / max(1, total_auto)
    typo_recovery_rate = typo_recovered_count / max(1, total_typo_cases)

    # ==================== 2. RELATED SEARCHES BENCHMARK ====================
    rel_coherence_passes = 0
    rel_empty_passes = 0
    total_rel_queries = len(RELATED_SEARCHES_TEST_CASES)
    rel_details = []

    for case in RELATED_SEARCHES_TEST_CASES:
        q = case["query"]
        expected_count = case.get("expected_count")

        # Get SERP top slugs
        serp = ranking_engine.search(q, limit=5)
        top_slugs = [r.slug for r in serp]

        rel_res = related_engine.get_related_searches(q, top_slugs=top_slugs, limit=5)
        rel_queries = [r.query.lower() for r in rel_res.related_searches]

        passed = False
        if expected_count is not None:
            # Empty state test
            passed = len(rel_queries) == expected_count
            if passed:
                rel_empty_passes += 1
        else:
            # Check coherence: must contain at least one relevant term and zero forbidden terms
            has_relevant = any(
                any(term in rq for term in case.get("relevant_terms", []))
                for rq in rel_queries
            )
            has_forbidden = any(
                any(term in rq for term in case.get("must_not_contain", []))
                for rq in rel_queries
            )
            count_ok = len(rel_queries) >= case.get("expected_min_count", 1)
            passed = has_relevant and not has_forbidden and count_ok
            if passed:
                rel_coherence_passes += 1

        rel_details.append({
            "query": q,
            "related_count": len(rel_queries),
            "surfaced": [r.query for r in rel_res.related_searches],
            "passed": passed,
        })

    rel_accuracy = (rel_coherence_passes + rel_empty_passes) / max(1, total_rel_queries)

    # ==================== 3. 'YOU MIGHT ALSO ASK' (PAA) BENCHMARK ====================
    paa_answerability_passes = 0
    paa_duplicate_violations = 0
    paa_details = []
    total_paa_cases = len(PAA_TEST_CASES)

    for case in PAA_TEST_CASES:
        q = case["query"]
        expected_count = case.get("expected_count")

        serp = ranking_engine.search(q, limit=5)
        top_slugs = [r.slug for r in serp]

        paa_res = paa_engine.get_questions_for_query(q, top_slugs=top_slugs, limit=4)
        surfaced = paa_res.questions

        passed = False
        if expected_count is not None:
            # Empty state test: must suppress all questions on unsupported topics
            passed = len(surfaced) == expected_count
            if passed:
                paa_answerability_passes += 1
        else:
            # Answerability Gate check: 100% of surfaced questions MUST have valid answers
            all_have_answers = all(
                q_item.answerability_status == "PASS" and len(q_item.answer.strip()) > 5
                for q_item in surfaced
            )
            # Check expected question or answers
            has_expected = False
            for q_item in surfaced:
                if any(exp.lower() in q_item.question.lower() for exp in case.get("expected_answerable_questions", [])):
                    has_expected = True
                    break
                if any(exp.lower() in q_item.answer.lower() for exp in case.get("expected_answers_contain", [])):
                    has_expected = True
                    break

            passed = all_have_answers and (has_expected or len(surfaced) > 0)
            if passed:
                paa_answerability_passes += 1

        # Check duplicates
        q_texts = [q_item.question.lower() for q_item in surfaced]
        if len(q_texts) != len(set(q_texts)):
            paa_duplicate_violations += 1

        paa_details.append({
            "query": q,
            "questions_count": len(surfaced),
            "surfaced_pairs": [(q_item.question, q_item.answer) for q_item in surfaced],
            "passed": passed,
        })

    paa_precision = paa_answerability_passes / max(1, total_paa_cases)

    # ==================== 4. COLD-START VS WARM-STATE ISOLATION CHECK ====================
    # Capture document ranking for core query before history is loaded
    serp_before = ranking_engine.search("what should I learn next in japanese", limit=5)
    slugs_before = [r.slug for r in serp_before]
    scores_before = [r.final_score for r in serp_before]

    # Pre-warm autocomplete ranking for 'what sh'
    auto_cold = autocomplete.get_suggestions("what sh", limit=3)
    cold_top_text = auto_cold.suggestions[0].text if auto_cold.suggestions else None

    # Load synthetic history into history store
    loaded_events = load_synthetic_history(history_store)

    # Re-query autocomplete with warm state
    auto_warm = autocomplete.get_suggestions("what sh", limit=3)
    warm_top_text = auto_warm.suggestions[0].text if auto_warm.suggestions else None

    # Re-query core document search to verify STRICT ZERO CONTAMINATION
    serp_after = ranking_engine.search("what should I learn next in japanese", limit=5)
    slugs_after = [r.slug for r in serp_after]
    scores_after = [r.final_score for r in serp_after]

    doc_ranking_uncontaminated = (slugs_before == slugs_after) and (scores_before == scores_after)

    # Cleanup test events file
    if test_events_path.exists():
        test_events_path.unlink()

    summary = {
        "benchmark_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_autocomplete_cases": total_auto,
        "autocomplete_mrr": round(auto_mrr, 4),
        "autocomplete_p_at_1": round(auto_p_at_1, 4),
        "autocomplete_p_at_3": round(auto_p_at_3, 4),
        "typo_recovery_rate": round(typo_recovery_rate, 4),
        "total_related_queries": total_rel_queries,
        "related_search_accuracy": round(rel_accuracy, 4),
        "total_paa_cases": total_paa_cases,
        "paa_answerability_precision": round(paa_precision, 4),
        "paa_duplicate_violations": paa_duplicate_violations,
        "cold_start_top_suggestion": cold_top_text,
        "warm_state_top_suggestion": warm_top_text,
        "doc_ranking_uncontaminated": doc_ranking_uncontaminated,
        "autocomplete_details": auto_details,
        "related_details": rel_details,
        "paa_details": paa_details,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    s = run_discovery_evaluation()
    print("=================================================================")
    print(" [PESE PHASE 2A DISCOVERY BENCHMARK REPORT] ")
    print("=================================================================")
    print(f"Autocomplete Evaluated:           {s['total_autocomplete_cases']}")
    print(f"Autocomplete MRR:                 {s['autocomplete_mrr']:.4f}")
    print(f"Autocomplete Hit@1 Rate:          {s['autocomplete_p_at_1'] * 100:.1f}%")
    print(f"Autocomplete Hit@3 Rate:          {s['autocomplete_p_at_3'] * 100:.1f}%")
    print(f"Typo Suggestion Recovery Rate:    {s['typo_recovery_rate'] * 100:.1f}%")
    print(f"Related Search Coherence Rate:    {s['related_search_accuracy'] * 100:.1f}%")
    print(f"PAA Answerability Precision:      {s['paa_answerability_precision'] * 100:.1f}%")
    print(f"PAA Duplicate Violations:         {s['paa_duplicate_violations']} (Target: 0)")
    print(f"Doc Ranking Contamination:        {'ZERO (Passed)' if s['doc_ranking_uncontaminated'] else 'FAILED'}")
    print("=================================================================")
