"""
PESE Indexing package: Document model, Passage model, Document Store, and Inverted Index.
"""

from .document import Document
from .passage import Passage
from .inverted_index import InvertedIndex, Posting, PassagePosting

__all__ = [
    "Document",
    "Passage",
    "DocumentStore",
    "InvertedIndex",
    "Posting",
    "PassagePosting",
]


def __getattr__(name):
    # Portable validators can import Document without resolving/initializing a runtime.
    if name == "DocumentStore":
        from .store import DocumentStore
        return DocumentStore
    raise AttributeError(name)
