"""
PESE Evaluation: Answer Relevance & Evidence Entailment Benchmark Runner
Phase 2D.2 — Scientific evaluation of search truthfulness and answer gating.

Evaluates the Answer Relevance Gate across comprehensive test categories:
  - Direct answers
  - Paraphrased answers
  - Yes/No positive propositions
  - Yes/No negative propositions (with preserved negation)
  - Topic-only distractors (same topic/entity, completely wrong fact)
  - Entity-only distractors
  - Predicate mismatches
  - Attribute mismatches
  - Adversarial topical similarity (high lexical overlap, wrong property)
  - Negation conflicts (stripped negation)
  - Semantic paraphrases (e.g. split fee into installments -> flexible payments)
  - Multiple dates / historical arbitration
  - No-answer abstentions

Metrics reported:
  - Answer Promotion Precision & Recall
  - Abstention Precision & Recall
  - Answer Relevance Accuracy
  - Wrong Featured Answer Rate (Target: 0%)
"""

import time
from typing import Dict, Any, List, Optional
from ..query_analysis.analyzer import QueryAnalyzer
from ..query_analysis.spelling import CorpusSpellingCorrector
from ..passages.answer_relevance import AnswerRelevanceGate, AnswerRelevanceResult


# Benchmark Test Cases
ANSWER_RELEVANCE_DATASET: List[Dict[str, Any]] = [
    # -------------------------------------------------------------
    # 1. Direct Answers (Expected: PASS)
    # -------------------------------------------------------------
    {
        "id": "direct_01_japan_ww2",
        "category": "direct_answer",
        "query": "when did japan enter ww2",
        "passage": "Japan entered World War II in December 1941, following the attack on Pearl Harbor.",
        "candidate": "1941",
        "expected_decision": "PASS",
        "expected_failure_class": None,
        "description": "Direct temporal extraction for historical event",
    },
    {
        "id": "direct_02_bicycle_purchase",
        "category": "direct_answer",
        "query": "when did I buy my bicycle",
        "passage": "On 17 March 2024, I walked into the local shop and bought my commuter bicycle.",
        "candidate": "17 March 2024",
        "expected_decision": "PASS",
        "expected_failure_class": None,
        "description": "Direct specific date extraction for personal query",
    },
    {
        "id": "direct_03_pese_definition",
        "category": "direct_answer",
        "query": "what is PESE",
        "passage": "PESE is a Personal Evil Search Engine built with Python and Next.js.",
        "candidate": "PESE is a Personal Evil Search Engine built with Python and Next.js.",
        "expected_decision": "PASS",
        "expected_failure_class": None,
        "description": "Direct declarative definition extraction",
    },
    {
        "id": "direct_04_bicycle_specs",
        "category": "direct_answer",
        "query": "what is my bicycle specification",
        "passage": "Bicycle specification: Frame is 6061 Aluminum alloy with Shimano Claris 8-speed drivetrain and mechanical disc brakes.",
        "candidate": "Frame is 6061 Aluminum alloy with Shimano Claris 8-speed drivetrain and mechanical disc brakes.",
        "expected_decision": "PASS",
        "expected_failure_class": None,
        "description": "Grounded bicycle component specifications",
    },

    # -------------------------------------------------------------
    # 2. Topic-Only Distractors / Real Failure Cases (Expected: REJECT)
    # -------------------------------------------------------------
    {
        "id": "distractor_01_healing_lounge_failure",
        "category": "topic_only_distractor",
        "query": "does healing lounge offer flexible payments",
        "passage": "The Healing Lounge Pakistan offers therapy and psychiatry. Yasir K. has been working with The Healing Lounge since November 2024.",
        "candidate": "Yasir K. has been working with The Healing Lounge since November 2024.",
        "expected_decision": "REJECT",
        "expected_failure_class": "PREDICATE_MISMATCH",
        "description": "Real Failure Case A: Employment fact promoted for flexible payments query",
    },
    {
        "id": "distractor_02_bicycle_transport_failure",
        "category": "topic_only_distractor",
        "query": "what is my bicycle specification",
        "passage": "Bicycles are the principal means of transport in many regions of the world. They provide low-cost mobility.",
        "candidate": "Bicycles are the principal means of transport in many regions of the world.",
        "expected_decision": "REJECT",
        "expected_failure_class": "PREDICATE_MISMATCH",
        "description": "Real Failure Case B: Generic transport fact promoted for bicycle specs query",
    },
    {
        "id": "distractor_03_adversarial_flexible_scheduling",
        "category": "adversarial_topical_similarity",
        "query": "does healing lounge offer flexible payments",
        "passage": "Healing Lounge offers flexible online appointment scheduling for all clients across Pakistan.",
        "candidate": "Healing Lounge offers flexible online appointment scheduling for all clients across Pakistan.",
        "expected_decision": "REJECT",
        "expected_failure_class": "NO_ANSWER_EVIDENCE",
        "description": "Adversarial: 'flexible' matches but 'payments' has zero evidence",
    },

    # -------------------------------------------------------------
    # 3. Semantic Paraphrase Support (Expected: PASS)
    # -------------------------------------------------------------
    {
        "id": "paraphrase_01_split_installments",
        "category": "semantic_paraphrase",
        "query": "does healing lounge offer flexible payments",
        "passage": "Clients may split the consultation fee into two installments upon request.",
        "candidate": "Clients may split the consultation fee into two installments upon request.",
        "expected_decision": "PASS",
        "expected_failure_class": None,
        "description": "Split fee into installments constitutes grounded evidence for flexible payments",
    },
    {
        "id": "paraphrase_02_payment_options",
        "category": "semantic_paraphrase",
        "query": "does the service offer flexible payment options",
        "passage": "Payment plans and installment options are available for long-term programs.",
        "candidate": "Payment plans and installment options are available for long-term programs.",
        "expected_decision": "PASS",
        "expected_failure_class": None,
        "description": "Installment options directly support flexible payment options",
    },

    # -------------------------------------------------------------
    # 4. Negation Handling (Expected: PASS when preserved, REJECT when stripped)
    # -------------------------------------------------------------
    {
        "id": "negation_01_preserved",
        "category": "yes_no_negative",
        "query": "does the healing lounge offer installment plans",
        "passage": "The Healing Lounge does not currently offer installment payment plans.",
        "candidate": "The Healing Lounge does not currently offer installment payment plans.",
        "expected_decision": "PASS",
        "expected_failure_class": None,
        "description": "Negation preserved in candidate sentence answers yes/no query negatively",
    },
    {
        "id": "negation_02_stripped_rejection",
        "category": "negation",
        "query": "does the healing lounge offer installment plans",
        "passage": "The Healing Lounge does not currently offer installment payment plans.",
        "candidate": "offer installment payment plans",
        "expected_decision": "REJECT",
        "expected_failure_class": "NEGATION_CONFLICT",
        "description": "Stripped negation: candidate dropped 'does not', falsely suggesting feature exists",
    },

    # -------------------------------------------------------------
    # 5. Multiple Dates / Historical Arbitration (Expected: PASS for matched, REJECT for distractor)
    # -------------------------------------------------------------
    {
        "id": "multidate_01_yasir_joined",
        "category": "multiple_dates",
        "query": "When did Yasir join",
        "passage": "The Healing Lounge was founded in 2023. Yasir joined in November 2024.",
        "candidate": "November 2024",
        "expected_decision": "PASS",
        "expected_failure_class": None,
        "description": "Date bound to 'Yasir joined'",
    },
    {
        "id": "multidate_02_wrong_date_distractor",
        "category": "multiple_dates",
        "query": "When did Yasir join",
        "passage": "The Healing Lounge was founded in 2023. Yasir joined in November 2024.",
        "candidate": "2023",
        "expected_decision": "REJECT",
        "expected_failure_class": "PREDICATE_MISMATCH",
        "description": "Distractor date bound to 'founded' rejected for 'join' query",
    },
    {
        "id": "multidate_03_hl_founded",
        "category": "multiple_dates",
        "query": "When was The Healing Lounge founded",
        "passage": "The Healing Lounge was founded in 2023. Yasir joined in November 2024.",
        "candidate": "2023",
        "expected_decision": "PASS",
        "expected_failure_class": None,
        "description": "Date bound to 'founded'",
    },
    {
        "id": "multidate_04_hl_founded_wrong_date",
        "category": "multiple_dates",
        "query": "When was The Healing Lounge founded",
        "passage": "The Healing Lounge was founded in 2023. Yasir joined in November 2024.",
        "candidate": "November 2024",
        "expected_decision": "REJECT",
        "expected_failure_class": "PREDICATE_MISMATCH",
        "description": "Distractor date bound to 'Yasir joined' rejected for 'founded' query",
    },

    # -------------------------------------------------------------
    # 6. Entity & Predicate Mismatches (Expected: REJECT)
    # -------------------------------------------------------------
    {
        "id": "mismatch_01_predicate",
        "category": "predicate_mismatch",
        "query": "how do I clean a bicycle chain",
        "passage": "A bicycle chain transfers power from the pedals to the drive-wheel of a bicycle.",
        "candidate": "A bicycle chain transfers power from the pedals to the drive-wheel of a bicycle.",
        "expected_decision": "REJECT",
        "expected_failure_class": "PREDICATE_MISMATCH",
        "description": "Mechanical definition does not answer procedural clean query",
    },
    {
        "id": "mismatch_02_entity",
        "category": "entity_only_distractor",
        "query": "when was the meiji constitution promulgated",
        "passage": "The Meiji period saw Japan pursue rapid modernization, adopting Western administrative practices.",
        "candidate": "The Meiji period saw Japan pursue rapid modernization.",
        "expected_decision": "REJECT",
        "expected_failure_class": "ANSWER_TYPE_MISMATCH",
        "description": "WHEN query receives descriptive text instead of temporal entity",
    },

    # -------------------------------------------------------------
    # 7. No-Answer Abstentions (Expected: REJECT or ABSTAIN)
    # -------------------------------------------------------------
    {
        "id": "no_answer_01_hl_installment",
        "category": "no_answer",
        "query": "does The Healing Lounge offer installment payments",
        "passage": "The Healing Lounge offers therapy, psychiatry, life coaching, and dietitian services. It operates online and serves clients across Pakistan.",
        "candidate": "The Healing Lounge offers therapy, psychiatry, life coaching, and dietitian services.",
        "expected_decision": "REJECT",
        "expected_failure_class": "NO_ANSWER_EVIDENCE",
        "description": "Document mentions services but zero payment evidence -> must abstain",
    },
]


