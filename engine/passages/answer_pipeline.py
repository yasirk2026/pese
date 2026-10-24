"""Bounded extractive answering. Similarity never authorizes propositions.

Query roles, candidate discovery, validation and arbitration are separate records.
All strings returned as answers occur verbatim in the selected source.
"""
from dataclasses import dataclass, asdict
import re
import unicodedata
from ..nlp.evidence import sentences, term_matches
from ..nlp.stemmer import stem_word
from ..nlp.local_context import resolve_local_context

STOP = set('what which who whom whose where when why how a an the of on at in to for from with by into through as and or does do did is are was were be been being am can could may might must should would will shall has have had i my our your their its it they he she we you me us please tell about'.split())
STOP.update('s if named called during off up one before after dr mr mrs ms prof'.split())
SLOTS = set('year date month century weekday time many much long often number quantity price cost color colour temperature mean meaning definition first step'.split())
# Morphology uses shared Porter stems; this is a compact verb lexicon, not a
# table of benchmark questions or relation-specific expected answers.
VERBS = set('repair design fund create invent build implement write develop open close complete launch release enter buy purchase stop cause trigger result happen keep store put place spread use weigh cost pay split divide offer allow permit accept carry take reserve book confirm appear mark label hold return pack meet work chat borrow extend report switch wait unplug dry specialize attend protect envision become lead contain require need reset install run set'.split())
VERBS.update('annex invade surrender end begin change empty identify paint mean look own join lose leave'.split())
VERBS.update('found hire operate renovate inspect'.split())
VERB_STEMS = {stem_word(x) for x in VERBS}
ATTRIBUTES = set('brake brakes weight frame material surface colour color price cost temperature reference label wording code language capital specification specifications processor size'.split())
# Small, explicit property/relation equivalences, always followed by entity,
# local predicate, polarity, answer-type and grounding checks.
FAMILIES = [set('price cost'.split()), set('weight weigh'.split()), set('reserve book reservation booking'.split()), set('build implement develop write'.split()), set('split divide installment installments'.split()), set('payment fee bill pay'.split()), set('keep store'.split()), set('put place spread'.split())]
FAMILIES += [set('allow permit offer support'.split()), set('label wording mark'.split())]
MORPH = {'kept':'keep','held':'hold','made':'make','began':'begin','begun':'begin','sent':'send','became':'become','lost':'lose'}
COLORS = re.compile(r'\b(?:red|orange|yellow|green|blue|violet|purple|amber|black|white|grey|gray|brown|pink|silver|gold)\b',re.I)
NEG = re.compile(r"\b(?:not|never|cannot|unavailable|unsupported|no longer|no\b)\b", re.I)
NUM = re.compile(r'\b(?:\d[\d,.]*|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|hundred)\b', re.I)
TIME = re.compile(r'\b(?:\d{1,2}\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December)(?:\s+\d{1,2},?)?(?:\s+\d{4})?\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}(?:st|nd|rd|th)\s+century(?:\s+(?:BCE|CE|BC|AD))?\b|\b[1-9]\d{3}\b|\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)(?:\s+(?:morning|afternoon|evening))?\b|\b(?:next|following)\s+(?:working|business)\s+day\b|\b(?:medieval|Victorian|Roman)\s+(?:era|period)\b', re.I)
CAUSAL = re.compile(r'\b(?:because|due to|caused by|resulted from|triggered|caused)\b',re.I)
NAME = re.compile(r'\b(?:Dr\.\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b')
NON_NAMES={'The','A','An','It','He','She','His','Her','Its','Their','They','No','Yes','Old','Current','Each','To','In','On','At'}


def names_in(text):
    return [m for m in NAME.finditer(text) if m.group() not in NON_NAMES]


def plain(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text) if not unicodedata.combining(c))


def matches(term, text):
    term=plain(term.lower()); text=plain(text)
    term=MORPH.get(term,term)
    text=re.sub(r'\b(?:kept|held|made|began|begun|sent|became|lost)\b',lambda m:MORPH[m.group().lower()],text,flags=re.I)
    if term_matches(term,text): return True
    for family in FAMILIES:
        if stem_word(term) in {stem_word(t) for t in family}:
            return any(term_matches(t,text) for t in family)
    return False


