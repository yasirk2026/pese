"""
PESE Discovery: Autocomplete Engine
Generates and ranks typo-aware, corpus-derived, and session-informed suggestions
as the user types into the search box.
"""

import time
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from ..indexing.store import DocumentStore
from ..indexing.document import Document
from ..query_analysis.spelling import CorpusSpellingCorrector
from .models import AutocompleteSuggestion, SuggestResponse
from .history import SearchHistoryStore, LocalHistoryStore
from .sessions import SessionManager
from .families import QueryFamilyRegistry
from .scoring import calculate_autocomplete_score


def normalize_suggestion_text(text: str) -> str:
    """Clean markdown artifacts, colons, or punctuation for clean query presentation."""
    # Remove leading markdown headings #
    t = re.sub(r'^#+\s*', '', text)
    # Remove trailing punctuation like colons
    t = re.sub(r'[:\-–—]+$', '', t)
    # Collapse whitespace
    t = ' '.join(t.split())
    return t.strip()


class AutocompleteEngine:
    """
    Authoritative Autocomplete / Query Suggestions engine.
    Extracts corpus candidates, merges behavioural history, handles typos,
    and applies transparent multi-signal scoring.
    """

    def __init__(
        self,
        store: DocumentStore,
        spelling_corrector: CorpusSpellingCorrector,
        history_store: Optional[SearchHistoryStore] = None,
        session_manager: Optional[SessionManager] = None,
        family_registry: Optional[QueryFamilyRegistry] = None,
    ):
        self.store = store
        self.spelling_corrector = spelling_corrector
        self.history_store = history_store or LocalHistoryStore()
        self.session_manager = session_manager or SessionManager(self.history_store)
        self.family_registry = family_registry or QueryFamilyRegistry()
        self._corpus_candidates: Dict[str, Dict[str, Any]] = {}
        self._rebuild_corpus_candidates()

    def _rebuild_corpus_candidates(self) -> None:
        """Extract and index suggestion candidates from all published documents."""
        candidates: Dict[str, Dict[str, Any]] = {}

        docs = self.store.list_documents(status="published")
        for doc in docs:
            # 1. Document title
            title = normalize_suggestion_text(doc.title)
            if title and len(title) >= 3:
                # If title has a subtitle (e.g. "Japanese Beginner Roadmap: From Zero..."), prefer concise version
                if ":" in title:
                    sub = title.split(":")[0].strip()
                    if len(sub) >= 3:
                        candidates[sub.lower()] = {
                            "text": sub,
                            "source": "corpus_title",
                            "corpus_support": 3.0,
                            "doc_slug": doc.slug,
                        }
                    candidates[title.lower()] = {
                        "text": title,
                        "source": "corpus_title_full",
                        "corpus_support": 1.5,
                        "doc_slug": doc.slug,
                    }
                else:
                    candidates[title.lower()] = {
                        "text": title,
                        "source": "corpus_title",
                        "corpus_support": 3.0,
                        "doc_slug": doc.slug,
                    }

            # 2. Document Headings
            for h in doc.headings or []:
                clean_h = normalize_suggestion_text(h)
                # Strip section numbers like "1. ", "Phase 1: "
                clean_h = re.sub(r'^(?:Phase\s+\d+:?|\d+\.?\s*)', '', clean_h).strip()
                if clean_h and 4 <= len(clean_h) <= 60:
                    key = clean_h.lower()
                    if key not in candidates:
                        candidates[key] = {
                            "text": clean_h,
                            "source": "corpus_heading",
                            "corpus_support": 2.2,
                            "doc_slug": doc.slug,
                        }

            # 3. Document Keywords
            for kw in doc.keywords or []:
                clean_kw = normalize_suggestion_text(kw)
                if clean_kw and 3 <= len(clean_kw) <= 45:
                    key = clean_kw.lower()
                    if key not in candidates:
                        candidates[key] = {
                            "text": clean_kw,
                            "source": "corpus_phrase",
                            "corpus_support": 1.8,
                            "doc_slug": doc.slug,
                        }

        # 4. Add Query Family seed queries and questions
        for fam in self.family_registry.families:
            for sq in fam.seed_questions:
                clean_sq = normalize_suggestion_text(sq)
                key = clean_sq.lower()
                if key not in candidates:
                    candidates[key] = {
                        "text": clean_sq,
                        "source": "query_family",
                        "corpus_support": 2.5,
                        "doc_slug": fam.canonical_slugs[0] if fam.canonical_slugs else None,
                    }
            for rq in fam.related_queries:
                clean_rq = normalize_suggestion_text(rq)
                key = clean_rq.lower()
                if key not in candidates:
                    candidates[key] = {
                        "text": clean_rq,
                        "source": "query_family",
                        "corpus_support": 2.0,
                        "doc_slug": fam.canonical_slugs[0] if fam.canonical_slugs else None,
                    }

        self._corpus_candidates = candidates

    def reload(self) -> None:
        """Refresh candidate dictionary after document updates."""
        self._rebuild_corpus_candidates()

    def get_suggestions(
        self,
        raw_prefix: str,
        limit: int = 6,
        session_id: Optional[str] = None,
        debug: bool = False,
    ) -> SuggestResponse:
        """
        Generate ranked suggestions for a given input prefix.
        Handles typo recovery, behavioural boosting, and session context.
        """
        start_time = time.perf_counter()
        clean_prefix = raw_prefix.strip().lower()

        if not clean_prefix or len(clean_prefix) < 1:
            return SuggestResponse(
                query=raw_prefix,
                effective_prefix="",
                suggestions=[],
                took_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
            )

        # Retrieve history data if enabled
        history_enabled = self.history_store.is_history_enabled()
        query_freqs = self.history_store.get_query_frequencies() if history_enabled else {}
        query_clicks = self.history_store.get_query_clicks() if history_enabled else {}

        # 1. Attempt direct prefix matching
        matched_candidates = self._find_matching_candidates(clean_prefix)
        has_typo = False
        corrected_prefix = None

        # 2. If direct prefix match has few/no results, attempt typo recovery
        if len(matched_candidates) < 2 and len(clean_prefix) >= 3:
            # Check typo recovery through spelling corrector
            corrected_term = self._attempt_prefix_spelling_recovery(clean_prefix)
            if corrected_term and corrected_term != clean_prefix:
                typo_matches = self._find_matching_candidates(corrected_term, is_typo=True)
                if typo_matches:
                    has_typo = True
                    corrected_prefix = corrected_term
                    # Merge typo matches
                    for cand_key, cand_data in typo_matches.items():
                        if cand_key not in matched_candidates:
                            matched_candidates[cand_key] = cand_data

        # 3. Score all matched candidates
        scored_suggestions: List[AutocompleteSuggestion] = []

        for cand_key, match_info in matched_candidates.items():
            text = match_info["text"]
            match_type = match_info["match_type"]
            corpus_support = match_info.get("corpus_support", 1.0)
            source = match_info.get("source", "corpus")

            # Behavioural signals
            hist_searches = query_freqs.get(cand_key, 0)
            # Clicks associated with this exact candidate or query
            clicks_for_cand = sum(query_clicks.get(cand_key, {}).values())

            # Session context bonus
            session_bonus, session_reason = self.session_manager.compute_session_context_bonus(
                text, session_id
            )

            # Calculate explainable score
            score, debug_trace = calculate_autocomplete_score(
                prefix_match_type=match_type,
                corpus_support=corpus_support,
                search_frequency=hist_searches,
                recent_searches=min(3, hist_searches),
                successful_clicks=clicks_for_cand,
                session_bonus=session_bonus,
            )

            debug_trace["session_reason"] = session_reason

            # Calculate highlight span for UI
            highlight_ranges = self._compute_highlights(text, clean_prefix, corrected_prefix)

            scored_suggestions.append(
                AutocompleteSuggestion(
                    text=text,
                    source=source,
                    score=score,
                    match_type=match_type,
                    corpus_support=corpus_support,
                    historical_searches=hist_searches,
                    recent_searches=min(3, hist_searches),
                    successful_clicks=clicks_for_cand,
                    session_context_bonus=session_bonus,
                    highlight_ranges=highlight_ranges,
                    debug_trace=debug_trace if debug else {},
                )
            )

        # 4. Sort descending by score, tiebreak by shorter length (more concise)
        scored_suggestions.sort(key=lambda s: (s.score, -len(s.text)), reverse=True)

        # Deduplicate suggestions by normalized lowercase text, preferring concise titles over subtitle variants
        unique_suggestions: List[AutocompleteSuggestion] = []
        seen = set()
        for sug in scored_suggestions:
            norm = re.sub(r'[\?\.\!]+$', '', sug.text.lower()).strip()
            norm = re.sub(r'\bwhat i should\b', 'what should i', norm)
            norm = re.sub(r'\bwhen i bought\b', 'when did i buy', norm)
            base_norm = norm.split(":")[0].strip() if ":" in norm else norm
            if base_norm in seen and ":" in sug.text:
                continue
            if norm not in seen and base_norm not in seen:
                seen.add(norm)
                seen.add(base_norm)
                unique_suggestions.append(sug)
                if len(unique_suggestions) >= limit:
                    break

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        return SuggestResponse(
            query=raw_prefix,
            effective_prefix=corrected_prefix or clean_prefix,
            has_typo_correction=has_typo,
            corrected_prefix=corrected_prefix,
            suggestions=unique_suggestions,
            took_ms=elapsed_ms,
        )

    def _find_matching_candidates(
        self,
        prefix: str,
        is_typo: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """Search across corpus candidates and historical queries for matching prefix."""
        matches: Dict[str, Dict[str, Any]] = {}

        # 1. Check all corpus candidates
        for key, cand in self._corpus_candidates.items():
            match_type = self._determine_match_type(key, prefix, is_typo)
            if match_type:
                matches[key] = {
                    **cand,
                    "match_type": match_type,
                }

        # 2. Check historical queries
        if self.history_store.is_history_enabled():
            freqs = self.history_store.get_query_frequencies()
            for hist_q, freq in freqs.items():
                if hist_q not in matches:
                    match_type = self._determine_match_type(hist_q, prefix, is_typo)
                    if match_type:
                        matches[hist_q] = {
                            "text": hist_q,
                            "source": "query_history",
                            "corpus_support": 1.0,
                            "match_type": match_type,
                        }

        return matches

    def _determine_match_type(self, candidate_key: str, prefix: str, is_typo: bool) -> Optional[str]:
        """Determine match quality: exact_prefix, word_prefix, containment, or typo_recovered."""
        if is_typo:
            if candidate_key.startswith(prefix) or any(w.startswith(prefix) for w in candidate_key.split()):
                return "typo_recovered"
            return None

        # Exact prefix match (e.g. "jap" matches "japanese beginner roadmap")
        if candidate_key.startswith(prefix):
            return "exact_prefix"

        # Word boundary prefix match (e.g. "sh" matches "what should i learn...")
        words = candidate_key.split()
        if any(w.startswith(prefix) for w in words):
            return "word_prefix"

        # Prefix is multi-word and matches start of words in sequence
        # e.g. "what sh" matches "what should i learn next"
        if len(prefix.split()) > 1:
            p_words = prefix.split()
            cand_words = words
            if len(cand_words) >= len(p_words):
                if all(cand_words[i].startswith(p_words[i]) for i in range(len(p_words))):
                    return "exact_prefix"

        # Containment (for longer prefixes >= 4 chars)
        if len(prefix) >= 4 and prefix in candidate_key:
            return "containment"

        return None

    def _attempt_prefix_spelling_recovery(self, prefix: str) -> Optional[str]:
        """Check if prefix itself or its primary token can be recovered via spelling corrector."""
        tokens = prefix.split()
        if not tokens:
            return None

        target_token = tokens[-1].lower()

        # 1. First check if it corrects as a full token (e.g. 'bycycle' -> 'bicycle')
        correction = self.spelling_corrector.correct_token(target_token)
        if correction:
            corrected_tokens = tokens[:-1] + [correction.corrected_token]
            return " ".join(corrected_tokens)

        # 2. Check prefix distance against corpus vocabulary
        from ..query_analysis.spelling import damerau_levenshtein_distance
        vocab = getattr(self.spelling_corrector, "vocab_frequencies", {})
        best_candidate = None
        best_freq = 0

        for word, freq in vocab.items():
            if len(word) >= 3 and len(target_token) >= 3:
                min_len = max(2, len(target_token) - 1)
                max_len = min(len(word), len(target_token) + 1)
                for l in range(min_len, max_len + 1):
                    prefix_slice = word[:l]
                    dist, _ = damerau_levenshtein_distance(target_token, prefix_slice)
                    if dist <= 1 and freq > best_freq:
                        if target_token[0] == word[0] or (len(target_token) > 1 and target_token[1] == word[0]):
                            best_candidate = word
                            best_freq = freq

        if best_candidate:
            corrected_tokens = tokens[:-1] + [best_candidate]
            return " ".join(corrected_tokens)

        return None

    def _compute_highlights(
        self,
        text: str,
        prefix: str,
        corrected_prefix: Optional[str],
    ) -> List[Tuple[int, int]]:
        """Find start and end indices of the matched prefix within the text for UI highlighting."""
        ranges: List[Tuple[int, int]] = []
        p_to_find = (corrected_prefix or prefix).lower()
        t_lower = text.lower()

        # Find first occurrence of prefix
        idx = t_lower.find(p_to_find)
        if idx != -1:
            ranges.append((idx, idx + len(p_to_find)))
        else:
            # Highlight individual tokens
            for tok in p_to_find.split():
                if len(tok) >= 2:
                    t_idx = t_lower.find(tok)
                    if t_idx != -1:
                        ranges.append((t_idx, t_idx + len(tok)))

        return ranges
