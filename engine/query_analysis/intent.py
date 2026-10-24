"""
PESE Query Analysis: Intent Classification
Deterministic lexical classification of search queries into intent categories:
WHEN, WHAT, WHY, HOW, WHO, WHERE, GENERAL.
"""

import re
from enum import Enum
from typing import Tuple, List


class QueryIntent(str, Enum):
    WHEN = "WHEN"
    WHAT = "WHAT"
    WHY = "WHY"
    HOW = "HOW"
    WHO = "WHO"
    WHERE = "WHERE"
    GENERAL = "GENERAL"


def classify_query_intent(normalized_tokens: List[str], raw_query: str) -> Tuple[QueryIntent, str]:
    """
    Classify query into an explicit intent category using transparent lexical patterns.
    Returns (QueryIntent, justification).
    """
    if not normalized_tokens:
        return QueryIntent.GENERAL, "Empty query defaulted to GENERAL"

    first_tok = normalized_tokens[0]
    q_lower = raw_query.lower().strip()

    target_tokens = normalized_tokens
    target_q = q_lower

    # If query begins with subordinate conjunction (when, after, before, if, while, once),
    # check if an embedded main question operator exists.
    prefix_sub = re.match(r'^(?:when|whenever|after|before|if|while|once|during|as)\s+.*?[,\-]\s*(.+)$', q_lower)
    if prefix_sub:
        rem = prefix_sub.group(1).strip()
        rem_toks = rem.split()
        if rem_toks and rem_toks[0] in ("what", "who", "where", "why", "how", "which", "does", "do", "did", "can", "is", "are", "should"):
            target_tokens = rem_toks
            first_tok = target_tokens[0]
            target_q = rem
    elif re.match(r'^(?:after|before|if|while|once|during)\b', q_lower):
        embedded = re.search(r'\b(what|who|where|why|how|which|does|do|did|can|could|is|are|was|were|should)\b.*$', q_lower)
        if embedded:
            target_q = embedded.group(0).strip()
            target_tokens = target_q.split()
            first_tok = target_tokens[0]

    # 1. WHO intent (entity / person inquiries)
    if first_tok in ("who", "whom", "whose"):
        return QueryIntent.WHO, "Detected person/entity inquiry (who)"

    # 2. WHERE intent (location inquiries)
    if first_tok in ("where", "wherever"):
        return QueryIntent.WHERE, "Detected location inquiry (where)"

    # 3. WHY intent (causal explanations)
    if first_tok in ("why", "wherefore"):
        return QueryIntent.WHY, "Detected causal explanation inquiry (why/reason)"

    # 4. HOW intent (procedural guidance)
    if first_tok in ("how",) or any(phrase in target_q for phrase in ["how to", "how do", "how does", "steps to", "guide to"]):
        return QueryIntent.HOW, "Detected procedural instruction inquiry (how/procedure)"

    # 5. WHAT procedural / action inquiry
    if target_q.startswith(("what should", "what must", "what do i do", "what is the first step")):
        return QueryIntent.HOW, "Detected procedural action inquiry (what should/procedure)"

    # 6. WHEN intent (genuine temporal inquiries)
    if first_tok in ("when", "whenever") or (first_tok in ("what", "which") and any(w in target_tokens[:2] for w in ["year", "date", "time", "month", "weekday"])) or any(w in normalized_tokens for w in ["date", "year", "month"]):
        return QueryIntent.WHEN, "Detected temporal inquiry (when/date/time)"

    # 7. WHAT intent (definitional or declarative inquiries)
    if first_tok in ("what", "whatever", "is", "are", "does", "do", "did", "can") or any(phrase in target_q for phrase in ["what is", "what are", "what cannot", "define", "definition"]):
        return QueryIntent.WHAT, "Detected definitional/declarative inquiry (what/definition)"

    # 8. Causal inquiry fallback
    if "reason" in target_tokens or "why" in target_tokens:
        return QueryIntent.WHY, "Detected causal explanation inquiry (why/reason)"

    # 9. Default to GENERAL (keyword topical queries)
    return QueryIntent.GENERAL, "Keyword/topical query without explicit question operator"