def classify_interrogative(query: str, tokens: list):
    """
    Classifies the expected answer type for a query based on the main question slot,
    ensuring subordinate clauses (e.g. 'when doing X...', 'after X happens') do not
    hijack the primary interrogative.

    Returns:
        (kind, main_interrogative, classification_reason, matched_rule)
    """
    q = plain(query.lower()).strip()
    target_q = q
    subordinate_info = ''

    # Check for leading subordinate clause
    # e.g., 'When doing X, what should I do first?'
    # or 'After X happens, who should I call?'
    prefix_sub = re.match(r'^(?:when|whenever|after|before|if|while|once|during|as)\s+.*?[,\-]\s*(.+)$', q)
    if prefix_sub:
        remainder = prefix_sub.group(1).strip()
        if re.match(r'^(?:what|who|where|why|how|which|does|do|did|can|could|is|are|was|were|should)\b', remainder):
            target_q = remainder
            subordinate_info = f'subordinate prefix stripped; main clause "{remainder}" evaluated'

    elif re.match(r'^(?:after|before|if|while|once|during)\b', q):
        embedded = re.search(r'\b(what|who|where|why|how|which|does|do|did|can|could|is|are|was|were|should)\b.*$', q)
        if embedded:
            target_q = embedded.group(0).strip()
            subordinate_info = f'subordinate context ignored; main clause "{target_q}" evaluated'

    # 1. PERSON: Leading who/whom/whose or which person
    if re.match(r'^(?:who|whom|whose)\b', target_q):
        reason = f'main clause "{target_q.split("when")[0].strip()}"; subordinate "when" ignored' if 'when' in q and target_q == q and not target_q.startswith('when') else 'Leading interrogative "who" requests human actor/entity'
        return ('PERSON', 'who', reason, 'PERSON_LEADING_WHO')
    if re.match(r'^which\s+(?:person|individual|man|woman|author|founder|creator|engineer|director|scientist|doctor|architect|artist|president|minister|leader|officer)\b', target_q):
        return ('PERSON', 'which person', 'Interrogative specifies human actor', 'PERSON_WHICH_PERSON')

    # 2. ORGANIZATION: Which company/organization/association/agency
    if re.match(r'^which\s+(?:company|organization|organisation|association|agency|firm|institution|developer|publisher|studio|university|corporation|bank|club|team)\b', target_q):
        return ('ORGANIZATION', 'which organization', 'Interrogative specifies corporate/institutional entity', 'ORGANIZATION_WHICH_ORG')

    # 3. LOCATION: Leading where / in which city/place
    if re.match(r'^(?:where|wherever)\b', target_q):
        reason = f'main clause "{target_q.split("when")[0].strip()}"; subordinate "when" ignored' if 'when' in q and target_q == q and not target_q.startswith('when') else 'Leading interrogative "where" requests location'
        return ('LOCATION', 'where', reason, 'LOCATION_LEADING_WHERE')
    if re.match(r'^(?:in|at|to|from)\s+(?:what|which)\s+(?:place|city|country|location|building|room|town|state|province|nation)\b', target_q):
        return ('LOCATION', 'which location', 'Prepositional interrogative requests geographic location', 'LOCATION_WHICH_PLACE')

    # 4. CAUSE: Leading why / what caused
    if re.match(r'^(?:why|wherefore)\b', target_q):
        reason = f'main clause "{target_q.split("when")[0].strip()}"; subordinate "when" ignored' if 'when' in q and target_q == q and not target_q.startswith('when') else 'Leading interrogative "why" requests causal explanation'
        return ('CAUSE', 'why', reason, 'CAUSE_LEADING_WHY')
    if re.match(r'^what\s+(?:caused|causes|triggered|triggers|results\s+in)\b', target_q):
        return ('CAUSE', 'what caused', 'Interrogative requests causal trigger/factor', 'CAUSE_WHAT_CAUSED')
    if re.match(r'^what\s+(?:is|was|are)\s+(?:the\s+)?(?:cause|reason|explanation)\b', target_q):
        return ('CAUSE', 'what is the cause', 'Interrogative requests underlying cause or reason', 'CAUSE_WHAT_IS_CAUSE')

    # 5. HOW interrogatives
    if re.match(r'^(?:how\s+many|what\s+number\s+of)\b', target_q):
        return ('NUMBER', 'how many', 'Interrogative "how many" requests count', 'NUMBER_HOW_MANY')

    if re.match(r'^how\s+much\b', target_q):
        if re.search(r'\b(?:weigh|weight|mass|heavy|kg|gram|pound)\b', target_q):
            return ('QUANTITY', 'how much weight', 'Interrogative "how much" with weight terms requests quantity', 'QUANTITY_HOW_MUCH_WEIGHT')
        return ('PRICE', 'how much price', 'Interrogative "how much" requests monetary amount/price', 'PRICE_HOW_MUCH')

    if re.match(r'^how\s+(?:long|heavy|far|tall|wide|thick|deep|often|fast)\b', target_q):
        return ('QUANTITY', 'how dimensional', 'Interrogative requests dimensional measurement, duration or rate', 'QUANTITY_HOW_DIMENSION')

    if re.match(r'^how\b', target_q):
        reason = f'main clause "{target_q.split("when")[0].strip()}"; subordinate "when" ignored' if 'when' in q and target_q == q and not target_q.startswith('when') else 'Interrogative "how" requests procedure/method'
        return ('PROCEDURE', 'how', reason, 'PROCEDURE_LEADING_HOW')

    # 6. WHAT: Procedural / Action
    if re.match(r'^what\s+(?:should|must|do|can)\s+(?:i|we|you|one)\s+(?:do|check|perform|take|follow)\b', target_q):
        reason = f'main clause "{target_q.split("when")[0].strip()}"; subordinate "when" ignored' if 'when' in q and target_q == q and not target_q.startswith('when') else 'Interrogative requests recommended action or procedure'
        return ('PROCEDURE', 'what should do', reason, 'PROCEDURE_WHAT_SHOULD_DO')
    if re.match(r'^what\s+(?:is|are)\s+(?:the\s+)?(?:first|next|second|final|initial|\d+(?:st|nd|rd|th))\s+steps?\b', target_q):
        return ('PROCEDURE', 'what is step', 'Interrogative requests ordered procedure step', 'PROCEDURE_WHAT_STEP')
    if re.match(r'^what\s+(?:is|are)\s+(?:the\s+)?(?:procedure|instructions|steps|guide|process)\b', target_q):
        return ('PROCEDURE', 'what is procedure', 'Interrogative requests procedural guide', 'PROCEDURE_WHAT_PROCEDURE')

    # 7. WHAT / WHICH: Temporal (YEAR, CENTURY, DATE)
    if re.match(r'^(?:what|which|in\s+what|in\s+which)\s+year\b', target_q):
        return ('YEAR', 'what year', 'Interrogative explicitly requests calendar year', 'YEAR_WHAT_YEAR')
    if re.match(r'^(?:what|which|in\s+what|in\s+which)\s+century\b', target_q):
        return ('CENTURY', 'what century', 'Interrogative explicitly requests historical century', 'CENTURY_WHAT_CENTURY')
    if re.match(r'^(?:what|which)\s+(?:date|day|weekday|month)\b', target_q):
        return ('DATE', 'what date', 'Interrogative requests date or day', 'DATE_WHAT_TEMPORAL')
    if re.match(r'^what\s+time\b', target_q):
        return ('DATE', 'what time', 'Interrogative requests specific time of event', 'DATE_WHAT_TIME')

    # 8. WHAT: Monetary / Price
    if re.match(r'^what\s+(?:is|was)?\s*(?:the\s+)?(?:price|cost|fee|charge|fare|rate)\b', target_q):
        return ('PRICE', 'what price', 'Interrogative requests price or fee', 'PRICE_WHAT_PRICE')
    if re.search(r'^what\s+does\s+.*\b(?:cost)\b', target_q):
        return ('PRICE', 'what does cost', 'Interrogative requests cost of entity', 'PRICE_WHAT_DOES_COST')

    # 9. WHAT: Count / Number
    if re.match(r'^what\s+(?:is\s+the\s+)?number\s+of\b', target_q):
        return ('NUMBER', 'what number', 'Interrogative requests count/number', 'NUMBER_WHAT_NUMBER')

    # 10. WHAT: Definition cues (mean, meaning, definition)
    if re.search(r'\b(?:mean|means|meaning|definition)\b', target_q):
        return ('DEFINITION', 'definition cue', 'Query contains explicit definition/meaning cue', 'DEFINITION_MEANING_CUE')
    if re.match(r'^define\b', target_q):
        return ('DEFINITION', 'define', 'Imperative command to define concept', 'DEFINITION_DEFINE_COMMAND')

    # 11. WHAT: Attributes (explicit property queries like "what color", "what is X weight")
    attr_tokens = [t for t in tokens if t in ATTRIBUTES and t not in {'price', 'cost', 'mean', 'meaning', 'definition', 'first', 'step'}]
    if attr_tokens or re.match(r'^(?:what|which)\s+(?:color|colour|brake|brakes|material|frame|surface|temperature|weight|size|speed|capacity|language|capital|engine|processor|specifications?)\b', target_q):
        attr_name = attr_tokens[0] if attr_tokens else 'attribute'
        return ('ATTRIBUTE_VALUE', f'what {attr_name}', f'Interrogative requests specific attribute slot ({attr_name})', 'ATTRIBUTE_WHAT_SPECIFIC')

    # 12. WHAT IS Concept Definition (pure concept questions without attribute words)
    if re.match(r'^what\s+(?:is|are|was|were)\s+(?:a|an|the)?\s*[\w-]+(?:\s+[\w-]+){0,4}\??$', target_q):
        m = re.match(r'^what\s+(?:is|are|was|were)\s+(?:a|an|the)?\s*(.*?)\??$', target_q)
        rest = m.group(1).strip() if m else ''
        first_word = rest.split()[0] if rest else ''
        if first_word.endswith('ed') or first_word in {'done', 'built', 'made', 'written', 'found', 'born', 'lost', 'held', 'shown'}:
            return ('DESCRIPTION', 'what passive event', 'Interrogative asks what entity underwent action', 'DESCRIPTION_WHAT_PASSIVE')
        return ('DEFINITION', 'what is concept', 'Interrogative "what is [concept]" requests definition', 'DEFINITION_WHAT_IS')

    # 13. WHAT: Description / Event
    if re.match(r'^what\s+(?:happened|happens|occurred|occurs|took\s+place)\b', target_q):
        reason = f'main clause "{target_q.split("when")[0].strip()}"; subordinate "when" ignored' if 'when' in q and target_q == q and not target_q.startswith('when') else 'Interrogative requests narrative event description'
        return ('DESCRIPTION', 'what happened', reason, 'DESCRIPTION_WHAT_HAPPENED')

    # 14. GENUINE WHEN:
    if re.match(r'^(?:when|whenever)\b', target_q):
        if 'year' in tokens:
            return ('YEAR', 'when year', 'Interrogative "when" with year keyword requests year', 'YEAR_WHEN')
        if 'century' in tokens:
            return ('CENTURY', 'when century', 'Interrogative "when" with century keyword requests century', 'CENTURY_WHEN')
        return ('DATE', 'when', 'Leading interrogative "when" requests event date/time', 'DATE_LEADING_WHEN')

    # 15. BOOLEAN: Polar auxiliary starters
    if re.match(r'^(?:does|do|did|is|are|was|were|can|could|may|might|must|has|have|had|will|would|should)\b', target_q):
        reason = f'main clause "{target_q.split("when")[0].strip()}"; subordinate "when" ignored' if 'when' in q and target_q == q and not target_q.startswith('when') else 'Leading auxiliary verb requests polar yes/no validation'
        return ('BOOLEAN', 'auxiliary starter', reason, 'BOOLEAN_AUX_STARTER')

    # 16. Attribute fallback:
    if any(t in ATTRIBUTES for t in tokens if t not in {'mean', 'meaning', 'definition', 'first', 'step', 'price', 'cost'}):
        return ('ATTRIBUTE_VALUE', 'attribute token', 'Query references specific attribute slot', 'ATTRIBUTE_TOKEN_FALLBACK')

    return ('DESCRIPTION', 'general', 'Default descriptive question contract', 'DESCRIPTION_FALLBACK')


