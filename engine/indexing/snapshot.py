"""One published search generation; canonical storage remains authoritative."""
from dataclasses import dataclass
from hashlib import sha256
import json
from copy import deepcopy


def document_generation(documents):
    return sha256(json.dumps([d.model_dump() for d in sorted(documents, key=lambda d: d.id)],
                             sort_keys=True).encode()).hexdigest()[:16]


class SnapshotStore:
    """Read-only document view used by every discovery component in a generation."""
    def __init__(self, documents):
        self.documents = tuple(d.model_copy(deep=True) for d in documents)

    def list_documents(self, status=None):
        return [d.model_copy(deep=True) for d in self.documents if status is None or d.status == status]

    def get_document(self, identity):
        return next((d.model_copy(deep=True) for d in self.documents if identity in (d.id, d.slug)), None)

    get_by_slug = get_document


@dataclass(frozen=True)
class SearchSnapshot:
    generation: str
    engine: object
    index: object
    vectors: object
    graph: object
    authority: object
    autocomplete: object
    related: object
    questions: object
