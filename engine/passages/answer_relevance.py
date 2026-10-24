"""
PESE Passages: Answer Relevance & Evidence Entailment Gate
Phase 2D.2 — Generalized answer validation system.

Determines whether a candidate answer span satisfies the user's question by evaluating:
  - Interrogative contract compatibility (WHEN/WHO/WHERE/HOW MANY/DOES-IS-CAN/WHAT)
  - Predicate / relation alignment (what the user is asking ABOUT vs what the answer says)
  - Key property / attribute alignment
  - Negation preservation
  - Semantic support score
  - Yes/No question proposition validation

The gate produces a structured AnswerRelevanceResult with component scores
and a final binary PASS / REJECT decision. Zero hardcoded query rules.
"""

import re
from typing import Optional, List, Tuple

from pydantic import BaseModel, Field
from ..query_analysis.analyzer import AnalyzedQuery
from ..query_analysis.intent import QueryIntent
from ..nlp.stemmer import stem_word
from ..nlp.evidence import term_matches, sentences
from ..nlp.tokenizer import tokenize
from ..nlp.local_context import resolve_local_context


# ---------------------------------------------------------------------------
# Constants: scoring weights & thresholds
# ---------------------------------------------------------------------------

FINAL_ENTAILMENT_WEIGHTS = {
    "entity":    0.25,
    "predicate": 0.30,
    "property":  0.20,
    "ans_type":  0.15,
    "semantic":  0.10,
}

PASS_THRESHOLD   = 0.38
REJECT_THRESHOLD = 0.18

# Interrogative words that signal specific contracts
_WHEN_WORDS   = {"when", "whenever", "date", "year", "month"}
_WHO_WORDS    = {"who", "whom", "whose"}
_WHERE_WORDS  = {"where", "wherever"}
_HOW_MANY_WORDS = {"how many", "how much", "how often", "count", "number", "amount", "price", "cost", "quantity"}
_DOES_IS_CAN_STARTERS = {"does", "is", "are", "can", "has", "have", "was", "were", "do", "will", "would", "shall"}

# Temporal regex for WHEN contract
_TEMPORAL_RE = re.compile(
    r'\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}'
    r'|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}'
    r'|[1-9]\d{3}'
    r'|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}'
    r'|(?:January|February|March|April|May|June|July|August|September|October|November|December)'
    r'|(?:summer|spring|autumn|fall|winter)(?:\s+(?:19|20)\d{2})?'
    r')\b',
    re.IGNORECASE,
)

# HOW_MANY: numeric / monetary signals
_NUMERIC_RE = re.compile(
    r'\b(\d[\d,]*(?:\.\d+)?(?:\s*(?:million|billion|thousand|hundred|k|m|b|%))?\b'
    r'|\$[\d,]+(?:\.\d+)?'
    r'|£[\d,]+(?:\.\d+)?'
    r'|€[\d,]+(?:\.\d+)?)',
    re.IGNORECASE,
)

# Procedural signals for HOW_PROCEDURAL
_PROCEDURAL_SIGNALS = re.compile(
    r'\b(step|use|apply|install|by doing|by using|first|then|next|finally|configure|run|execute|follow)\b',
    re.IGNORECASE,
)

# Negation patterns
_NEGATION_RE = re.compile(
    r'\b(does not|do not|don\'t|doesn\'t|never|no longer|cannot|can\'t|not available|not offered|not provided'
    r'|without|excluded|lacking|unfortunately|did not|didn\'t|has not|haven\'t|have not|will not|won\'t'
    r'|not|unavailable|unsupported|no\b)\b',
    re.IGNORECASE,
)

# Yes/no evidence: supporting vs negating
_SUPPORT_SIGNALS = re.compile(
    r'\b(available|offered|accepted|yes|provide|provides|can|does|include|includes|installment|split|plan|option'
    r'|flexible|payment|pay|finance|financing|allow|allows|offer|offers|accept|accepts|supported|supports|booked|yes\b)\b',
    re.IGNORECASE,
)

# Location signals for WHERE
_LOCATION_SIGNALS = re.compile(
    r'\b(located|situated|in\s+[A-Z]|at\s+[A-Z]|near|bordered|coast|headquartered|based|found in)\b',
    re.IGNORECASE,
)