def run_answer_relevance_evaluation() -> Dict[str, Any]:
    """
    Execute the Answer Relevance & Truthfulness Benchmark Suite.
    Evaluates every case through AnswerRelevanceGate and reports IR truthfulness metrics.
    """
    start_time = time.perf_counter()
    corrector = CorpusSpellingCorrector()
    analyzer = QueryAnalyzer(corrector)
    gate = AnswerRelevanceGate()

    total_cases = len(ANSWER_RELEVANCE_DATASET)
    passed_cases = 0
    failed_cases = 0

    # Metric accumulators
    tp = 0  # Expected PASS, got PASS
    fp = 0  # Expected REJECT/ABSTAIN, got PASS (Wrong Featured Answer!)
    tn = 0  # Expected REJECT/ABSTAIN, got REJECT/ABSTAIN
    fn = 0  # Expected PASS, got REJECT/ABSTAIN

    eval_results = []

    for item in ANSWER_RELEVANCE_DATASET:
        c_id = item["id"]
        cat = item["category"]
        query = item["query"]
        passage = item["passage"]
        candidate = item["candidate"]
        exp_dec = item["expected_decision"]
        exp_fail = item.get("expected_failure_class")

        analyzed = analyzer.analyze_query(query)
        result = gate.evaluate(
            query=query,
            candidate=candidate,
            passage_text=passage,
            analyzed_query=analyzed,
        )

        actual_dec = result.decision
        actual_fail = result.failure_class

        # Decision match:
        # If expected is PASS, actual must be PASS.
        # If expected is REJECT, actual must be REJECT or ABSTAIN.
        if exp_dec == "PASS":
            is_correct = (actual_dec == "PASS")
            if is_correct:
                tp += 1
            else:
                fn += 1
        else:
            is_correct = (actual_dec in ("REJECT", "ABSTAIN"))
            if is_correct:
                tn += 1
            else:
                fp += 1

        if is_correct:
            passed_cases += 1
        else:
            failed_cases += 1

        eval_results.append({
            "id": c_id,
            "category": cat,
            "query": query,
            "candidate": candidate[:60] + "..." if len(candidate) > 60 else candidate,
            "expected_decision": exp_dec,
            "actual_decision": actual_dec,
            "expected_failure_class": exp_fail,
            "actual_failure_class": actual_fail,
            "correct": is_correct,
            "final_entailment": result.final_entailment,
            "entity_alignment": result.entity_alignment,
            "predicate_alignment": result.predicate_alignment,
            "property_alignment": result.property_alignment,
            "answer_type_alignment": result.answer_type_alignment,
            "semantic_support": result.semantic_support,
            "negation_preserved": result.negation_preserved,
            "reason": result.reason,
        })

    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    # Scientific Truthfulness Metrics
    promotion_precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 1.0
    promotion_recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    abstention_precision = round(tn / (tn + fn), 4) if (tn + fn) > 0 else 1.0
    abstention_recall = round(tn / (tn + fp), 4) if (tn + fp) > 0 else 0.0
    relevance_accuracy = round((tp + tn) / total_cases, 4) if total_cases > 0 else 0.0
    wrong_answer_rate = round(fp / (tp + fp), 4) if (tp + fp) > 0 else 0.0

    summary = {
        "benchmark_name": "PESE Phase 2D.2 Answer Relevance & Truthfulness Suite",
        "total_test_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "answer_relevance_accuracy": relevance_accuracy,
        "wrong_featured_answer_rate": wrong_answer_rate,
        "answer_promotion_precision": promotion_precision,
        "answer_promotion_recall": promotion_recall,
        "abstention_precision": abstention_precision,
        "abstention_recall": abstention_recall,
        "true_positives": tp,
        "false_positives_wrong_answers": fp,
        "true_negatives_correct_abstentions": tn,
        "false_negatives": fn,
        "elapsed_ms": elapsed_ms,
        "target_wrong_answer_rate": "0.0%",
        "status": "PASS" if fp == 0 and relevance_accuracy >= 0.90 else "FAIL",
    }

    return {
        "summary": summary,
        "test_results": eval_results,
    }


if __name__ == "__main__":
    import json
    res = run_answer_relevance_evaluation()
    print(json.dumps(res["summary"], indent=2))
