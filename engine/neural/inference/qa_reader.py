"""
PESE-QA-0: Inference Reader & Constrained Span Decoding Subsystem
Executes neural reading comprehension with exact token-to-char projection,
vectorized batched forward passes, top-K constrained span decoding,
LRU result caching, answerability thresholds, and multi-passage arbitration.
"""

import re
import math
import hashlib
from collections import OrderedDict
from threading import RLock
from typing import List, Dict, Tuple, Optional, Any
import torch
import torch.nn.functional as F
from pydantic import BaseModel, Field

from ..models.qa_reader import PESEQAReader
from ..tokenization.base import BaseTokenizer
from ..data.contracts import QAExample
from ..data.qa_dataset import build_qa_features, QAInputFeature
from ...nlp.stemmer import stem_word


from ...nlp.evidence import ACRONYMS, term_matches as _term_matches, term_spans

def _is_exact_temporal_span(text: str) -> bool:
    """Check if a span is itself a concise temporal expression (not a clause containing a year)."""
    if not text:
        return False
    # Max words for a concise temporal span
    if len(text.split()) > 5:
        return False
    # Reject strings starting with 0 or containing comma-separated subwords (e.g. '000' from '14,000')
    clean = text.strip(".,;:!?()[]{}\"' ")
    if clean.startswith("0") or ",0" in clean:
        return False
    # Check for 3-4 digit years starting with 1-9 (e.g., 2023, 1941, 1258, 2026)
    if re.search(r"\b[1-9]\d{2,3}(?:\s*(?:CE|BCE|AD|BC))?\b", clean, re.IGNORECASE):
        return True
    # Check for dates with months (e.g. 15 May 2023, 17 March 2024, October 2026)
    if re.search(r"\b(?:\d{1,2}\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december)(?:\s+\d{4})?\b", clean, re.IGNORECASE):
        return True
    # Check for centuries
    if re.search(r"\b\d+(?:st|nd|rd|th)?(?:\s+or\s+\d+(?:st|nd|rd|th)?)?\s+century\b", clean, re.IGNORECASE):
        return True
    return False


def _get_sentence_context(text: str, start_char: int, end_char: int) -> str:
    """Local sentence evidence, preserving original character offsets."""
    from ...nlp.evidence import sentences
    cursor = 0
    for sentence in sentences(text):
        offset = text.find(sentence,cursor)
        if offset < 0:
            continue
        if offset <= start_char and end_char <= offset+len(sentence):
            return sentence.lower()
        cursor = offset+len(sentence)
    return text[start_char:end_char].lower()


class QAResult(BaseModel):
    """Structured extraction output from PESE-QA-0."""
    answer: Optional[str] = None
    answerable: bool = False
    answer_confidence: float = 0.0
    start_confidence: float = 0.0
    end_confidence: float = 0.0
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    start_token: Optional[int] = None
    end_token: Optional[int] = None
    source_passage: str = ""
    source_doc_id: Optional[str] = None
    source_slug: Optional[str] = None
    model: str = "PESE-QA-0"
    abstention_reason: Optional[str] = None
    trace: Dict[str, Any] = Field(default_factory=dict)


class QACache:
    """In-memory thread-safe LRU cache for PESE-QA neural inference."""

    def __init__(self, maxsize: int = 512):
        self.maxsize = maxsize
        self._lock = RLock()
        self._cache: OrderedDict[Tuple[str, str, str], QAResult] = OrderedDict()

    def _make_key(self, model: str, question: str, passage: str) -> Tuple[str, str, str]:
        q_norm = question.strip().lower()
        p_hash = hashlib.sha256(passage.strip().encode("utf-8")).hexdigest()
        return (model, q_norm, p_hash)

    def get(self, model: str, question: str, passage: str) -> Optional[QAResult]:
        key = self._make_key(model, question, passage)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key].model_copy(deep=True)
        return None

    def set(self, model: str, question: str, passage: str, result: QAResult) -> None:
        key = self._make_key(model, question, passage)
        with self._lock:
            self._cache[key] = result.model_copy(deep=True)
            self._cache.move_to_end(key)
            if len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