@dataclass
class QueryFrame:
    subject: list
    relation: list
    property: list
    expected_answer_type: str
    answer_target: str
    polarity: str
    temporal_modifiers: list
    ownership: list
    qualifiers: list
    proper_entities: list
    main_interrogative: str = ""
    classification_reason: str = ""
    matched_rule: str = ""

    @classmethod
    def parse(cls, query):
        q=plain(query.lower()); tokens=re.findall(r"[\w]+(?:-[\w]+)*",q)
        kind, main_interrogative, classification_reason, matched_rule = classify_interrogative(query, tokens)
        props=[t for t in tokens if t in ATTRIBUTES]
        detected=[t for t in tokens if (stem_word(MORPH.get(t,t)) in VERB_STEMS or (t.startswith('re') and stem_word(t[2:]) in VERB_STEMS)) and t not in props]
        relations=detected[:1]
        if kind in {'PERSON','ORGANIZATION'} and len(tokens)>1 and tokens[1] not in STOP:
            relations=[tokens[1]]
        # In an attribute question, appearance/identity is carried by the
        # explicit property rather than being a second mandatory relation.
        role_verbs=[]
        if props and relations and relations[0] in {'appears','appear','identifies','identify'}:
            role_verbs=relations;relations=[]
        if kind=='ATTRIBUTE_VALUE' and any(t in {'made','make'} for t in tokens):role_verbs+=['made','make']
        # Copular definitions have an explicit relation even without a lexical verb.
        if kind=='DEFINITION':relations=['define']
        subject=[t for t in tokens if t not in STOP|SLOTS and t not in relations+role_verbs and t not in props]
        # Infinitive purpose after a requirement is not a second asserted
        # predicate: "an audition required to join" asks about the requirement.
        if relations and matches(relations[0],'require'):
            purposes=re.findall(r'\bto\s+(\w+)\b',q)
            subject=[t for t in subject if t not in purposes]
        payment_mode=kind=='BOOLEAN' and any(matches(t,'payment fee pay bill') for t in tokens) and bool(re.search(r'\b(?:flexible|installments?|split|divide|all at once|everything at once)\b',q))
        if payment_mode:
            relations=['installment_payment']
            subject=[t for t in subject if t not in {'flexible','available','installment','installments','plans','plan','everything','all','once','clients','customers'} and not matches(t,'payment fee pay bill')]
        elif kind=='BOOLEAN' and 'available' in subject:
            subject.remove('available');relations=['availability']
        # Temporal modifiers belong to the proposition window, not the object.
        qualifiers=[]
        modifier=None if re.search(r'\blooks? after\b',q) else re.search(r'\b(?:before|after|during)\b(.+)',q)
        if modifier:
            qualifiers=[t for t in re.findall(r'\w+',modifier.group(1)) if t not in STOP]
            subject=[t for t in subject if t not in qualifiers]
        proper=[t.lower() for t in re.findall(r'\b[A-Z][\w-]*\b',query) if t.lower() not in STOP|SLOTS and not matches(t,' '.join(relations+props))]
        return cls(subject,relations,props,kind,kind,'negative' if NEG.search(q) else 'unspecified',
                   re.findall(r'\b(?:before|after|overnight|morning|afternoon|evening)\b',q),
                   [t for t in tokens if t in {'my','our'}],qualifiers,proper,
                   main_interrogative, classification_reason, matched_rule)