# Capitalized token heuristic for WHO (person/org names)
_CAPITALIZED_TOKEN_RE = re.compile(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b')

# Stopword-like intent words to strip during predicate extraction
_INTENT_REMOVE = {
    "what", "when", "who", "where", "why", "how", "which", "whose", "whom",
    "does", "do", "is", "are", "can", "has", "have", "was", "were", "will",
    "would", "shall", "did", "a", "an", "the", "my", "your", "his", "her",
    "their", "its", "our", "me", "it", "he", "she", "they", "we", "i",
    "of", "in", "at", "on", "to", "for", "from", "with", "by", "about",
    "into", "through", "during", "before", "after", "above", "below", "as",
    "between", "that", "this", "these", "those", "there", "here",
    "be", "been", "being", "having",
    "many", "much", "often", "long",
}

# Modifier words that should not alone count as core noun properties
_MODIFIER_WORDS = {
    "flexible", "easy", "good", "quick", "fast", "best", "new", "online",
    "private", "local", "different", "various", "multiple", "all"
}

# Semantic synonym expansions for common payment / schedule / attribute words
_SYNONYMS: dict[str, List[str]] = {
    "weight": ["weigh", "weighs", "weighed"],
    "payment":     ["pay", "paid", "fee", "charge", "cost", "invoice", "billing", "installment", "split"],
    "payments":    ["pay", "paid", "fee", "charge", "cost", "invoice", "billing", "installment", "split"],
    "flexible":    ["split", "installment", "instalment", "divide"],
    "installment": ["instalment", "split", "payment plan"],
    "installments": ["instalments", "split", "divide"],
    "split": ["divide", "installment", "instalment"],
    "available": ["unavailable"],
    "plans":       ["plan", "plans", "option", "options", "arrangement"],
    "specification": ["spec", "specification", "specifications", "component", "components", "detail", "breakdown", "feature", "groupset", "frame"],
    "specs":       ["spec", "specification", "specifications", "component", "components", "detail", "breakdown", "feature", "groupset", "frame"],
    "schedule":    ["schedule", "scheduling", "appointment", "booking", "slot"],
    "end":         ["until", "ended", "ends", "ending", "concluded", "conclusion", "terminated", "termination", "ceased", "through"],
    "start":       ["from", "started", "starts", "starting", "began", "begin", "beginning", "commenced", "since"],
    "begin":       ["from", "started", "starts", "starting", "began", "begin", "beginning", "commenced", "since"],
}

# Explicit verb / relation patterns (words that describe an ACTION or RELATION)
_VERB_SUFFIX_RE = re.compile(r'(ing|ed|tion|ment|ance|ence|ity|ness|ize|ise|ify)$', re.IGNORECASE)

_COMMON_VERBS = {
    "offer", "offers", "offered", "accept", "accepts", "accepted",
    "provide", "provides", "provided", "enter", "entered", "invade", "invaded",
    "annex", "annexed", "join", "joined", "found", "founded", "build", "built",
    "develop", "developed", "clean", "cleaned", "make", "made", "buy", "bought",
    "sell", "sold", "pay", "paid", "split", "surrender", "surrendered", "end", "ended",
    "promulgate", "promulgated", "occur", "occurs", "happen", "happens", "result", "results",
    "cause", "caused", "learn", "teach", "use", "used", "allow", "allows", "support", "supports",
    "dream", "dreamed", "launch", "launched", "open", "opened", "close", "closed",
    "reopen", "reopened", "adopt", "adopted", "weigh", "weighs", "weighed",
    "become", "became", "operate", "operates", "book", "booked", "execute", "executes",
    "hire", "hired", "invent", "invented", "begin", "began", "start", "started",
    "locate", "located", "store", "stores", "coordinate", "coordinates", "cost",
}

_COMMON_ATTRIBUTES = {
    "specification", "specifications", "spec", "specs", "payment", "payments",
    "price", "cost", "fee", "plan", "plans", "option", "options", "method", "methods",
    "language", "framework", "component", "components", "rule", "rules", "feature", "features",
    "reason", "reasons", "date", "year", "time", "definition", "schedule", "scheduling",
    "brakes", "frame", "weight", "capacity", "battery", "refund", "refunds", "revenue", "port",
}

_IRREGULAR_VERB_FORMS: dict[str, List[str]] = {
    "dream": ["dreamed", "dreamt"],
    "become": ["became", "becomes"],
    "begin": ["began", "begun", "beginning"],
    "invent": ["invented", "invention"],
    "buy": ["bought", "purchased", "purchase", "buys", "buying"],
    "bought": ["buy", "purchased", "purchase", "buys", "buying"],
    "sell": ["sold", "sells", "selling"],
    "sold": ["sell", "sells", "selling"],
    "build": ["built", "builds", "building"],
    "built": ["build", "builds", "building"],
    "pay": ["paid", "pays", "paying"],
    "paid": ["pay", "pays", "paying"],
    "find": ["found", "finds", "finding"],
    "found": ["find", "found", "founded", "finds"],
    "founded": ["found", "establish", "established", "create", "created"],
    "make": ["made", "makes", "making"],
    "made": ["make", "makes", "making"],
    "clean": ["clean", "cleaned", "cleans", "cleaning", "wash", "washed"],
    "enter": ["enter", "entered", "enters", "entering", "join", "joined"],
    "join": ["join", "joined", "joins", "joining"],
    "invade": ["invade", "invaded", "invades", "invading"],
    "annex": ["annex", "annexed", "annexes", "annexing"],
    "surrender": ["surrender", "surrendered", "surrenders"],
    "promulgate": ["promulgate", "promulgated", "promulgates", "enact", "enacted"],
}


# ---------------------------------------------------------------------------
# Result Model
# ---------------------------------------------------------------------------

class AnswerRelevanceResult(BaseModel):
    """Structured result from the Answer Relevance / Entailment Gate."""
    candidate:             str
    query:                 str
    passage_text:          str
    decision:              str                   # "PASS" | "REJECT" | "ABSTAIN"
    failure_class:         Optional[str] = None  # see spec
    entity_alignment:      float = 0.0
    predicate_alignment:   float = 0.0
    property_alignment:    float = 0.0
    answer_type_alignment: float = 0.0
    semantic_support:      float = 0.0
    negation_preserved:    bool  = True
    final_entailment:      float = 0.0
    reason:                str   = ""
    debug_lines:           List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

class AnswerRelevanceGate:
    """
    Phase 2D.2 Answer Relevance & Evidence Entailment Gate.

    Validates whether a candidate answer truly satisfies the user's question.
    Zero hardcoded query-specific rules.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def __init__(self, relation_matcher=None):
        self.relation_matcher = relation_matcher
        self._relation_budget = 4

    def _get_enclosing_context(self, candidate: str, passage_text: str, analyzed_query: AnalyzedQuery) -> str:
        """
        For extractive short spans (e.g. '1941', '17 March 2024', 'Python'),
        the evidence for predicate, property, and entity alignment comes from
        the sentence in the passage that contains the candidate span.

        For full-sentence candidates, the candidate itself is the context.
        """
        c_words = candidate.strip().split()
        if len(c_words) >= 6 or candidate.strip().endswith((".", "!", "?")):
            return candidate

        if not passage_text:
            return candidate

        passage_sentences = sentences(passage_text)
        c_lower = candidate.lower().strip()
        content_terms = [t.lower() for t in analyzed_query.effective_content_terms]

        matching_sents = []
        for s in passage_sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            if re.search(rf'\b{re.escape(c_lower)}\b', s_clean.lower()) or c_lower in s_clean.lower():
                matching_sents.append(s_clean)

        if len(matching_sents) == 1:
            return matching_sents[0]
        elif len(matching_sents) > 1:
            def _score_sent(st: str) -> float:
                st_low = st.lower()
                score = 0.0
                for ct in content_terms:
                    if re.search(rf'\b{re.escape(ct)}\b', st_low):
                        score += 2.0
                    elif stem_word(ct) and re.search(rf'\b{re.escape(stem_word(ct))}\w*', st_low):
                        score += 1.0
                return score
            matching_sents.sort(key=_score_sent, reverse=True)
            return matching_sents[0]

        return candidate

    def evaluate(
        self,
        query: str,
        candidate: str,
        passage_text: str,
        analyzed_query: AnalyzedQuery,
    ) -> AnswerRelevanceResult:
        """
        Evaluate whether *candidate* answers *query* as grounded in *passage_text*.

        Returns an AnswerRelevanceResult with a PASS / REJECT / ABSTAIN decision.
        """
        debug: List[str] = []
        q_lower    = query.lower().strip()
        cand_lower = candidate.lower().strip()
        pass_lower = passage_text.lower()

        # Context for evaluation: for extractive short spans, use enclosing sentence
        eval_context = self._get_enclosing_context(candidate, passage_text, analyzed_query)
        eval_context, evidence_window = resolve_local_context(eval_context, passage_text)
        debug.append(f"[eval_context]    {eval_context[:80]}")
        debug.append(f"[evidence_window] {evidence_window}")

        # 1. Interrogative contract
        contract = self._classify_interrogative_contract(analyzed_query)
        debug.append(f"[contract] {contract}")

        # 2. Extract semantic components (entity, predicate, property)
        entity_terms, predicate_terms, property_terms = self._extract_query_semantic_components(analyzed_query)
        debug.append(f"[entity_terms]    {entity_terms}")
        debug.append(f"[predicate_terms] {predicate_terms}")
        debug.append(f"[property_terms]  {property_terms}")

        # 3. Component scores: answer type is on candidate, relations on eval_context
        ans_type_score  = self._check_answer_type_alignment(candidate, contract)
        entity_score    = self._check_entity_alignment(eval_context, entity_terms)
        predicate_score = self._check_predicate_alignment(eval_context, predicate_terms)
        property_score  = self._check_property_alignment(eval_context, property_terms)
        neg_preserved   = self._check_negation_preserved(query, candidate, eval_context)
        semantic_score  = self._check_semantic_support(eval_context, passage_text, analyzed_query)

        relation_support = False
        # Embeddings may recover a predicate paraphrase. They cannot invent a
        # missing attribute, entity, polarity or an ungrounded answer.
        lexical_properties = all(self._matches(t, eval_context) for t in property_terms)
        lexical_entities = all(self._matches(t, eval_context) for t in entity_terms)
        if (self.relation_matcher and self._relation_budget > 0 and predicate_terms and
                predicate_score < 1.0 and lexical_properties and lexical_entities and
                not eval_context.rstrip().endswith("?") and not _NEGATION_RE.search(eval_context)):
            self._relation_budget -= 1
            similarity = self.relation_matcher.similarity(analyzed_query.effective_query, eval_context, entity_terms)
            debug.append(f"[relation_similarity] {similarity:.4f}")
            relation_support = similarity >= self.relation_matcher.threshold
            if relation_support:
                predicate_score = max(predicate_score, 0.85)
                semantic_score = max(semantic_score, similarity)

        debug.append(f"[ans_type_score]  {ans_type_score:.3f}")
        debug.append(f"[entity_score]    {entity_score:.3f}")
        debug.append(f"[predicate_score] {predicate_score:.3f}")
        debug.append(f"[property_score]  {property_score:.3f}")
        debug.append(f"[neg_preserved]   {neg_preserved}")
        debug.append(f"[semantic_score]  {semantic_score:.3f}")

        # 4. Yes/No proposition check (for DOES_IS_CAN contract)
        yesno_verdict: Optional[str] = None
        if contract == "DOES_IS_CAN":
            yesno_verdict = self._check_yesno_proposition(candidate, eval_context, property_terms)
            debug.append(f"[yesno_verdict]   {yesno_verdict}")
            # Boost property & predicate scores when strong yesno evidence found
            if yesno_verdict in ("YES", "NO"):
                property_score  = max(property_score, 0.65)
                predicate_score = max(predicate_score, 0.65)
                semantic_score  = max(semantic_score, 0.60)
            elif yesno_verdict is None and property_score < 0.10:
                # No evidence at all for the proposition
                pass

        # 5. Final entailment
        final_ent = (
            FINAL_ENTAILMENT_WEIGHTS["entity"]    * entity_score
            + FINAL_ENTAILMENT_WEIGHTS["predicate"] * predicate_score
            + FINAL_ENTAILMENT_WEIGHTS["property"]  * property_score
            + FINAL_ENTAILMENT_WEIGHTS["ans_type"]  * ans_type_score
            + FINAL_ENTAILMENT_WEIGHTS["semantic"]  * semantic_score
        )
        final_ent = round(min(1.0, max(0.0, final_ent)), 4)
        debug.append(f"[final_entailment] {final_ent:.4f}  (PASS>={PASS_THRESHOLD}, REJECT<{REJECT_THRESHOLD})")

        # 6. Failure class & decision
        failure_class, decision, reason = self._determine_decision(
            final_ent=final_ent,
            entity_score=entity_score,
            predicate_score=predicate_score,
            property_score=property_score,
            ans_type_score=ans_type_score,
            neg_preserved=neg_preserved,
            contract=contract,
            yesno_verdict=yesno_verdict,
            query=query,
            candidate=candidate,
        )
        # Mandatory constraints cannot be outweighed by unrelated topical overlap.
        # In particular WHEN/WHO/WHERE still require the requested object/attribute.
        missing_properties = [t for t in property_terms if not self._matches(t, eval_context)]
        missing_entities = [t for t in entity_terms if not self._matches(t, eval_context)]
        if missing_properties and decision == "PASS":
            failure_class, decision, reason = "PROPERTY_MISMATCH", "REJECT", f"Evidence lacks requested terms: {missing_properties}"
        if missing_entities:
            failure_class, decision, reason = "ENTITY_MISMATCH", "REJECT", f"Evidence lacks query entity: {missing_entities}"
        if candidate.strip().lower() not in passage_text.lower():
            failure_class, decision, reason = "UNGROUNDED_SPAN", "REJECT", "Candidate does not occur in source evidence"
        if candidate.rstrip().endswith("?"):
            failure_class, decision, reason = "QUESTION_WITHOUT_ANSWER", "REJECT", "Repeating a question is not answer evidence"
        if contract == "WHEN" and re.search(r"\b(?:not|never)\b", eval_context, re.I):
            failure_class, decision, reason = "NEGATED_EVENT", "REJECT", "Date belongs to a negated event"
        if contract in {"WHAT","WHO","WHERE","DOES_IS_CAN","HOW_PROCEDURAL"}:
            for predicate in predicate_terms:
                if predicate in _COMMON_ATTRIBUTES:
                    continue
                # Porter conflates verbs with nominal mentions (execute /
                # execution). Topic labels and roadmap nouns do not assert
                # that the queried entity performs the requested action.
                words=re.findall(r"\w+",eval_context.lower())
                verbal=any(self._matches(predicate,word) and not re.search(r"(?:tion|sion|ment|ness|ity|ance|ence)$",word) for word in words)
                if not verbal and not relation_support and not (contract=="DOES_IS_CAN" and yesno_verdict is not None):
                    failure_class,decision,reason="PREDICATE_MISMATCH","REJECT","Only a nominal/topic mention of the requested action; no asserted predicate"
        debug.append(f"[decision] {decision} — {failure_class or 'OK'}")

        return AnswerRelevanceResult(
            candidate=candidate,
            query=query,
            passage_text=passage_text,
            decision=decision,
            failure_class=failure_class,
            entity_alignment=round(entity_score, 4),
            predicate_alignment=round(predicate_score, 4),
            property_alignment=round(property_score, 4),
            answer_type_alignment=round(ans_type_score, 4),
            semantic_support=round(semantic_score, 4),
            negation_preserved=neg_preserved,
            final_entailment=final_ent,
            reason=reason,
            debug_lines=debug,
        )

    # ------------------------------------------------------------------
    # Interrogative contract classification
    # ------------------------------------------------------------------

    def _classify_interrogative_contract(self, analyzed_query: AnalyzedQuery) -> str:
        """
        Determine the interrogative contract type from the analyzed query.

        Returns one of: WHEN, WHO, WHERE, HOW_MANY, DOES_IS_CAN, WHAT,
        HOW_PROCEDURAL, GENERAL.
        """
        intent = analyzed_query.intent
        q_lower = analyzed_query.original_query.lower().strip()
        tokens  = [t.lower() for t in analyzed_query.raw_tokens]
        first   = tokens[0] if tokens else ""

        # WHEN
        if intent == QueryIntent.WHEN:
            return "WHEN"

        # WHO
        if intent == QueryIntent.WHO:
            return "WHO"

        # WHERE
        if intent == QueryIntent.WHERE:
            return "WHERE"

        # HOW_MANY / HOW_MUCH (subset of HOW intent, checked before HOW_PROCEDURAL)
        if intent == QueryIntent.HOW:
            if re.search(r'\bhow\s+(many|much|often|long)\b', q_lower):
                return "HOW_MANY"
            return "HOW_PROCEDURAL"

        # DOES_IS_CAN — yes/no contract
        if first in _DOES_IS_CAN_STARTERS:
            return "DOES_IS_CAN"

        # WHAT
        if intent == QueryIntent.WHAT:
            return "WHAT"

        # WHY / GENERAL
        return "GENERAL"

    # ------------------------------------------------------------------
    # Semantic Component Decomposition
    # ------------------------------------------------------------------

    def _extract_query_semantic_components(
        self, analyzed_query: AnalyzedQuery
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        Decomposes query content terms into (entity_terms, predicate_terms, property_terms).
        Ensures entity/subject tokens are cleanly separated from predicates and properties.
        Zero hardcoded query strings.
        """
        raw_tokens = tokenize(analyzed_query.effective_query)
        tokens = [t for t in raw_tokens if t not in _INTENT_REMOVE and len(t) > 1]
        if not tokens:
            return ([], [], [])

        # 1. Search for verb in tokens: check _COMMON_VERBS first!
        verb_idx = -1
        for idx, t in enumerate(tokens):
            if (t in _COMMON_VERBS or any(stem_word(t) == stem_word(v) for v in _COMMON_VERBS)) and (t not in _COMMON_ATTRIBUTES or t == "cost"):
                verb_idx = idx
                break

        # Fall back to suffix only if no exact common verb matched
        if verb_idx == -1:
            for idx, t in enumerate(tokens):
                if re.search(r'(ing|ed)$', t) and t not in _COMMON_ATTRIBUTES:
                    verb_idx = idx
                    break

        if verb_idx != -1:
            v_term = tokens[verb_idx]
            predicate_terms = [v_term]
            entity_terms = tokens[:verb_idx]
            property_terms = tokens[verb_idx + 1:]
            return (entity_terms, predicate_terms, property_terms)

        # 2. Search for attribute term
        attr_idx = -1
        for idx, t in enumerate(tokens):
            if t in _COMMON_ATTRIBUTES or t in ("spec", "specs"):
                attr_idx = idx
                break

        if attr_idx != -1:
            a_term = tokens[attr_idx]
            property_terms = [a_term]
            predicate_terms = [a_term]
            entity_terms = [t for i, t in enumerate(tokens) if i != attr_idx]
            return (entity_terms, predicate_terms, property_terms)

        # 3. Default: all content tokens are entity terms
        return (tokens, [], [])

    def _matches(self, term: str, text: str) -> bool:
        alternatives = [term] + _IRREGULAR_VERB_FORMS.get(term, []) + _SYNONYMS.get(term, [])
        for root, values in _SYNONYMS.items():
            if stem_word(term) == stem_word(root):
                alternatives.extend(values)
        return any(term_matches(t, text) for t in alternatives)

    def _extract_query_predicate_terms(self, analyzed_query: AnalyzedQuery) -> List[str]:
        _, preds, _ = self._extract_query_semantic_components(analyzed_query)
        return preds

    def _extract_query_property_terms(self, analyzed_query: AnalyzedQuery) -> List[str]:
        _, _, props = self._extract_query_semantic_components(analyzed_query)
        return props

    # ------------------------------------------------------------------
    # Answer type alignment
    # ------------------------------------------------------------------

    def _check_answer_type_alignment(self, candidate: str, contract: str) -> float:
        """
        Check whether the candidate's surface form matches the expected answer type
        for the interrogative contract.
        """
        c_low = candidate.lower()

        if contract == "WHEN":
            if _TEMPORAL_RE.search(candidate):
                return 1.0
            # Partial credit for temporal-ish words
            if re.search(r'\b(decade|century|era|period|age)\b', c_low, re.IGNORECASE):
                return 0.50
            return 0.05

        elif contract == "WHO":
            if _CAPITALIZED_TOKEN_RE.search(candidate):
                return 1.0
            if re.search(r'\b(he|she|they|the\s+\w+)\b', c_low):
                return 0.40
            return 0.10

        elif contract == "WHERE":
            if _LOCATION_SIGNALS.search(candidate):
                return 1.0
            if _CAPITALIZED_TOKEN_RE.search(candidate):
                return 0.55
            return 0.10

        elif contract == "HOW_MANY":
            if _NUMERIC_RE.search(candidate):
                return 1.0
            return 0.05

        elif contract == "DOES_IS_CAN":
            c_stripped = c_low.strip()
            if c_stripped in ("yes", "no", "yes.", "no."):
                return 1.0
            # Candidate that contains a full proposition (sentence-length)
            if len(candidate.split()) >= 3:
                return 0.65
            return 0.30

        elif contract == "HOW_PROCEDURAL":
            if _PROCEDURAL_SIGNALS.search(candidate):
                return 1.0
            return 0.35

        elif contract == "WHAT":
            # Definitional candidates should be sentence-like
            if len(candidate.split()) >= 5:
                return 0.80
            return 0.40

        # GENERAL
        return 0.60

    # ------------------------------------------------------------------
    # Entity alignment
    # ------------------------------------------------------------------

    def _check_entity_alignment(
        self, candidate: str, entity_terms: List[str], passage_text: str = ""
    ) -> float:
        """
        Check whether the candidate or its passage context is grounded in the query's entity context.
        """
        if not entity_terms:
            return 0.50
        return sum(self._matches(t, candidate) for t in entity_terms) / len(entity_terms)

    # ------------------------------------------------------------------
    # Predicate alignment
    # ------------------------------------------------------------------

    def _check_predicate_alignment(self, candidate: str, predicate_terms: List[str]) -> float:
        """
        Check whether the candidate includes words relating to the query's predicate
        (the action / relation being asked about).
        """
        if not predicate_terms:
            return 0.50  # nothing to align against

        return sum(self._matches(t, candidate) for t in predicate_terms) / len(predicate_terms)

    # ------------------------------------------------------------------
    # Property alignment
    # ------------------------------------------------------------------

    def _check_property_alignment(self, candidate: str, property_terms: List[str]) -> float:
        """
        Check whether the candidate contains the requested attribute / property terms.
        Uses stem matching and semantic synonym expansion for common paraphrases.
        """
        if not property_terms:
            return 0.50

        return sum(self._matches(t, candidate) for t in property_terms) / len(property_terms)

    # ------------------------------------------------------------------
    # Negation preservation
    # ------------------------------------------------------------------

    def _check_negation_preserved(
        self, query: str, candidate: str, passage_text: str
    ) -> bool:
        """
        Returns True if negation is handled correctly.

        Checks: if a negation word appears NEAR the property terms in the passage,
        does the candidate also contain that negation word?

        If negation is in passage near property but NOT in candidate → False (bad strip).
        """
        pass_low = passage_text.lower()
        cand_low = candidate.lower()

        # Find negation locations in passage
        neg_spans = [(m.start(), m.end()) for m in _NEGATION_RE.finditer(pass_low)]
        if not neg_spans:
            return True  # No negation in passage; nothing to violate

        # Does the candidate contain any negation at all?
        cand_has_neg = bool(_NEGATION_RE.search(cand_low))

        # Check if candidate text appears to come from the passage (substring or high overlap)
        cand_in_passage = (
            cand_low in pass_low
            or any(
                word in pass_low
                for word in cand_low.split()
                if len(word) > 4
            )
        )

        if not cand_in_passage:
            # Candidate is synthetic / paraphrase → allow without negation
            return True

        # Candidate is a passage excerpt: if passage has negation near candidate words
        # and candidate strips it, that's a conflict.
        cand_words = [w for w in cand_low.split() if len(w) > 3]
        for word in cand_words:
            for m in re.finditer(rf'\b{re.escape(word)}\b', pass_low):
                word_pos = m.start()
                # Check if any negation is within 60 chars of this word in the passage
                for neg_s, neg_e in neg_spans:
                    if abs(word_pos - neg_s) < 60:
                        # Negation is near this candidate word in the passage
                        if not cand_has_neg:
                            return False  # Negation was stripped!

        return True

    # ------------------------------------------------------------------
    # Semantic support
    # ------------------------------------------------------------------

    def _check_semantic_support(
        self, candidate: str, passage_text: str, analyzed_query: AnalyzedQuery
    ) -> float:
        """
        Lightweight semantic support score:
        measures content-term overlap between candidate and passage,
        weighted by query content terms.
        """
        content = [t.lower() for t in analyzed_query.effective_content_terms]
        if not content:
            return 0.50

        pass_low  = passage_text.lower()
        cand_low  = candidate.lower()

        # How many query content terms appear in BOTH the passage AND the candidate?
        in_passage   = 0
        in_candidate = 0
        for t in content:
            stem = stem_word(t)
            p_has = bool(re.search(rf'\b{re.escape(t)}\b', pass_low)) or (
                stem and len(stem) >= 3 and bool(re.search(rf'\b{re.escape(stem)}\w*', pass_low))
            )
            c_has = bool(re.search(rf'\b{re.escape(t)}\b', cand_low)) or (
                stem and len(stem) >= 3 and bool(re.search(rf'\b{re.escape(stem)}\w*', cand_low))
            )
            if p_has:
                in_passage += 1
            if c_has:
                in_candidate += 1

        if in_passage == 0:
            return 0.0

        # Candidate overlap fraction relative to passage support
        return min(1.0, in_candidate / max(1, in_passage) * 0.85 + 0.10)

    # ------------------------------------------------------------------
    # Yes/No proposition validation
    # ------------------------------------------------------------------

    def _check_yesno_proposition(
        self,
        candidate: str,
        passage_text: str,
        property_terms: List[str],
    ) -> Optional[str]:
        """
        For DOES_IS_CAN queries: determine whether the passage contains evidence
        FOR or AGAINST the proposition being asked about.

        Returns "YES", "NO", or None (no evidence found).
        """
        pass_low  = passage_text.lower()
        cand_low  = candidate.lower()
        prop_terms = property_terms

        if not prop_terms:
            return None

        # Split passage into sentences for targeted evidence search
        sentences = re.split(r'(?<=[.!?])\s+|\n+', passage_text)

        support_score  = 0
        negation_score = 0

        core_terms = [t for t in prop_terms if t not in _MODIFIER_WORDS]
        check_terms = core_terms if core_terms else prop_terms

        for sent in sentences:
            sent_low = sent.lower()
            # Does this sentence contain any core property term or synonym?
            contains_prop = False
            for t in check_terms:
                if re.search(rf'\b{re.escape(t)}\b', sent_low):
                    contains_prop = True
                    break
                stem = stem_word(t)
                if stem and len(stem) >= 3 and re.search(rf'\b{re.escape(stem)}\w*', sent_low):
                    contains_prop = True
                    break
                for syn in _SYNONYMS.get(t, []):
                    if re.search(rf'\b{re.escape(syn)}\b', sent_low):
                        contains_prop = True
                        break
                if contains_prop:
                    break

            if not contains_prop:
                continue

            has_support  = bool(_SUPPORT_SIGNALS.search(sent))
            has_negation = bool(_NEGATION_RE.search(sent))

            if has_negation:
                negation_score += 2
            if has_support and not has_negation:
                support_score  += 2
            elif has_support and has_negation:
                # Both present → negation likely modifies the support signal
                negation_score += 1

        if negation_score > support_score and negation_score >= 2:
            return "NO"
        elif support_score > 0:
            return "YES"
        else:
            return None

    # ------------------------------------------------------------------
    # Decision logic
    # ------------------------------------------------------------------

    def _determine_decision(
        self,
        final_ent: float,
        entity_score: float,
        predicate_score: float,
        property_score: float,
        ans_type_score: float,
        neg_preserved: bool,
        contract: str,
        yesno_verdict: Optional[str],
        query: str,
        candidate: str,
    ) -> Tuple[Optional[str], str, str]:
        """
        Apply failure-class rules and thresholds to produce a decision.

        Returns (failure_class, decision, reason).
        """
        strict_contracts = {"WHEN", "WHO", "WHERE", "HOW_MANY"}

        # Negation conflict trumps everything
        if not neg_preserved:
            return (
                "NEGATION_CONFLICT",
                "REJECT",
                "Candidate strips negation that was present in the passage near property terms.",
            )

        # Answer type mismatch for strict contracts
        if contract in strict_contracts and ans_type_score < 0.15:
            return (
                "ANSWER_TYPE_MISMATCH",
                "REJECT",
                f"Candidate type does not match expected answer type for {contract} query "
                f"(ans_type_score={ans_type_score:.3f}).",
            )

        # Predicate mismatch: answer says nothing about what was asked
        if predicate_score < 0.05:
            return (
                "PREDICATE_MISMATCH",
                "REJECT",
                f"Candidate does not mention any predicate / relation words from the query "
                f"(predicate_score={predicate_score:.3f}).",
            )

        # Property / Attribute mismatch
        if property_score < 0.05 and contract not in ("GENERAL", "WHEN", "WHO", "WHERE"):
            return (
                "PREDICATE_MISMATCH",
                "REJECT",
                f"Candidate does not mention the requested attribute / property terms "
                f"(property_score={property_score:.3f}).",
            )

        # Yes/No queries with no evidence → abstain or no_answer_evidence
        if contract == "DOES_IS_CAN" and yesno_verdict is None:
            return (
                "NO_ANSWER_EVIDENCE",
                "REJECT",
                "Yes/No query: passage contains neither supporting nor negating evidence for the proposition.",
            )

        # Entity mismatch
        if entity_score < 0.10:
            return (
                "ENTITY_MISMATCH",
                "REJECT",
                f"Candidate does not mention query entity terms (entity_score={entity_score:.3f}).",
            )

        # Hard reject below minimum threshold
        if final_ent < REJECT_THRESHOLD:
            return (
                "TOPIC_WITHOUT_EVIDENCE",
                "REJECT",
                f"Final entailment score {final_ent:.4f} is below reject threshold {REJECT_THRESHOLD}.",
            )

        # Low confidence → abstain
        if final_ent < PASS_THRESHOLD:
            return (
                "LOW_CONFIDENCE",
                "ABSTAIN",
                f"Final entailment score {final_ent:.4f} is below pass threshold {PASS_THRESHOLD}; abstaining.",
            )

        # PASS
        return (
            None,
            "PASS",
            f"Candidate satisfies the {contract} interrogative contract "
            f"(entailment={final_ent:.4f}).",
        )
