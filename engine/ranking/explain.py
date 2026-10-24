"""
PESE Ranking: Explain
Provides detailed comparative audit answering:
"WHY did result A defeat result B?"
"""

from typing import Dict, Any, List
from .scorer import RankingTrace


def compare_traces(trace_a: RankingTrace, trace_b: RankingTrace) -> Dict[str, Any]:
    """
    Compare two ranking traces and generate a decisive audit explanation
    explaining why Document A outranked or lost to Document B.
    """
    winner = trace_a if trace_a.final_score >= trace_b.final_score else trace_b
    loser = trace_b if winner == trace_a else trace_a

    diff_score = winner.final_score - loser.final_score
    insights: List[str] = []

    # 1. Spam check
    if loser.spam_penalty > winner.spam_penalty:
        penalty_diff = round((loser.spam_penalty - winner.spam_penalty) * 100, 1)
        insights.append(
            f"[Spam Penalty Factor]: '{loser.title}' suffered a {penalty_diff}% higher spam penalty "
            f"due to: {', '.join(loser.spam_reasons)}."
        )

    # 2. Passage relevance
    if abs(winner.passage_signal - loser.passage_signal) >= 1.0:
        if winner.passage_signal > loser.passage_signal:
            insights.append(
                f"[Passage Precision]: '{winner.title}' contained a significantly more relevant passage "
                f"(passage score {winner.passage_signal:.2f} vs {loser.passage_signal:.2f})."
            )
        else:
            insights.append(
                f"[Passage Signal]: '{loser.title}' had a stronger passage score ({loser.passage_signal:.2f} vs {winner.passage_signal:.2f}), "
                f"but was overcome by other signals."
            )

    # 3. Query term coverage
    if winner.coverage_ratio > loser.coverage_ratio:
        insights.append(
            f"[Query Term Coverage]: '{winner.title}' matched {winner.matched_query_terms}/{winner.total_query_terms} query terms "
            f"(coverage factor {winner.coverage_factor:.2f}) vs '{loser.title}' matching {loser.matched_query_terms}/{loser.total_query_terms}."
        )

    # 4. Phrase match
    if winner.phrase_signal > loser.phrase_signal:
        insights.append(
            f"[Exact Phrase Alignment]: '{winner.title}' matched exact multi-word query phrases (+{winner.phrase_signal:.2f})."
        )

    # 5. Title & Heading alignment
    title_head_win = (winner.title_signal + winner.heading_signal)
    title_head_lose = (loser.title_signal + loser.heading_signal)
    if title_head_win > title_head_lose + 1.0:
        insights.append(
            f"[Structural Headings/Title]: '{winner.title}' demonstrated superior title/heading relevance "
            f"({title_head_win:.2f} vs {title_head_lose:.2f})."
        )

    # 6. Lexical BM25F
    if winner.bm25f_lexical > loser.bm25f_lexical:
        insights.append(
            f"[BM25F Lexical Weight]: '{winner.title}' earned higher multi-field BM25F relevance "
            f"({winner.bm25f_lexical:.2f} vs {loser.bm25f_lexical:.2f})."
        )

    # 7. Internal Link Authority
    if abs(winner.link_authority - loser.link_authority) >= 0.3:
        if winner.link_authority > loser.link_authority:
            insights.append(
                f"[Link Graph Authority]: '{winner.title}' has stronger internal backlink authority "
                f"(+{winner.link_authority:.2f} vs +{loser.link_authority:.2f})."
            )

    # 8. Freshness
    if abs(winner.freshness_bonus - loser.freshness_bonus) >= 0.2:
        insights.append(
            f"[Freshness Signal]: '{winner.title}' received +{winner.freshness_bonus:.2f} freshness bonus "
            f"vs +{loser.freshness_bonus:.2f}."
        )

    return {
        "winner_slug": winner.slug,
        "winner_title": winner.title,
        "winner_score": winner.final_score,
        "loser_slug": loser.slug,
        "loser_title": loser.title,
        "loser_score": loser.final_score,
        "score_difference": round(diff_score, 4),
        "decisive_factors": insights,
        "signal_comparison": {
            "bm25f_lexical": {"winner": winner.bm25f_lexical, "loser": loser.bm25f_lexical},
            "passage_signal": {"winner": winner.passage_signal, "loser": loser.passage_signal},
            "title_signal": {"winner": winner.title_signal, "loser": loser.title_signal},
            "heading_signal": {"winner": winner.heading_signal, "loser": loser.heading_signal},
            "phrase_signal": {"winner": winner.phrase_signal, "loser": loser.phrase_signal},
            "coverage_factor": {"winner": winner.coverage_factor, "loser": loser.coverage_factor},
            "link_authority": {"winner": winner.link_authority, "loser": loser.link_authority},
            "freshness_bonus": {"winner": winner.freshness_bonus, "loser": loser.freshness_bonus},
            "quality_bonus": {"winner": winner.quality_bonus, "loser": loser.quality_bonus},
            "spam_penalty": {"winner": winner.spam_penalty, "loser": loser.spam_penalty},
            "final_score": {"winner": winner.final_score, "loser": loser.final_score},
        }
    }