class PESEQAInferenceReader:
    """
    Inference controller for PESE-QA-0 reading comprehension reader.
    High-performance batched inference with top-K constrained span decoding and LRU caching.
    """

    def __init__(
        self,
        model: PESEQAReader,
        tokenizer: BaseTokenizer,
        max_answer_length: int = 25,
        answerability_threshold: float = 0.50,
        device: str = "cpu"
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.max_answer_length = max_answer_length
        self.answerability_threshold = answerability_threshold
        self.device = torch.device(device)
        self.model.to(self.device)
        self.model.eval()
        self.cache = QACache(maxsize=512)

    def read_passage(
        self,
        question: str,
        passage: str,
        doc_id: Optional[str] = None,
        slug: Optional[str] = None
    ) -> QAResult:
        """
        Reads a single passage conditioned on the question and returns the exact answer span.
        Uses cached result if available, otherwise executes vectorized batched forward pass and top-K decoding.
        """
        if not passage.strip() or not question.strip():
            return QAResult(
                answer=None,
                answerable=False,
                abstention_reason="NO EVIDENCE = NO ANSWER (Empty input)",
                source_passage=passage,
                source_doc_id=doc_id,
                source_slug=slug
            )

        # 1. LRU Cache Check
        cached = self.cache.get("PESE-QA-0", question, passage)
        if cached is not None:
            # Return fresh copy with updated document metadata
            copy_res = cached.model_copy(deep=True)
            copy_res.source_doc_id = doc_id or copy_res.source_doc_id
            copy_res.source_slug = slug or copy_res.source_slug
            copy_res.trace["cache_hit"] = True
            return copy_res

        # 2. Build feature windows
        example = QAExample(
            id="inference-query",
            question=question,
            context=passage,
            is_answerable=True
        )
        features = build_qa_features(
            example=example,
            tokenizer=self.tokenizer,
            max_seq_len=self.model.config.max_seq_len,
            doc_stride=32
        )

        if not features:
            return QAResult(
                answer=None,
                answerable=False,
                abstention_reason="NO EVIDENCE = NO ANSWER (Failed tokenization)",
                source_passage=passage,
                source_doc_id=doc_id,
                source_slug=slug
            )

        # Interrogative intent signals for typed span verification
        q_lower = question.lower()
        is_when_q = bool(re.search(r"\b(when|year|date)\b", q_lower))
        is_num_q = bool(re.search(r"\b(how much|how many|cost|price|count|total)\b", q_lower))
        is_who_q = bool(re.search(r"\b(who|whose|inventor|pioneer|founder|author|creator)\b", q_lower))

        # Query content terms for sliding-window context prioritization
        q_content_words = [
            w for w in re.findall(r"\w+", q_lower)
            if len(w) > 2 and w not in {"when", "what", "where", "which", "who", "did", "was", "the", "and", "for", "with", "from"}
        ]

        # 3. Vectorized Batched Forward Pass in PyTorch
        all_input_ids = torch.tensor([f.input_ids for f in features], dtype=torch.long, device=self.device)
        all_token_types = torch.tensor([f.token_type_ids for f in features], dtype=torch.long, device=self.device)
        all_att_mask = torch.tensor([f.attention_mask for f in features], dtype=torch.long, device=self.device)

        with torch.inference_mode():
            s_logits_batch, e_logits_batch, a_logits_batch, _ = self.model(
                all_input_ids,
                token_type_ids=all_token_types,
                attention_mask=all_att_mask
            )

        best_window_result: Optional[QAResult] = None
        best_window_score = -float("inf")

        # 4. Top-K Span Decoding across windows
        for idx, feat in enumerate(features):
            s_logits = s_logits_batch[idx].cpu()
            e_logits = e_logits_batch[idx].cpu()
            a_logits = a_logits_batch[idx].cpu()

            # Normalize and decode only legal whole-word context boundaries.
            # Tokenization subwords and question/padding positions are not
            # valid competing answer starts/ends.
            valid_start = torch.zeros_like(s_logits,dtype=torch.bool)
            valid_end = torch.zeros_like(e_logits,dtype=torch.bool)
            for position in range(feat.context_token_start,feat.context_token_end):
                offset = feat.token_to_char_offsets[position]
                if offset is None:
                    continue
                a,b = offset
                valid_start[position] = a == 0 or not (passage[a-1].isalnum() and passage[a].isalnum())
                valid_end[position] = b == len(passage) or not (passage[b-1].isalnum() and passage[b].isalnum())
            constrained_s = s_logits.masked_fill(~valid_start,float('-inf'))
            constrained_e = e_logits.masked_fill(~valid_end,float('-inf'))
            s_probs = F.softmax(constrained_s, dim=-1)
            e_probs = F.softmax(constrained_e, dim=-1)
            a_probs = F.softmax(a_logits, dim=-1)

            # Answerability probability: index 1 is answerable
            p_answerable = float(a_probs[1].item())
            null_score = float(s_logits[0].item() + e_logits[0].item())

            c_start = feat.context_token_start
            c_end = feat.context_token_end

            # Window query-term coverage ratio
            valid_offsets = [off for off in feat.token_to_char_offsets[c_start:c_end] if off is not None]
            if not valid_offsets:
                continue
            window_slice = passage[valid_offsets[0][0]:valid_offsets[-1][1]].lower()
            term_matches_count = sum(1 for w in q_content_words if _term_matches(w, window_slice))
            overlap_ratio = term_matches_count / max(1, len(q_content_words))

            # Top-K candidate start and end token positions within context boundaries
            ctx_s = constrained_s[c_start:c_end]
            ctx_e = constrained_e[c_start:c_end]
            k_val = min(12, max(1, c_end - c_start))
            top_s_indices = (torch.topk(ctx_s, k=k_val).indices + c_start).tolist()
            top_e_indices = (torch.topk(ctx_e, k=k_val).indices + c_start).tolist()

            best_span_score = -float("inf")
            best_start = None
            best_end = None

            for i in top_s_indices:
                for j in top_e_indices:
                    if j < i or j >= i + self.max_answer_length:
                        continue
                    if not valid_start[i] or not valid_end[j]:
                        continue
                    score = float(s_logits[i].item() + e_logits[j].item())

                    offset_i = feat.token_to_char_offsets[i]
                    offset_j = feat.token_to_char_offsets[j]
                    if offset_i is None or offset_j is None:
                        continue
                    if offset_i[0] >= offset_j[1]:
                        continue

                    a,b = offset_i[0],offset_j[1]
                    if (a > 0 and passage[a-1].isalnum() and passage[a].isalnum()) or (b < len(passage) and passage[b-1].isalnum() and passage[b].isalnum()):
                        continue
                    span_slice = passage[a:b]
                    if ". " in span_slice or "\n" in span_slice:
                        continue

                    span_clean = span_slice.strip(".,;:!?()[]{}\"' ")
                    if len(span_clean) < 2:
                        continue

                    # Interrogative type matching: reject spans that contradict question intent
                    if is_when_q and not _is_exact_temporal_span(span_clean):
                        continue
                    if is_num_q and not re.search(r"[\d$]", span_clean):
                        continue
                    if is_who_q and re.search(r"^\d+$", span_clean):
                        continue

                    # Semantic binding: boost spans whose local sentence context matches non-stopword query terms
                    sent_ctx = _get_sentence_context(passage, offset_i[0], offset_j[1])
                    sent_match_score = 0.0
                    terms_in_sent = {}
                    for w in q_content_words:
                        if _term_matches(w, sent_ctx):
                            sent_match_score += 1.0
                            # Find positions of this specific term within sentence context
                            t_low = w.lower()
                            s_low = sent_ctx.lower()
                            term_pos = []
                            if t_low in ACRONYMS:
                                for a in ACRONYMS[t_low]:
                                    for m in re.finditer(rf"\b{re.escape(a)}\b", s_low):
                                        term_pos.append(m.start())
                            for m in re.finditer(rf"\b{re.escape(t_low)}\b", s_low):
                                term_pos.append(m.start())
                            stem = stem_word(t_low)
                            if stem and len(stem) >= 3:
                                for m in re.finditer(rf"\b{re.escape(stem)}\w*", s_low):
                                    term_pos.append(m.start())
                            if term_pos:
                                terms_in_sent[w] = term_pos

                    score += 15.0 * (sent_match_score / max(1.0, 1.0 + 3.0 * (len(q_content_words) - 1)))

                    # Harmonic proximity boost for temporal queries with multiple candidate dates
                    if terms_in_sent and is_when_q:
                        ctx_idx = passage.lower().find(sent_ctx)
                        span_in_sent = max(0, offset_i[0] - (ctx_idx if ctx_idx != -1 else offset_i[0]))
                        prox_score = 0.0
                        for w, positions in terms_in_sent.items():
                            min_d = min(abs(span_in_sent - p) for p in positions)
                            weight = 1.0
                            prox_score += weight / (1.0 + (min_d / 8.0))
                        score += prox_score

                    if score > best_span_score:
                        best_span_score = score
                        best_start = i
                        best_end = j

            # Extract character offsets if a valid span was found
            extracted_text = None
            start_char = None
            end_char = None
            span_conf = 0.0
            start_conf = 0.0
            end_conf = 0.0

            if best_start is not None and best_end is not None:
                offset_start = feat.token_to_char_offsets[best_start]
                offset_end = feat.token_to_char_offsets[best_end]

                if offset_start is not None and offset_end is not None:
                    start_char = offset_start[0]
                    end_char = offset_end[1]
                    raw_text = passage[start_char:end_char].strip(".,;:!?()[]{}\"' ")
                    if raw_text and len(raw_text) >= 2 and raw_text.lower() not in {"the", "a", "an", "is", "of", "and", "in", "to", "it"}:
                        if is_when_q:
                            date_m = re.search(r"\b(?:\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|\d{1,2}(?:st|nd|rd|th)?(?:\s+or\s+\d{1,2}(?:st|nd|rd|th)?)?\s+century|[1-9]\d{2,3}(?:\s*(?:CE|BCE))?)\b", raw_text, re.IGNORECASE)
                            extracted_text = date_m.group(0) if date_m else raw_text
                        else:
                            extracted_text = raw_text

                start_conf = float(s_probs[best_start].item())
                end_conf = float(e_probs[best_end].item())
                span_conf = math.sqrt(max(1e-6, start_conf * end_conf))

            # Abstention Decision Policy:
            is_ans = (
                p_answerable >= self.answerability_threshold
                and best_span_score > (null_score + self.model.config.null_score_diff_threshold)
                and span_conf >= 0.05
                and extracted_text is not None
                and (len(q_content_words) == 0 or term_matches_count > 0)
            )

            combined_conf = float(round(0.6 * span_conf + 0.4 * p_answerable, 4))

            res = QAResult(
                answer=extracted_text if is_ans else None,
                answerable=is_ans,
                answer_confidence=combined_conf if is_ans else float(round(p_answerable, 4)),
                start_confidence=round(start_conf, 4),
                end_confidence=round(end_conf, 4),
                start_char=start_char if is_ans else None,
                end_char=end_char if is_ans else None,
                start_token=best_start if is_ans else None,
                end_token=best_end if is_ans else None,
                source_passage=passage,
                source_doc_id=doc_id,
                source_slug=slug,
                abstention_reason=None if is_ans else "NO EVIDENCE = NO ANSWER",
                trace={
                    "p_answerable": round(p_answerable, 4),
                    "null_score": round(null_score, 4),
                    "best_span_score": round(best_span_score, 4),
                    "start_prob": round(start_conf, 4),
                    "end_prob": round(end_conf, 4),
                    "span_confidence": round(span_conf, 4),
                    "features_count": len(features),
                    "cache_hit": False,
                }
            )

            # Window score prioritizes answerable spans, boosted by window question-term coverage
            window_score = (best_span_score + (4.0 * overlap_ratio)) if is_ans else (best_span_score - 100.0)
            if window_score > best_window_score:
                best_window_score = window_score
                best_window_result = res

        final_res = best_window_result or QAResult(
            answer=None,
            answerable=False,
            abstention_reason="NO EVIDENCE = NO ANSWER",
            source_passage=passage,
            source_doc_id=doc_id,
            source_slug=slug,
            trace={"cache_hit": False, "features_count": len(features)}
        )

        # Store in LRU cache
        self.cache.set("PESE-QA-0", question, passage, final_res)
        return final_res

    def read_candidate_passages(
        self,
        question: str,
        candidates: List[Dict[str, Any]]
    ) -> QAResult:
        """
        Evaluates top candidate passages from retrieval and selects the best answer.
        Combines retrieval evidence, passage quality, and QA answer confidence.
        Implements early exit when a high-confidence answer is found.
        """
        if not candidates:
            return QAResult(
                answer=None,
                answerable=False,
                abstention_reason="NO EVIDENCE = NO ANSWER (Zero candidate passages)"
            )

        # Prioritize passages that have positive passage score
        pos_candidates = [c for c in candidates if (c.get("passage_score") or 0.0) > 0.0]
        eval_candidates = pos_candidates if pos_candidates else candidates

        max_p_score = max((c.get("passage_score") or 1.0 for c in eval_candidates), default=1.0)
        max_r_score = max((c.get("final_score") or 1.0 for c in eval_candidates), default=1.0)

        best_result: Optional[QAResult] = None
        best_arbitration_score = -float("inf")

        windows_created_total = 0
        forward_passes_total = 0
        cache_hits_total = 0
        early_exit_triggered = False

        for cand_idx, cand in enumerate(eval_candidates):
            passage_text = cand.get("passage_text") or cand.get("text", "")
            doc_id = cand.get("doc_id")
            slug = cand.get("slug")
            retrieval_score = cand.get("final_score") or cand.get("score", 1.0)
            p_score = cand.get("passage_score") or 1.0
            spam_penalty = cand.get("spam_penalty", 0.0)

            # Skip passages from heavy spam documents
            if spam_penalty > 0.3:
                continue

            qa_res = self.read_passage(question, passage_text, doc_id=doc_id, slug=slug)

            # Work accounting
            is_cache_hit = qa_res.trace.get("cache_hit", False)
            if is_cache_hit:
                cache_hits_total += 1
            else:
                forward_passes_total += 1
            windows_created_total += qa_res.trace.get("features_count", 1)

            norm_p = p_score / max(1.0, max_p_score)
            norm_r = retrieval_score / max(1.0, max_r_score)

            # Combine retrieval score with QA confidence
            if qa_res.answerable:
                # Weighted arbitration score respecting retrieval evidence and answer confidence
                arbitration_score = (
                    0.45 * qa_res.answer_confidence
                    + 0.35 * norm_p
                    + 0.20 * norm_r
                )
            else:
                arbitration_score = -10.0 + (norm_p * 0.1)

            if arbitration_score > best_arbitration_score:
                best_arbitration_score = arbitration_score
                best_result = qa_res

            # Early Exit: If the primary passage produced a high-confidence answer, avoid scanning lower passages
            if qa_res.answerable and qa_res.answer_confidence >= 0.82 and norm_p >= 0.85:
                early_exit_triggered = True
                break

        res = best_result or QAResult(
            answer=None,
            answerable=False,
            abstention_reason="NO EVIDENCE = NO ANSWER (All candidates abstained)"
        )

        res.trace["windows_created"] = windows_created_total
        res.trace["forward_passes"] = forward_passes_total
        res.trace["cache_hits"] = cache_hits_total
        res.trace["early_exit"] = early_exit_triggered
        return res
