"""Bounded process-local presentation receipts. Never canonical or backed up."""
from collections import OrderedDict
from copy import deepcopy
from threading import RLock
from .evidence import digest


class SearchContexts:
    def __init__(self, capacity=64):
        self.capacity = capacity
        self._items = OrderedDict()
        self._lock = RLock()

    def remember(self, context_id, raw_query, results):
        targets = {}
        for r in results:
            if not r.evidence_provenance:
                continue
            receipt = deepcopy(r.evidence_provenance)
            targets[("SERP_RESULT", r.doc_id)] = (receipt, r.rank, r.slug, r.base_score)
            if r.is_featured and r.featured_answer:
                fa = {**receipt, "target_type": "FEATURED_ANSWER", "evidence_id": r.slug + "#fa",
                      "evidence_hash": digest(r.featured_answer)}
                targets[("FEATURED_ANSWER", r.doc_id)] = (fa, r.rank, r.slug, r.base_score)
        with self._lock:
            self._items[context_id] = (raw_query, targets)
            self._items.move_to_end(context_id)
            while len(self._items) > self.capacity:
                self._items.popitem(last=False)

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
