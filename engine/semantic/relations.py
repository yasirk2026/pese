"""Bounded relation comparison using the existing local embedding provider.

This is a similarity aid, not an entailment model. Entity, attribute, grounding,
negation and answer-type checks remain mandatory in the caller.
"""
from functools import lru_cache
import re
import numpy as np


class RelationMatcher:
    threshold = 0.84

    def __init__(self, provider):
        self.provider = provider

    @lru_cache(maxsize=256)
    def _embedding(self, text):
        return self.provider.embed_query(text)

    def similarity(self, query, sentence, entities):
        # Compare relations rather than letting a shared proper name dominate.
        for entity in entities:
            query = re.sub(rf"\b{re.escape(entity)}\b", "", query, flags=re.I)
            sentence = re.sub(rf"\b{re.escape(entity)}\b", "", sentence, flags=re.I)
        query = re.sub(r"\b(?:what|when|where|who|does|did|can|is|was|the|a|my|i)\b", "", query, flags=re.I)
        query, sentence = " ".join(query.split()), " ".join(sentence.split())
        if len(query.split()) < 2 or not sentence:
            return 0.0
        a, b = self._embedding(query), self._embedding(sentence)
        return float(np.dot(a, b) / max(1e-9, np.linalg.norm(a)*np.linalg.norm(b)))
