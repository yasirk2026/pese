"""
PESE Ranking: Minimum Evidence Gate
Filters candidates between retrieval and ranking to ensure every eligible result
possesses genuine topical evidence rather than weak intent/stopword coincidences.
Prefers returning 'No results' over irrelevant random pages.
"""

from typing import List, Dict, Any, Tuple
from ..query_analysis.analyzer import AnalyzedQuery
from ..indexing.inverted_index import InvertedIndex
from ..nlp.stemmer import stem_word


class CandidateEvidenceDecision:
    """Detailed evidence decision for a candidate document."""
    def __init__(self, doc_id: str, slug: str, title: str, passed: bool, reason: str, matched_content_terms: List[str]):
        self.doc_id = doc_id
        self.slug = slug
        self.title = title
        self.passed = passed
        self.reason = reason
        self.matched_content_terms = matched_content_terms

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "slug": self.slug,
            "title": self.title,
            "passed": self.passed,
            "reason": self.reason,
            "matched_content_terms": self.matched_content_terms,
        }


class MinimumEvidenceGate:
    """
    Enforces that candidate documents demonstrate meaningful topical evidence.
    Generic intent words (when, what, why, etc.) or grammatical stopwords ALONE
    never qualify a document for ranking.
    """

    def __init__(self, index: InvertedIndex):
        self.index = index

    def evaluate_candidates(
        self,
        candidates: List[Dict[str, Any]],
        analyzed_query: AnalyzedQuery,
    ) -> Tuple[List[Dict[str, Any]], List[CandidateEvidenceDecision]]:
        """
        Evaluate candidate documents against the Minimum Evidence Gate.
        Returns:
            (passed_candidates, all_decisions)
        """
        passed: List[Dict[str, Any]] = []
        decisions: List[CandidateEvidenceDecision] = []

        content_terms = analyzed_query.effective_content_terms
        content_stems = analyzed_query.effective_stems
        num_content_terms = len(content_terms)

        for candidate in candidates:
            doc_id = candidate["doc_id"]
            slug = candidate["slug"]
            title = candidate["title"]

            matched_content: List[str] = []

            # Check if any effective content terms or stems match this document
            for idx, term in enumerate(content_terms):
                stem = content_stems[idx] if idx < len(content_stems) else term
                posting_term = self.index.index.get(term, {}).get(doc_id)
                posting_stem = self.index.index.get(stem, {}).get(doc_id)
                if posting_term or posting_stem:
                    matched_content.append(term)

            is_semantic_rescue = candidate.get("is_semantic_rescue", False)
            semantic_score = candidate.get("semantic_score", 0.0)
            drift_penalty = candidate.get("drift_penalty", 0.0)

            # RULE 1: If query has content terms, candidate MUST match at least one (or qualify for Semantic Rescue)
            if num_content_terms > 0:
                # Check for completely ungrounded unknown nonsense tokens
                uncorrected_unknowns = [
                    t for t in analyzed_query.content_terms
                    if t not in self.index.index
                    and stem_word(t) not in self.index.index
                    and not any(c.original_token == t for c in analyzed_query.corrections)
                ]
                all_unknown = len(uncorrected_unknowns) == num_content_terms

                if len(matched_content) == 0:
                    # If all content terms in the query are completely ungrounded unknown words,
                    # do NOT allow semantic rescue to hallucinate arbitrary results
                    if all_unknown:
                        decision = CandidateEvidenceDecision(
                            doc_id=doc_id,
                            slug=slug,
                            title=title,
                            passed=False,
                            reason=f"Insufficient evidence: query contains ungrounded term(s) ({', '.join(uncorrected_unknowns)}).",
                            matched_content_terms=[],
                        )
                        decisions.append(decision)
                        continue

                    # Semantic Rescue: Allow high-affinity semantic matches for grounded paraphrases,
                    # provided dense semantic affinity is high and no drift penalty was triggered.
                    if is_semantic_rescue and drift_penalty == 0.0 and semantic_score >= 0.55:
                        decision = CandidateEvidenceDecision(
                            doc_id=doc_id,
                            slug=slug,
                            title=title,
                            passed=True,
                            reason=f"Passed evidence gate via Semantic Rescue: high dense affinity ({semantic_score:.4f}) without lexical overlap.",
                            matched_content_terms=["[semantic_rescue]"],
                        )
                        decisions.append(decision)
                        passed.append(candidate)
                        continue

                    decision = CandidateEvidenceDecision(
                        doc_id=doc_id,
                        slug=slug,
                        title=title,
                        passed=False,
                        reason=f"0/{num_content_terms} meaningful content terms matched. Only generic intent or stopword tokens matched.",
                        matched_content_terms=[],
                    )
                    decisions.append(decision)
                    continue

                # RULE 2: Ungrounded unknown term check
                # If the query contains uncorrected unknown words (e.g. 'zoobadongas'),
                # reject candidates that only match 1 term if unknown words dominate (>= 50%),
                # or reject if all content terms are completely unknown.
                if uncorrected_unknowns:
                    weak_match = len(matched_content) < 2 and (len(uncorrected_unknowns) / num_content_terms) >= 0.5
                    if all_unknown or weak_match:
                        decision = CandidateEvidenceDecision(
                            doc_id=doc_id,
                            slug=slug,
                            title=title,
                            passed=False,
                            reason=f"Insufficient evidence: query contains ungrounded term(s) ({', '.join(uncorrected_unknowns)}). Matched only {len(matched_content)}/{num_content_terms} content terms.",
                            matched_content_terms=matched_content,
                        )
                        decisions.append(decision)
                        continue

                # Passed gate
                decision = CandidateEvidenceDecision(
                    doc_id=doc_id,
                    slug=slug,
                    title=title,
                    passed=True,
                    reason=f"Passed evidence gate: matched {len(matched_content)}/{num_content_terms} content terms ({', '.join(matched_content)}).",
                    matched_content_terms=matched_content,
                )
                decisions.append(decision)
                passed.append(candidate)

            else:
                # Query has NO content terms (pure stopword/intent query, e.g. 'what is when')
                # Require exact phrase match in title or heading
                has_phrase = False
                for phrase in analyzed_query.quoted_phrases:
                    if phrase.lower() in title.lower():
                        has_phrase = True
                        break

                if has_phrase:
                    decision = CandidateEvidenceDecision(
                        doc_id=doc_id,
                        slug=slug,
                        title=title,
                        passed=True,
                        reason="Passed: exact quoted phrase matched in title.",
                        matched_content_terms=[],
                    )
                    decisions.append(decision)
                    passed.append(candidate)
                else:
                    decision = CandidateEvidenceDecision(
                        doc_id=doc_id,
                        slug=slug,
                        title=title,
                        passed=False,
                        reason="Rejected: query contains zero content terms and no exact phrase matches title.",
                        matched_content_terms=[],
                    )
                    decisions.append(decision)

        return passed, decisions
