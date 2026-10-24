"""
PESE Passages: Scorer
Scores passage relevance using lexical density, term proximity, and question-intent signals.
"""

import re
import math
from typing import List, Dict, Tuple, Optional
from ..indexing.inverted_index import InvertedIndex
from ..indexing.passage import Passage
from ..nlp.tokenizer import QueryRepresentation
from ..nlp.stemmer import stem_word
from ..nlp.evidence import term_matches, sentences
from ..nlp.evidence import ACRONYMS
from ..nlp.local_context import resolve_local_context


# Patterns for dates and temporal expressions (used for "when" / temporal queries)
DATE_PATTERNS = [
    re.compile(r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b', re.IGNORECASE),
    re.compile(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b', re.IGNORECASE),
    re.compile(r'\b\d{4}-\d{2}-\d{2}\b'),
    re.compile(r'\b(?:19|20)\d{2}\b'),
]


def contains_date_pattern(text: str) -> bool:
    """Check if passage contains an explicit date expression."""
    return any(p.search(text) for p in DATE_PATTERNS)


def extract_matched_date(text: str) -> Optional[str]:
    """Extract first explicit date from text."""
    for p in DATE_PATTERNS:
        m = p.search(text)
        if m:
            return m.group(0)
    return None


class PassageScorer:
    """Scores passages for a given document against a search query."""

    def __init__(self, index: InvertedIndex):
        self.index = index
        self.by_slug = {}
        self.sentence_terms = {}
        for passage in index.passages.values():
            self.by_slug.setdefault(passage.slug, []).append(passage)
            rows = []
            for sentence in sentences(passage.text):
                context, _ = resolve_local_context(sentence, passage.text)
                words = re.findall(r"\w+", context.lower())
                rows.append((context, set(words) | {stem_word(w) for w in words}))
            self.sentence_terms[passage.passage_id] = rows

    @staticmethod
    def _has(term, row):
        text, terms = row
        return term in terms or stem_word(term) in terms or (term in ACRONYMS and term_matches(term, text))

    def score_passages_for_doc(
        self,
        doc_slug: str,
        query_rep: QueryRepresentation,
    ) -> List[Tuple[Passage, float, Dict[str, float]]]:
        """
        Evaluate all passages belonging to a document.
        Returns list of (Passage, total_passage_score, score_breakdown) sorted descending by score.
        """
        # Find all passages for this slug
        passages = self.by_slug.get(doc_slug, [])
        if not passages:
            return []

        scored_passages = []
        is_when_query = any(w in query_rep.raw_query.lower().split() for w in ["when", "year", "date", "month"])

        for passage in passages:
            breakdown = self._score_single_passage(passage, query_rep, is_when_query)
            scored_passages.append((passage, breakdown["total"], breakdown))

        scored_passages.sort(key=lambda x: x[1], reverse=True)
        return scored_passages

    def _score_single_passage(
        self,
        passage: Passage,
        query_rep: QueryRepresentation,
        is_when_query: bool,
    ) -> Dict[str, float]:
        """Compute multi-signal score for a single passage."""
        passage_text_lower = passage.text.lower()
        passage_tokens = passage.tokens
        passage_stems = passage.stems

        # 1. Term density & coverage
        query_terms = query_rep.filtered_tokens
        query_stems = query_rep.stems
        matched_terms = set()
        term_freq_sum = 0

        context_heading = passage.heading_context or passage.doc_title
        h_tokens = [w.lower() for w in re.findall(r"\w+", context_heading)] if context_heading else []
        h_stems = [stem_word(w) for w in h_tokens]

        for idx, term in enumerate(query_terms):
            stem = query_stems[idx] if idx < len(query_stems) else term
            in_body = term in passage_tokens or stem in passage_stems or (term in ACRONYMS and term_matches(term,passage.text))
            in_heading = term in h_tokens or stem in h_stems
            if in_body or in_heading:
                matched_terms.add(stem)
                tf = passage_tokens.count(term) + passage_stems.count(stem) + (2 if in_heading else 0)
                tf = max(1,tf)
                # Saturate each term's contribution. Long repetitive passages
                # cannot accumulate unlimited relevance from one query word.
                term_freq_sum += min(4, tf)

        total_unique_qterms = max(1, len(set(query_stems)))
        coverage_ratio = len(matched_terms) / total_unique_qterms

        # Base lexical passage score
        base_lexical = term_freq_sum * 1.5 + (coverage_ratio * 4.0)

        # 2. Term proximity bonus: are matched terms close together?
        proximity_bonus = 0.0
        if len(matched_terms) >= 2 and passage_tokens:
            positions = []
            for idx, token in enumerate(passage_tokens):
                stem = passage_stems[idx] if idx < len(passage_stems) else token
                if stem in matched_terms:
                    positions.append(idx)
            if len(positions) >= 2:
                # Minimum span containing at least 2 distinct matched terms
                min_span = max(1, positions[-1] - positions[0])
                if min_span <= 15:
                    proximity_bonus = max(0.0, (15 - min_span) * 0.3)

        # 3. Exact phrase bonus in passage
        phrase_bonus = 0.0
        for phrase in query_rep.phrases:
            if phrase.lower() in passage_text_lower:
                phrase_bonus += 3.0

        # 4. Question-intent temporal bonus
        temporal_bonus = 0.0
        if is_when_query and contains_date_pattern(passage.text):
            # If query is "when did I..." and passage has a concrete date, award strong passage signal
            temporal_bonus = 4.5

        # 5. Length penalty for excessively short or noisy fragments
        length_factor = 1.0
        if passage.token_count < 6:
            length_factor = 0.4
        elif passage.token_count > 150:
            length_factor = 0.9

        relation_terms = getattr(query_rep, "relation_terms", [])
        relation_bonus = 0.0
        if relation_terms:
            relation_coverage = max((sum(self._has(t,row) for t in relation_terms)/len(relation_terms) for row in self.sentence_terms[passage.passage_id]),default=0.0)
            relation_bonus = 6.0 * relation_coverage
        # Terms in unrelated sentences must not masquerade as one coherent
        # evidence passage. Full co-occurrence retains its existing score.
        heading_terms = set(h_tokens) | set(h_stems)
        sentence_coverage = max((sum(self._has(t,row) or t in heading_terms or stem_word(t) in heading_terms for t in query_terms)/max(1,len(query_terms)) for row in self.sentence_terms[passage.passage_id]),default=0.0)
        coherence_factor = sentence_coverage ** 2 if len(query_terms)>1 else 1.0
        total_score = (base_lexical + proximity_bonus + phrase_bonus + temporal_bonus + relation_bonus) * length_factor * coherence_factor
        # Explicit document structure can distinguish current from archived
        # policy. It does not infer chronology from an arbitrary newer date.
        policy_factor = 1.0
        if not re.search(r"\b(?:old|previous|historical|formerly)\b", query_rep.raw_query, re.I):
            if re.search(r"\b(?:old|previous|archived)\s+policy\b", passage.heading_context or "", re.I):
                policy_factor = 0.6
            elif re.search(r"\bcurrent\s+policy\b", passage.heading_context or "", re.I):
                policy_factor = 1.15
        total_score *= policy_factor

        return {
            "total": total_score,
            "base_lexical": base_lexical,
            "coverage_ratio": coverage_ratio,
            "proximity_bonus": proximity_bonus,
            "phrase_bonus": phrase_bonus,
            "temporal_bonus": temporal_bonus,
            "length_factor": length_factor,
            "relation_bonus": relation_bonus,
            "coherence_factor": coherence_factor,
            "policy_factor": policy_factor,
        }
