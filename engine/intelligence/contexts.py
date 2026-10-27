"""Bounded process-local presentation receipts. Never canonical or backed up."""
from collections import OrderedDict
from copy import deepcopy
from threading import RLock
from .evidence import digest


class SearchContexts:
    def __init__(self, capacity=64):
        self.capacity = capacity
        self._items = OrderedDict()
        self._learning = OrderedDict()
        self._lock = RLock()

    def remember(self, context_id, raw_query, results, learning=False):
        targets = {}
        evidence = {}
        for r in results:
            if not r.evidence_provenance:
                continue
            receipt = deepcopy(r.evidence_provenance)
            targets[("SERP_RESULT", r.doc_id)] = (receipt, r.rank, r.slug, r.base_score)
            if learning:
                evidence[("SERP_RESULT",r.doc_id)]={"receipt":receipt,"original_query":raw_query,
                    "evidence_text":r.learning_evidence_text,"rank":r.rank,"maae_score":r.base_score,
                    "neural_adjustment":r.neural_adjustment,"preference_adjustment":r.search_sync_adjustment,
                    "final_score":r.final_score,"model":r.trace.neural_model_version}
            if r.is_featured and r.featured_answer:
                fa = {**receipt, "target_type": "FEATURED_ANSWER", "evidence_id": r.slug + "#fa",
                      "evidence_hash": digest(r.featured_answer)}
                targets[("FEATURED_ANSWER", r.doc_id)] = (fa, r.rank, r.slug, r.base_score)
                if learning:evidence[("FEATURED_ANSWER",r.doc_id)]={**evidence[("SERP_RESULT",r.doc_id)],"receipt":fa,"evidence_text":r.featured_answer}
        with self._lock:
            self._items[context_id] = (raw_query, targets)
            if learning:self._learning[context_id]=deepcopy(evidence)
            self._items.move_to_end(context_id)
            while len(self._items) > self.capacity:
                expired,_=self._items.popitem(last=False)
                self._learning.pop(expired,None)

    def learning_target(self, submission):
        with self._lock:
            return deepcopy(self._learning.get(submission.search_context_id,{}).get((submission.target_type,submission.target_id)))

    def resolve(self, submission):
        with self._lock:
            context = self._items.get(submission.search_context_id)
            if context is None:
                return None  # legacy/expired remains unverified preference only
            raw_query, targets = context
            entry = targets.get((submission.target_type, submission.target_id.strip()))
            if raw_query != submission.query or entry is None:
                raise ValueError("Feedback does not match a displayed search target")
            receipt, rank, slug, base = entry
            if ((submission.rank_position is not None and submission.rank_position != rank)
                    or (submission.target_slug is not None and submission.target_slug != slug)):
                raise ValueError("Feedback rank/slug differs from displayed result")
            return deepcopy(receipt), base
