"""
PESE Discovery: 'You Might Also Ask' (PAA) Engine
Extracts grounded question candidates, enforces the Answerability Gate
by executing the real retrieval & featured-answer pipeline, and ranks
questions by answer confidence and topical relatedness.
"""

import time
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from ..indexing.store import DocumentStore
from ..indexing.document import Document
from ..ranking.scorer import RankingEngine
from .models import PAAQuestionItem, QuestionsResponse
from .families import QueryFamilyRegistry
from .scoring import calculate_paa_score
from ..nlp.stopwords import GENERIC_STOPWORDS, INTENT_WORDS
from .priority import primary_pending


def canonical_question_key(q: str) -> str:
    """Normalize question into a structural canonical key to prevent duplicates."""
    q_clean = q.strip().lower()
    q_clean = re.sub(r'[\?\.\!]+$', '', q_clean)
    words = q_clean.split()

    # Map creator verbs to canonical 'develop'
    replacements = {
        "built": "developed",
        "created": "developed",
        "made": "developed",
        "programmed": "developed",
        "author": "develop",
        "authored": "developed",
        "purchased": "buy",
        "bought": "buy",
        "get": "buy",
    }
    canonical_words = [replacements.get(w, w) for w in words]
    return " ".join(canonical_words)


class PAAQuestionEngine:
    """
    Authoritative 'You Might Also Ask' engine.
    Ensures zero speculation: every question presented to the user
    has been verified through the PESE Answerability Gate.
    """

    def __init__(
        self,
        store: DocumentStore,
        ranking_engine: RankingEngine,
        family_registry: Optional[QueryFamilyRegistry] = None,
    ):
        self.store = store
        self.ranking_engine = ranking_engine
        self.family_registry = family_registry or QueryFamilyRegistry()
        self._cached_candidates: List[Dict[str, Any]] = []
        self._rebuild_question_pool()

    def _rebuild_question_pool(self) -> None:
        """Extract question candidates from document titles, headings, and deterministic facts."""
        pool: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()

        docs = self.store.list_documents(status="published")
        for doc in docs:
            # 1. Document title if question-shaped
            title = doc.title.strip()
            if self._is_question(title):
                clean_q = self._format_question(title)
                c_key = doc.slug + ":" + canonical_question_key(clean_q)
                if c_key not in seen_keys:
                    seen_keys.add(c_key)
                    pool.append({
                        "question": clean_q,
                        "source_slug": doc.slug,
                        "source_title": doc.title,
                        "candidate_source": "document_title",
                    })

            # 2. Document headings that are questions
            for h in doc.get_all_headings():
                if any(h == faq.get("question") for faq in doc.faqs):
                    # Native FAQ entries below retain answer/id/ownership metadata.
                    continue
                if self._is_question(h):
                    clean_h = self._format_question(h)
                    c_key = doc.slug + ":" + canonical_question_key(clean_h)
                    if c_key not in seen_keys:
                        seen_keys.add(c_key)
                        pool.append({
                            "question": clean_h,
                            "source_slug": doc.slug,
                            "source_title": doc.title,
                            "candidate_source": "heading_question",
                        })

            # 4. Native FAQ Schema items
            for f_idx, faq in enumerate(doc.faqs or []):
                fq = faq.get("question", "").strip()
                fa = faq.get("answer", "").strip()
                if fq and fa:
                    clean_fq = self._format_question(fq)
                    c_key = doc.slug + ":" + canonical_question_key(clean_fq)
                    if c_key not in seen_keys:
                        seen_keys.add(c_key)
                        pool.append({
                            "question": clean_fq,
                            "source_slug": doc.slug,
                            "source_title": doc.title,
                            "candidate_source": "native_faq",
                            "direct_answer": fa,
                            "faq_id": faq.get("id") or f"faq-{f_idx+1}",
                        })

        # 5. Add Query Family seed questions
        for fam in self.family_registry.families:
            for sq in fam.seed_questions:
                c_key = (fam.canonical_slugs[0] if fam.canonical_slugs else "") + ":" + canonical_question_key(sq)
                if c_key not in seen_keys:
                    seen_keys.add(c_key)
                    pool.append({
                        "question": sq,
                        "source_slug": fam.canonical_slugs[0] if fam.canonical_slugs else "",
                        "source_title": fam.topic_label,
                        "candidate_source": "query_family",
                    })

        self._cached_candidates = pool

    def reload(self) -> None:
        """Refresh candidate question pool after document index changes."""
        self._rebuild_question_pool()

    def get_questions_for_query(
        self,
        query: str,
        top_slugs: Optional[List[str]] = None,
        limit: int = 4,
        debug: bool = False,
    ) -> QuestionsResponse:
        """
        Evaluate candidate questions for the query, enforce Answerability Gate,
        and return verified questions with pre-extracted featured answers.
        """
        start_time = time.perf_counter()
        q_clean = query.strip()
        q_lower = q_clean.lower()

        if not q_clean:
            return QuestionsResponse(query="", questions=[], took_ms=0.0)

        top_slugs = top_slugs or []
        candidates_to_test = self._select_candidate_questions(q_clean, top_slugs)

        passed_questions: List[PAAQuestionItem] = []
        seen_answers: Set[str] = set()
        evaluated = 0
        seen_questions = set()

        for cand in candidates_to_test:
            if primary_pending() or (time.perf_counter() - start_time) > 0.25:
                break
            q_text = cand["question"]
            relatedness = self._calculate_relatedness(q_lower, q_text.lower(), cand.get("source_slug"), top_slugs)
            if relatedness < 1.0 or canonical_question_key(q_text) in seen_questions:
                continue

            # Avoid surfacing identical query as a PAA question
            if canonical_question_key(q_text) == canonical_question_key(q_clean):
                continue

            # ==================== ANSWERABILITY GATE ====================
            # Run the candidate question through the fast featured-answer pipeline
            # with skip_qa=True to avoid redundant neural reading passes during SERP generation!
            results = self.ranking_engine.search(q_text, limit=3, skip_qa=True)
            evaluated += 1

            # Strict check: system must produce a winning result with a non-null featured answer
            if not results or not results[0].is_featured or not results[0].featured_answer:
                # FAILS GATE: Suppress!
                continue

            top_res = results[0]
            cand_src_slug = cand.get("source_slug")
            if cand_src_slug and top_res.slug != cand_src_slug:
                # A question authored on one source cannot borrow another
                # document's answer merely because it shares a topic.
                continue

            answer_text = top_res.featured_answer.strip()
            ans_norm = answer_text.lower()

            # Prevent duplicate identical answers
            if ans_norm in seen_answers:
                continue

            # Calculate relatedness to current query
            relatedness = self._calculate_relatedness(q_lower, q_text.lower(), cand.get("source_slug"), top_slugs)

            # Minimum relatedness threshold to keep questions topically coherent
            if relatedness < 1.0:
                continue

            # Answer confidence from passage score and document score
            passage_score = top_res.trace.passage_signal
            doc_score = top_res.final_score
            answer_confidence = min(10.0, passage_score * 0.7 + (doc_score / 5.0))

            authority_score = top_res.trace.link_authority

            # Final PAA Score
            final_score, debug_trace = calculate_paa_score(
                relatedness=relatedness,
                answer_confidence=answer_confidence,
                source_authority=authority_score,
            )

            debug_trace["candidate_source"] = cand.get("candidate_source")
            debug_trace["evaluated_slug"] = top_res.slug
            debug_trace["evaluated_title"] = top_res.title
            debug_trace["passage_score"] = passage_score
            debug_trace["gate_passed"] = True

            seen_answers.add(ans_norm)
            seen_questions.add(canonical_question_key(q_text))
            passed_questions.append(
                PAAQuestionItem(
                    question=q_text,
                    answer=answer_text,
                    justification=top_res.featured_justification or "Direct grounded passage answer",
                    source_slug=top_res.slug,
                    source_title=top_res.title,
                    confidence_score=final_score,
                    passage_score=passage_score,
                    answerability_status="PASS",
                    intent=top_res.trace.query_intent,
                    debug_trace=debug_trace if debug else {},
                )
            )

        # Sort descending by final score
        passed_questions.sort(key=lambda x: x.confidence_score, reverse=True)
        selected_questions = passed_questions[:limit]

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        return QuestionsResponse(
            query=q_clean,
            questions=selected_questions,
            total_candidates_evaluated=evaluated,
            total_passed_gate=len(passed_questions),
            took_ms=elapsed_ms,
        )

    def _select_candidate_questions(
        self,
        query: str,
        top_slugs: List[str],
    ) -> List[Dict[str, Any]]:
        """Filter candidate pool for initial candidates matching topic or top slugs."""
        q_lower = query.lower()
        q_tokens = set(re.findall(r'[a-zA-Z0-9_\-]+', q_lower))
        stopwords = GENERIC_STOPWORDS | INTENT_WORDS
        content_tokens = q_tokens - stopwords

        scored_cands: List[Tuple[float, Dict[str, Any]]] = []

        for cand in self._cached_candidates:
            cand_q = cand["question"].lower()
            cand_tokens = set(re.findall(r'[a-zA-Z0-9_\-]+', cand_q)) - stopwords
            overlap = len(content_tokens.intersection(cand_tokens))

            slug_bonus = 3.0 if cand.get("source_slug") in top_slugs[:3] else 0.0
            initial_score = overlap * 2.0 + slug_bonus

            # If question has topic affinity
            if initial_score > 0.0 or any(t in cand_q for t in content_tokens):
                scored_cands.append((initial_score, cand))

        scored_cands.sort(key=lambda x: x[0], reverse=True)
        # Bounded evaluation set to preserve low latency (max 10 candidates evaluated)
        return [c[1] for c in scored_cands[:3]]

    def _calculate_relatedness(
        self,
        query_lower: str,
        question_lower: str,
        cand_slug: Optional[str],
        top_slugs: List[str],
    ) -> float:
        """Compute topical relatedness between current query and candidate question."""
        tokens_a = set(re.findall(r'[a-zA-Z0-9_\-]+', query_lower))
        tokens_b = set(re.findall(r'[a-zA-Z0-9_\-]+', question_lower))
        stopwords = GENERIC_STOPWORDS | INTENT_WORDS

        overlap = (tokens_a - stopwords).intersection(tokens_b - stopwords)
        score = len(overlap) * 1.5

        if cand_slug and cand_slug in top_slugs:
            rank = top_slugs.index(cand_slug)
            score += max(0.5, 2.5 - (0.5 * rank))

        return round(score, 2)

    def _is_question(self, text: str) -> bool:
        t = text.strip()
        if t.endswith("?"):
            return True
        first = t.split()[0].lower() if t.split() else ""
        return first in ("what", "how", "why", "when", "who", "where", "which", "is", "are", "does", "do", "can")

    def _format_question(self, text: str) -> str:
        t = text.strip()
        # Remove markdown symbols
        t = re.sub(r'^#+\s*', '', t)
        t = re.sub(r'^(?:Phase\s+\d+:?|\d+\.?\s*)', '', t).strip()
        if not t.endswith("?"):
            t += "?"
        return t[0].upper() + t[1:]

