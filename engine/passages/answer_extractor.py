"""
PESE Passages: Generalized Featured-Answer Engine
Extracts grounded, intent-aligned answers across WHEN, WHAT, WHY, HOW, WHO, WHERE.
Applies temporal specificity (e.g. preferring '17 March 2024' over '2024'),
sentence-level semantic binding, harmonic proximity arbitration,
and enforces strict eligibility gates to prevent weak/hallucinated answers.
"""

import re
import logging
from typing import Optional, Tuple, List, Dict, Any
from ..query_analysis.intent import QueryIntent
from ..query_analysis.analyzer import AnalyzedQuery
from ..nlp.stemmer import stem_word
from .answer_relevance import AnswerRelevanceGate, AnswerRelevanceResult

# Yes/No query starter words (queries that use WHAT intent but are really yes/no)
_YESNO_STARTERS = {"does", "is", "are", "can", "has", "have", "was", "were", "do", "will", "would", "shall"}


from ..nlp.evidence import ACRONYMS, term_matches as _term_matches, term_spans as _get_term_match_spans, sentences as split_into_sentences

# Temporal Patterns with Specificity Weights (higher = more specific)
TEMPORAL_PATTERNS = [
    # 1. Full date: '17 March 2024' or 'March 17, 2024' (Specificity 3)
    (re.compile(r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b', re.IGNORECASE), 3.0),
    (re.compile(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b', re.IGNORECASE), 3.0),
    (re.compile(r'\b\d{4}-\d{2}-\d{2}\b'), 3.0),

    # 2. Month + Year: 'March 2024' or 'mid-March' (Specificity 2)
    (re.compile(r'\b(?:in\s+)?(?:mid-)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b', re.IGNORECASE), 2.0),
    (re.compile(r'\b(?:in\s+)?(?:mid-)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\b', re.IGNORECASE), 1.5),

    # 3. Standalone Year or Season: '2024', '1941', 'late July' (Specificity 1)
    (re.compile(r'\b[1-9]\d{3}\b'), 1.0),
    (re.compile(r'\b(?:summer|spring|autumn|fall|winter)(?:\s+(?:19|20)\d{2})?\b', re.IGNORECASE), 1.2),
]

# Causal indicators for WHY intent
CAUSAL_PATTERNS = [
    re.compile(r'\b(?:occurs when|happens when|results from|caused by|the reason is|due to|because)\b', re.IGNORECASE),
    re.compile(r'\b(?:differs from|mismatch between|failure of)\b', re.IGNORECASE),
]

# Definitional indicators for WHAT intent
DEFINITIONAL_PATTERNS = [
    re.compile(r'\b(?:is a|is an|is the|refers to|means|defined as|consists of|cannot rank what|is developed with|developed with|built with|written in)\b', re.IGNORECASE),
]


def extract_best_temporal_answer(text: str) -> Optional[str]:
    """
    Extract the most specific temporal expression from text.
    Prefers '17 March 2024' over 'March 2024' over '2024'.
    Rejects subwords or numbers starting with 0 (e.g. 000).
    """
    best_match: Optional[str] = None
    best_specificity = 0.0

    for pattern, specificity in TEMPORAL_PATTERNS:
        matches = pattern.finditer(text)
        for m in matches:
            val = m.group(0).strip()
            val = re.sub(r'^(?:in|on|at|around)\s+', '', val, flags=re.IGNORECASE).strip()
            if val.startswith("0") or ",0" in val:
                continue
            # If higher specificity found, take it
            if specificity > best_specificity:
                best_specificity = specificity
                best_match = val

    return best_match



class FeaturedAnswerExtractor:
    """Extracts generalized featured answers grounded in the winning passage."""

    def __init__(self):
        # Instantiate once at class level to avoid per-call overhead
        self.relevance_gate = AnswerRelevanceGate()
        self.last_relevance_result: Optional[AnswerRelevanceResult] = None
        self.pipeline_audit = {}

    def extract_source_answer(self, analyzed_query, passages, title, document_score):
        """Production V2 entry point; legacy single-passage API stays testable."""
        from .answer_pipeline import AnswerPipeline
        pipeline = AnswerPipeline()
        if document_score < 12:
            self.pipeline_audit = {"arbitration": "ABSTAIN: document confidence below unchanged threshold"}
            return None, self.pipeline_audit["arbitration"]
        try:
            answer, reason = pipeline.run(analyzed_query.effective_query, passages, title)
        except Exception as exc:
            pipeline.audit.update(arbitration=f"ABSTAIN: ANSWER_GATE_EXCEPTION: {type(exc).__name__}")
            answer, reason = None, pipeline.audit["arbitration"]
        self.pipeline_audit = pipeline.audit
        return answer, reason

    def _apply_relevance_gate(
        self,
        answer_text: Optional[str],
        justification: str,
        passage_text: str,
        analyzed_query: AnalyzedQuery,
    ) -> Tuple[Optional[str], str]:
        """
        Run the Answer Relevance Gate on *answer_text*.
        Stores last result in self.last_relevance_result.
        Returns (answer_text, justification) if PASS, else (None, suppression_reason).

        Fail closed if validation is unavailable. The failure is inspectable.
        """
        if answer_text is None:
            self.last_relevance_result = None
            return None, justification

        try:
            result = self.relevance_gate.evaluate(
                query=analyzed_query.original_query,
                candidate=answer_text,
                passage_text=passage_text,
                analyzed_query=analyzed_query,
            )
            self.last_relevance_result = result
            if result.decision != "PASS":
                return (
                    None,
                    f"Suppressed by Answer Relevance Gate: {result.failure_class} — {result.reason}",
                )
            return answer_text, justification
        except Exception as exc:
            logging.getLogger(__name__).exception("answer_gate_failed")
            self.last_relevance_result = AnswerRelevanceResult(
                candidate=answer_text, query=analyzed_query.original_query,
                passage_text=passage_text, decision="ABSTAIN",
                failure_class="ANSWER_GATE_EXCEPTION", reason=f"{type(exc).__name__}: {exc}",
            )
            return None, "Suppressed: answer validation unavailable"

    def extract_answer(
        self,
        passage_text: str,
        analyzed_query: AnalyzedQuery,
        passage_score: float,
        document_score: float,
        top_passage: Optional[Any] = None,
    ) -> Tuple[Optional[str], str]:
        """
        Extract an answer from the winning passage based on query intent.
        Returns (answer_string or None, confidence_justification).
        """
        # Reset last gate result for this call
        self.last_relevance_result = None

        # Eligibility Gate 1: Minimum Document and Passage Confidence
        min_doc_score = 9.0 if (top_passage and getattr(top_passage, "block_type", "") == "faq") else 12.0
        min_psg_score = 4.5 if (top_passage and getattr(top_passage, "block_type", "") == "faq") else 6.0

        if document_score < min_doc_score or passage_score < min_psg_score:
            return None, "Suppressed: Document or passage score below answer confidence threshold"

        intent = analyzed_query.intent
        content_terms = list(analyzed_query.effective_content_terms)
        evidence_sentences = split_into_sentences(passage_text)
        _, predicates, properties = self.relevance_gate._extract_query_semantic_components(analyzed_query)
        relation_terms = predicates + properties
        candidates = []

        # All producers feed this same list, and every candidate is validated.
        if top_passage and getattr(top_passage, "block_type", "") == "faq":
            faq_answer = getattr(top_passage, "structural_metadata", {}).get("faq_answer", "")
            if faq_answer:
                candidates.append((faq_answer, 100.0, "Native FAQ match: validated against the current question"))

        for sentence in evidence_sentences:
            term_score = sum(1.0 for t in content_terms if self.relevance_gate._matches(t, sentence))
            relation_score = sum(3.0 for t in relation_terms if self.relevance_gate._matches(t, sentence))
            score = term_score + relation_score
            if not term_score:
                continue
            if intent == QueryIntent.WHEN:
                date_candidates = []
                # Rank dates within their own sentence, conditioned on the query.
                for pattern, specificity in TEMPORAL_PATTERNS:
                    for match in pattern.finditer(sentence):
                        value = re.sub(r'^(?:in|on|at|around)\s+', '', match.group(), flags=re.I).strip()
                        if value.startswith("0"):
                            continue
                        midpoint = (match.start()+match.end())/2
                        proximity = 0.0
                        for term in relation_terms or content_terms:
                            spans = _get_term_match_spans(term, sentence)
                            if spans:
                                distance = min(abs(midpoint-(a+b)/2) for a,b in spans)
                                proximity += 1/(1+distance/8)
                        date_candidates.append((value, specificity*2+proximity*3))
                if date_candidates:
                    value, date_score = max(date_candidates, key=lambda item:item[1])
                    candidates.append((value, score + date_score/100, "Extracted temporal answer with specificity preference and query-conditioned sentence binding"))
            elif intent == QueryIntent.WHY:
                if any(pattern.search(sentence) for pattern in CAUSAL_PATTERNS):
                    candidates.append((sentence,score,"Extracted causal evidence"))
            elif intent == QueryIntent.HOW:
                contract = self.relevance_gate._classify_interrogative_contract(analyzed_query)
                if contract == "HOW_MANY" or re.search(r"\b(step|use|apply|first|then|check|inspect|by)\b",sentence,re.I):
                    candidates.append((sentence,score,"Extracted quantitative or procedural evidence"))
            elif intent in (QueryIntent.WHAT, QueryIntent.WHO, QueryIntent.WHERE):
                candidates.append((sentence,score,"Extracted query-conditioned declarative evidence"))
            elif term_score >= 2:
                candidates.append((sentence,score,"Extracted lead passage summary statement"))

        candidates.sort(key=lambda item:item[1],reverse=True)
        accepted = []
        rejected_reason = "No grounded candidate met the query contract"
        rejected_verdict = None
        seen = set()
        for answer, score, reason in candidates:
            if answer in seen:
                continue
            seen.add(answer)
            validated, explanation = self._apply_relevance_gate(answer,reason,passage_text,analyzed_query)
            if validated:
                accepted.append((validated,score,explanation,self.last_relevance_result))
            elif rejected_verdict is None:
                rejected_reason, rejected_verdict = explanation,self.last_relevance_result
        if accepted:
            contract = self.relevance_gate._classify_interrogative_contract(analyzed_query)
            if contract == "DOES_IS_CAN" and len(accepted) > 1:
                polarities = {bool(re.search(r"\b(?:not|never|no longer|unavailable|cannot)\b", c[0], re.I)) for c in accepted}
                if len(polarities) > 1:
                    self.last_relevance_result = accepted[0][3].model_copy(update={"decision":"ABSTAIN", "failure_class":"CONTRADICTORY_EVIDENCE", "reason":"Nearby positive and negative policy propositions have no explicit structural resolution"})
                    return None, "Suppressed: contradictory local policy evidence"
            # Equally relevant sentences that assert different dates for the same
            # relationship are unresolved evidence, not a date-priority contest.
            if intent == QueryIntent.WHEN and len(accepted)>1:
                best = accepted[0]
                conflicts = [c for c in accepted[1:] if int(c[1]) == int(best[1]) and c[0] != best[0]]
                if conflicts:
                    self.last_relevance_result = best[3].model_copy(update={"decision":"ABSTAIN", "failure_class":"CONTRADICTORY_EVIDENCE", "reason":"Multiple equally relevant event dates; source does not resolve them"})
                    return None,"Suppressed: contradictory temporal evidence"
            answer,_,reason,verdict = accepted[0]
            self.last_relevance_result = verdict
            return answer,reason
        self.last_relevance_result = rejected_verdict
        return None,rejected_reason