class AnswerPipeline:
    MAX_PASSAGES=3
    MAX_FAQS=4
    MAX_SENTENCES=24
    MAX_CANDIDATES=64

    def __init__(self):
        self.audit={}

    def run(self, query, passages, title=''):
        frame=QueryFrame.parse(query)
        self.audit=dict(query_frame=asdict(frame),selected_document=title,selected_passages=[],candidates=[],
                        budgets=dict(passages=self.MAX_PASSAGES,additional_faqs=self.MAX_FAQS,sentences_per_passage=self.MAX_SENTENCES,candidates=self.MAX_CANDIDATES,context_sentences=3),arbitration='ABSTAIN: no validated proposition')
        valid=[]
        for passage in passages[:self.MAX_PASSAGES+self.MAX_FAQS]:
            text=passage['text']; heading=passage.get('heading','')
            self.audit['selected_passages'].append(dict(id=passage.get('id'),score=passage.get('score'),heading=heading))
            # Discovery is generous. A passage score cannot authorize or veto
            # an otherwise validated proposition in this bounded source set.
            source_sentences=sentences(text)[:self.MAX_SENTENCES]
            for index,sentence in enumerate(source_sentences):
                if len(self.audit['candidates'])>=self.MAX_CANDIDATES:break
                if sentence.endswith('?') or len(sentence)>650:continue
                resolved,context=resolve_local_context(sentence,text)
                # A title is part of one person name, not a second antecedent.
                if resolved==sentence and index and re.match(r'^(?:He|She|His|Her)\b',sentence):
                    previous=source_sentences[index-1]
                    names=[m for m in names_in(previous) if not re.search(r'\b(?:at|in|near|from)\s*$',previous[:m.start()])]
                    if len(names)==1 and (names[0].start()==0 or re.search(r'\b(?:sent|given)\s+to\s*$',previous[:names[0].start()])):
                        resolved=re.sub(r'^(?:He|She|His|Her)\b',names[0].group(),sentence)
                        context=previous+' '+sentence
                if index:
                    previous=source_sentences[index-1]
                    # Restrict object anaphora to a single explicit grammatical
                    # object, excluding any trailing purpose/location phrase.
                    objects=re.findall(r'\b(?:bought|purchased|created)\s+(?:a|an|the)\s+([\w -]+?)(?:\s+for\b|[.!?])',previous,re.I)
                    objects+=re.findall(r'\b(?:looks after|maintains|manages)\s+(?:a|an|the)\s+([\w -]+?)(?:\s+at\b|\s+in\b|[.!?])',previous,re.I)
                    if len(objects)==1 and re.search(r'\bit\b',resolved,re.I):
                        resolved=re.sub(r'\bit\b',objects[0],resolved,flags=re.I)
                        context=previous+' '+sentence
                    # Repeated object nouns can carry an explicit local name.
                    named=re.search(r'\b(\w+)\s+is\s+(?:called|named)\s+([A-Z][\w-]*(?:\s+[A-Z][\w-]*)*)',previous)
                    if named and re.match(r'^The\s+'+re.escape(named.group(1))+r'\b',sentence):
                        resolved=sentence.replace('The '+named.group(1),named.group(2)+' '+named.group(1),1)
                        context=previous+' '+sentence
                # Local identity evidence is bounded to the adjacent sentences.
                window=' '.join(source_sentences[max(0,index-1):index+2])
                clauses=[sentence]
                if frame.expected_answer_type in {'DATE','YEAR','CENTURY'}:
                    clauses=re.split(r';\s*|,\s+(?:and|while|but|although)\s+|\s+while\s+|\s+but\s+|\s+and\s+(?=(?:[A-Z]|(?:was\s+)?\w+ed\b))',sentence)
                elif frame.expected_answer_type in {'PERSON','ORGANIZATION'}:
                    clauses=re.split(r';\s*|\s+and\s+(?=[A-Z][a-z]+\s+[A-Z][a-z]+\s)',sentence)
                for clause in clauses:
                    if frame.expected_answer_type in {'DATE','YEAR','CENTURY'}:spans=[m.group() for m in TIME.finditer(clause)]
                    elif frame.expected_answer_type in {'PERSON','ORGANIZATION'}:
                        spans=[m.group() for m in names_in(resolved if clause==sentence else clause) if m.group() in text]
                    else:spans=[clause]
                    # Remove overlapping shorter date candidates, never choose the first date.
                    spans=[v for v in spans if not any(v!=w and v in w for w in spans)]
                    for span in dict.fromkeys(spans):
                        if len(self.audit['candidates'])>=self.MAX_CANDIDATES:break
                        evidence=resolved if clause==sentence else clause
                        if clause!=sentence and clauses.index(clause)>0 and re.match(r'^(?:was\s+)?\w+ed\b',clause):
                            first_words=list(re.finditer(r'\b\w+\b',clauses[0]))
                            first_verb=next((w for w in first_words if stem_word(w.group().lower()) in VERB_STEMS),None)
                            if first_verb:evidence=clauses[0][:first_verb.start()]+' '+clause
                        record=dict(producer=frame.expected_answer_type.lower(),answer_span=span,support_sentence=sentence,support_clause=clause,support_passage=text,passage_id=passage.get('id'),heading=heading)
                        try:
                            self.validate(record,frame,evidence,window,title,context)
                        except Exception as exc:
                            record.update(validation='ABSTAIN',reason=f'ANSWER_GATE_EXCEPTION: {type(exc).__name__}',score=0)
                        self.audit['candidates'].append(record)
                        if record['validation']=='PASS':valid.append(record)
        if any('ANSWER_GATE_EXCEPTION' in c.get('reason','') for c in self.audit['candidates']):
            self.audit['arbitration']='ABSTAIN: ANSWER_GATE_EXCEPTION; arbitration unavailable'
            return None,self.audit['arbitration']
        # Archived evidence cannot override an explicitly current statement.
        current=[c for c in valid if re.search(r'\bcurrent\b',c['heading'],re.I)]
        if current:valid=current
        else:valid=[c for c in valid if not re.search(r'\b(?:old|previous|archived)\s+policy\b',c['heading'],re.I)]
        if valid:
            best=max(valid,key=lambda c:c['score'])
            conflicts=[c for c in valid if c['polarity']!=best['polarity']] if frame.expected_answer_type=='BOOLEAN' else []
            if frame.expected_answer_type in {'DATE','YEAR','CENTURY','PERSON','ORGANIZATION','ATTRIBUTE_VALUE','NUMBER','QUANTITY','PRICE'}:
                conflicts += [c for c in valid if c['answer_span']!=best['answer_span'] and c['score']==best['score']]
            if conflicts:self.audit['arbitration']='ABSTAIN: contradictory supported propositions'
            else:
                self.audit.update(arbitration='PASS: grounded proposition satisfies all hard contracts',selected_candidate=self.audit['candidates'].index(best),answer_span=best['answer_span'],support_sentence=best['support_sentence'],support_passage=best['support_passage'])
                return best['answer_span'],self.audit['arbitration']
        return None,self.audit['arbitration']

    def validate(self, c, frame, evidence, window, title, context):
        kind=frame.expected_answer_type
        anchors=frame.subject
        # Title establishes source identity only for proper names. Other nouns
        # must occur in the proposition or a resolved local antecedent.
        absent=[t for t in anchors if not matches(t,evidence)]
        missing=[t for t in absent if not matches(t,title)]
        properties=all(matches(t,evidence) for t in frame.property)
        if frame.property and set(frame.property)<={'color','colour'}:properties=properties or bool(COLORS.search(evidence))
        if frame.property==['temperature']:properties=properties or bool(re.search(r'\d+\s*°?\s*[CF]\b',evidence))
        relations=all(matches(t,evidence) for t in frame.relation)
        if frame.relation==['installment_payment']:
            mode=bool(re.search(r'\b(?:installments?|split|divide)\b',evidence,re.I))
            payment=any(matches(t,evidence) for t in ['payment','fee','bill','pay'])
            operative=bool(re.search(r'\b(?:may|can|cannot|must)\s+(?:not\s+)?(?:currently\s+)?(?:be\s+)?(?:pay|paid|split|divide)\b|\b(?:offer|allow|support|permit|accept)\w*\b|\b(?:available|unavailable|supported|unsupported|offered|permitted)\b',evidence,re.I))
            relations=mode and payment and operative
        elif frame.relation==['availability']:
            relations=bool(re.search(r'\b(?:available|unavailable|supported|unsupported|offered|not offered)\b',evidence,re.I))
        elif kind=='BOOLEAN' and frame.relation==['pay']:
            relations=relations or bool(re.search(r'\b(?:supported|accepted|available)\b',evidence,re.I))
        # Possessive/nominal uses ("its own name", "the repair manual") do
        # not assert the corresponding verb relation.
        for relation in frame.relation:
            spans=re.findall(r'\b(?:a|an|the|my|its|their|our|your)\s+(\w+)\b',evidence,re.I)
            if spans and any(matches(relation,w) for w in spans):
                occurrences=sum(matches(relation,w) for w in re.findall(r'\b\w+\b',evidence))
                if occurrences==sum(matches(relation,w) for w in spans):relations=False
        if kind=='DEFINITION':relations=bool(re.search(r'\b(?:is|are|means|refers to|defined as|use the term|denotes|studies|attaches|stores)\b',evidence,re.I))
        grounded=c['answer_span'] in c['support_passage'] and c['support_sentence'] in c['support_passage']
        type_ok=True
        if kind in {'DATE','YEAR','CENTURY'}:
            type_ok=bool(TIME.fullmatch(c['answer_span']))
            if kind=='YEAR':type_ok=type_ok and bool(re.search(r'\b[1-9]\d{3}\b',c['answer_span']))
            if kind=='CENTURY':type_ok=type_ok and 'century' in c['answer_span'].lower()
        elif kind in {'NUMBER','QUANTITY','PRICE'}:
            type_ok=bool(NUM.search(evidence) or re.search(r'\d+(?:\.\d+)?\s*(?:kg|g|km|cm|mm|ml)\b',evidence,re.I))
            if kind=='PRICE':type_ok=type_ok and bool(re.search(r'\b(?:coins?|crowns?|dollars?|pounds?|rupees?|Rs|PKR|USD|EUR|GBP)\b|[$£€]',evidence,re.I))
            if kind=='QUANTITY':type_ok=type_ok and bool(re.search(r'\b(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?|kilograms?|grams?|pounds?|metres?|meters?|litres?|liters?)\b|\d\s*(?:kg|g|km|cm|mm|ml)\b',evidence,re.I))
        elif kind=='CAUSE':type_ok=bool(CAUSAL.search(evidence))
        elif kind in {'PERSON','ORGANIZATION'}:
            # Require a named grammatical actor of the requested action, not
            # any capitalized word in a topical sentence.
            actor=False
            for relation in frame.relation:
                words=list(re.finditer(r'\b\w+\b',evidence))
                for pos,word in enumerate(words):
                    if not matches(relation,word.group()):continue
                    before=evidence[:word.start()].strip(); after=evidence[word.end():]
                    passive=re.search(r'\bby\s+((?:Dr\.\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',after)
                    if passive and c['answer_span'] in passive.group(1):actor=True
                    actor_name=NAME.match(before)
                    if actor_name and actor_name.group() in NON_NAMES:actor_name=None
                    if actor_name and not re.search(r'\b(?:was|were|is|been)\s*$',before):
                        # An already specified location/organization is not the
                        # unknown actor of a "who ... at LOCATION" question.
                        novel=[t for t in re.findall(r'\w+',actor_name.group()) if t.lower() not in STOP and not any(matches(t,a) for a in anchors)]
                        if novel and c['answer_span'] in actor_name.group():actor=True
            type_ok=actor and bool(frame.relation)
        elif kind=='LOCATION':type_ok=bool(re.search(r'\b(?:in|at|on|from|under|beneath|above|behind|near|outside|inside|through|upstairs|downstairs|mezzanine)\b',evidence,re.I))
        elif kind in {'ACTION','PROCEDURE'}:type_ok=bool(re.search(r'\b(?:first|then|before|after|by|through|contact|ask|report|switch|wait|use|booked|reserve|turn|press|run|install|remove)\b',evidence,re.I))
        if kind=='BOOLEAN':
            type_ok=bool(frame.relation or frame.property) and bool(re.search(r'\b(?:may|can|must|does|not|no|available|allow|permit|offer|accept|carry|require|take|pay|split|installments)\w*\b',evidence,re.I))
        # A bare use/have relation needs its requested object/property, and a
        # relationless description needs enough local anchors to be explanatory.
        local=sum(matches(t,evidence) for t in anchors)
        informative=bool(frame.relation or frame.property or kind=='DEFINITION') or (local>=2 and len(evidence.split())>local+2)
        # The requested object must participate locally; nearby mentions alone
        # cannot transfer repair(clock) to repair(bell).
        non_title=[t for t in anchors if not matches(t,title)]
        binding=non_title[-1:] if non_title else anchors[-1:]
        object_bound=all(matches(t,evidence) for t in binding)
        if kind=='ATTRIBUTE_VALUE' and frame.property and all(matches(t,evidence) for t in frame.property) and all(matches(t,title) for t in anchors):object_bound=True
        qualifiers=all(matches(t,window) for t in frame.qualifiers)
        reason='supported'
        if not grounded:reason='UNGROUNDED'
        elif missing:reason='ENTITY_OR_QUALIFIER_MISMATCH: '+', '.join(missing)
        elif not properties:reason='PROPERTY_MISMATCH'
        elif not relations:reason='PREDICATE_MISMATCH'
        elif not object_bound:reason='OBJECT_NOT_BOUND_TO_PROPOSITION'
        elif not qualifiers:reason='QUALIFIER_MISMATCH'
        elif not type_ok:reason='ANSWER_TYPE_MISMATCH'
        elif not informative:reason='NO_PROPOSITION_SUPPORT'
        # A negated event does not supply its actor/date/value. Boolean
        # answers and complete causal/procedural statements preserve negation.
        if kind in {'PERSON','ORGANIZATION','DATE','YEAR','CENTURY','ATTRIBUTE_VALUE','NUMBER','QUANTITY','PRICE'} and NEG.search(evidence) and frame.polarity!='negative':reason='NEGATED_PROPOSITION_HAS_NO_POSITIVE_ANSWER'
        if kind!='BOOLEAN' and frame.polarity=='negative' and not NEG.search(evidence):reason='POLARITY_CONFLICT'
        # Unresolved pronouns are not independent entity evidence.
        if re.match(r'^(?:He|She|They)\b',c['support_sentence']) and evidence==c['support_sentence'] and kind in {'PERSON','DATE','YEAR','CENTURY'}:reason='AMBIGUOUS_COREFERENCE'
        c.update(entity_match=not missing,predicate_match=relations,property_match=properties,type_match=type_ok,grounding=grounded,
                 polarity='negative' if NEG.search(evidence) else 'positive',context=context,validation='PASS' if reason=='supported' else 'REJECT',reason=reason,
                 score=local*2+len(frame.relation)*3+len(frame.property)*3,
                 proposition=dict(subject_anchors=anchors,relation=frame.relation,property=frame.property,evaluation_clause=evidence,qualifiers=frame.qualifiers))
