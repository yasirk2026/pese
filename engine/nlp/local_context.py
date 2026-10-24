"""Conservative two-sentence anaphora. No passage-wide identity borrowing."""
import re
from .evidence import sentences

_PRONOUN = re.compile(r"^(He|She|It|They|His|Her|Its|Their)\b", re.I)
_NAME = re.compile(r"\b[A-Z][A-Za-z0-9_-]*(?:\s+[A-Z][A-Za-z0-9_-]*)*\b")
_NON_NAMES = {"The", "A", "An", "Yes", "No", "Clients", "Customers", "Old", "Current"}


def resolve_local_context(sentence, passage):
    """Return evaluation text and evidence window; original answer remains unchanged.

    Only a leading pronoun following a single named grammatical subject is
    resolved. A second named person/organization makes the antecedent ambiguous.
    """
    if not _PRONOUN.match(sentence.strip()):
        return sentence, sentence
    spans = list(re.finditer(r"[^.!?\n]+[.!?]?", passage))
    for i, span in enumerate(spans):
        if span.group().strip() != sentence.strip() or i == 0:
            continue
        previous = spans[i-1].group().strip()
        between = passage[spans[i-1].end():span.start()]
        if "\n\n" in between or "\n\n" in previous:
            break
        # A short yes/no reply is not an antecedent; allow one preceding question.
        if previous.lower().strip(". ") in {"yes", "no"} and i >= 2:
            previous = spans[i-2].group().strip()
        names = [m for m in _NAME.finditer(previous) if m.group() not in _NON_NAMES]
        if not names or names[0].start() != 0:
            break
        subject = names[0].group()
        # Permit a named object only for neuter pronouns? No: keeping this
        # conservative avoids Ali / Hamza and person / organization ambiguity.
        named_objects = [m.group() for m in names[1:]]
        if named_objects and not (sentence.lower().startswith(("he ", "she ")) and
                                  all(n.isupper() for n in named_objects) and
                                  re.search(r"\b(?:idea|it|this)\b", sentence, re.I)):
            break
        resolved = _PRONOUN.sub(subject, sentence, count=1)
        if named_objects:
            resolved = previous + " " + resolved
        return resolved, previous + " " + sentence
    return sentence, sentence
