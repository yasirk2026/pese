"""
PESE Indexing: Inverted Index
Multi-field inverted index supporting document-level and passage-level lexical indexing,
field lengths, term frequencies, and positional postings for phrase matching.
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from .document import Document
from .passage import Passage
from ..nlp.tokenizer import tokenize
from ..nlp.stemmer import stem_word
from ..nlp.stopwords import filter_stopwords


class Posting:
    """Document posting containing field frequencies and token positions."""
    def __init__(self, doc_id: str):
        self.doc_id: str = doc_id
        self.field_tfs: Dict[str, int] = {
            "title": 0,
            "headings": 0,
            "keywords": 0,
            "meta_description": 0,
            "body": 0,
        }
        self.positions: Dict[str, List[int]] = {
            "title": [],
            "headings": [],
            "keywords": [],
            "meta_description": [],
            "body": [],
        }

    def total_tf(self) -> int:
        return sum(self.field_tfs.values())

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "field_tfs": self.field_tfs,
            "positions": self.positions,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Posting":
        p = cls(data["doc_id"])
        p.field_tfs = data.get("field_tfs", {})
        p.positions = data.get("positions", {})
        return p


class PassagePosting:
    """Passage posting for passage-level lexical retrieval."""
    def __init__(self, passage_id: str, doc_id: str, tf: int):
        self.passage_id: str = passage_id
        self.doc_id: str = doc_id
        self.tf: int = tf

    def to_dict(self) -> dict:
        return {
            "passage_id": self.passage_id,
            "doc_id": self.doc_id,
            "tf": self.tf,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PassagePosting":
        return cls(data["passage_id"], data["doc_id"], data["tf"])


class InvertedIndex:
    """
    Core inverted index supporting multi-field retrieval, field length normalization,
    and passage-level lexical matching.
    """

    def __init__(self):
        # term -> list of Posting
        self.index: Dict[str, Dict[str, Posting]] = {}
        # passage_term -> list of PassagePosting
        self.passage_index: Dict[str, Dict[str, PassagePosting]] = {}

        # Document registry: doc_id -> metadata
        self.documents: Dict[str, Dict[str, Any]] = {}
        # Passage registry: passage_id -> Passage
        self.passages: Dict[str, Passage] = {}

        # Raw vocabulary tracking (unstemmed tokens for spelling recovery)
        self.raw_terms: Dict[str, int] = {}

        # Field lengths per doc: doc_id -> {field: length}
        self.field_lengths: Dict[str, Dict[str, int]] = {}

        # Aggregated stats
        self.total_docs: int = 0
        self.total_field_lengths: Dict[str, int] = {
            "title": 0,
            "headings": 0,
            "keywords": 0,
            "meta_description": 0,
            "body": 0,
        }
        self.avg_field_lengths: Dict[str, float] = {
            "title": 1.0,
            "headings": 1.0,
            "keywords": 1.0,
            "meta_description": 1.0,
            "body": 1.0,
        }

    def _extract_field_tokens(self, doc: Document) -> Dict[str, List[Tuple[str, str, int]]]:
        """
        Extract (raw_token, stem, position) tuples for each field of a document.
        """
        fields: Dict[str, List[Tuple[str, str, int]]] = {}

        # 1. Title
        raw_title_tokens = tokenize(doc.title)
        fields["title"] = [(t, stem_word(t), idx) for idx, t in enumerate(raw_title_tokens)]

        # 2. Headings
        all_headings = doc.get_all_headings()
        heading_text = " ".join(all_headings)
        raw_heading_tokens = tokenize(heading_text)
        fields["headings"] = [(t, stem_word(t), idx) for idx, t in enumerate(raw_heading_tokens)]

        # 3. Keywords
        keyword_text = " ".join(doc.keywords)
        raw_keyword_tokens = tokenize(keyword_text)
        fields["keywords"] = [(t, stem_word(t), idx) for idx, t in enumerate(raw_keyword_tokens)]

        # 4. Meta Description
        raw_meta_tokens = tokenize(doc.meta_description)
        fields["meta_description"] = [(t, stem_word(t), idx) for idx, t in enumerate(raw_meta_tokens)]

        # 5. Body
        raw_body_tokens = tokenize(doc.content)
        fields["body"] = [(t, stem_word(t), idx) for idx, t in enumerate(raw_body_tokens)]

        return fields

    def index_document(self, doc: Document, passages: List[Passage]) -> None:
        """Add or replace a document and its passages in the index."""
        # If already exists, clear old entries first
        if doc.id in self.documents:
            self.remove_document(doc.id)

        field_tokens = self._extract_field_tokens(doc)
        field_lens = {}

        for field_name, tokens in field_tokens.items():
            field_lens[field_name] = len(tokens)
            self.total_field_lengths[field_name] += len(tokens)

            for raw_tok, stem, pos in tokens:
                low_raw = raw_tok.lower()
                self.raw_terms[low_raw] = self.raw_terms.get(low_raw, 0) + 1
                # Index both raw token and stem
                for term in {raw_tok, stem}:
                    if term not in self.index:
                        self.index[term] = {}
                    if doc.id not in self.index[term]:
                        self.index[term][doc.id] = Posting(doc.id)
                    posting = self.index[term][doc.id]
                    posting.field_tfs[field_name] += 1
                    posting.positions[field_name].append(pos)

        self.field_lengths[doc.id] = field_lens
        self.documents[doc.id] = {
            "id": doc.id,
            "slug": doc.slug,
            "title": doc.title,
            "meta_description": doc.meta_description,
            "keywords": doc.keywords,
            "internal_links": doc.get_all_internal_links(),
            "source_type": doc.source_type,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
            "content": doc.content,
            "faqs": doc.faqs,
            "headings": doc.get_all_headings(),
            "raw_word_count": len(doc.content.split()),
        }

        # Index passages
        for p in passages:
            self.passages[p.passage_id] = p
            # Calculate passage term frequencies
            p_tokens = p.tokens
            filtered = filter_stopwords(p_tokens, preserve_intent=True)
            for raw_tok in filtered:
                stem = stem_word(raw_tok)
                for term in {raw_tok, stem}:
                    if term not in self.passage_index:
                        self.passage_index[term] = {}
                    if p.passage_id not in self.passage_index[term]:
                        self.passage_index[term][p.passage_id] = PassagePosting(p.passage_id, doc.id, 0)
                    self.passage_index[term][p.passage_id].tf += 1

        self.total_docs += 1
        self._update_averages()

    def remove_document(self, doc_id: str) -> None:
        """Remove a document and its associated passages from the index."""
        if doc_id not in self.documents:
            return

        # Subtract field lengths
        old_lengths = self.field_lengths.get(doc_id, {})
        for field, length in old_lengths.items():
            self.total_field_lengths[field] -= length

        del self.field_lengths[doc_id]
        doc_slug = self.documents[doc_id]["slug"]
        del self.documents[doc_id]

        # Remove postings
        for term, postings in list(self.index.items()):
            if doc_id in postings:
                del postings[doc_id]
            if not postings:
                del self.index[term]

        # Remove passages
        passages_to_remove = [pid for pid, p in self.passages.items() if p.doc_id == doc_id or p.slug == doc_slug]
        for pid in passages_to_remove:
            del self.passages[pid]

        for term, p_postings in list(self.passage_index.items()):
            for pid in passages_to_remove:
                if pid in p_postings:
                    del p_postings[pid]
            if not p_postings:
                del self.passage_index[term]

        self.total_docs = max(0, self.total_docs - 1)
        self._update_averages()

    def _update_averages(self) -> None:
        """Recalculate average field lengths across the collection."""
        n = max(1, self.total_docs)
        for field in self.total_field_lengths:
            self.avg_field_lengths[field] = max(1.0, self.total_field_lengths[field] / n)

    def get_document_frequency(self, term: str) -> int:
        """Return the number of documents containing term or its stem."""
        return len(self.index.get(term, {}))

    def get_postings(self, term: str) -> List[Posting]:
        """Return postings list for a given term."""
        return list(self.index.get(term, {}).values())

    def get_passage_postings(self, term: str) -> List[PassagePosting]:
        """Return passage postings for a given term."""
        return list(self.passage_index.get(term, {}).values())

    def save_to_disk(self, file_path: Path) -> None:
        """Serialize index to JSON."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "total_docs": self.total_docs,
            "total_field_lengths": self.total_field_lengths,
            "avg_field_lengths": self.avg_field_lengths,
            "field_lengths": self.field_lengths,
            "raw_terms": self.raw_terms,
            "documents": self.documents,
            "passages": {pid: p.to_dict() for pid, p in self.passages.items()},
            "index": {
                term: {doc_id: posting.to_dict() for doc_id, posting in postings.items()}
                for term, postings in self.index.items()
            },
            "passage_index": {
                term: {pid: pp.to_dict() for pid, pp in p_postings.items()}
                for term, p_postings in self.passage_index.items()
            }
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    @classmethod
    def load_from_disk(cls, file_path: Path) -> "InvertedIndex":
        """Deserialize index from JSON."""
        idx = cls()
        if not file_path.exists():
            return idx

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        idx.total_docs = data.get("total_docs", 0)
        idx.total_field_lengths = data.get("total_field_lengths", idx.total_field_lengths)
        idx.avg_field_lengths = data.get("avg_field_lengths", idx.avg_field_lengths)
        idx.field_lengths = data.get("field_lengths", {})
        idx.raw_terms = data.get("raw_terms", {})
        idx.documents = data.get("documents", {})

        # Load passages
        for pid, pdata in data.get("passages", {}).items():
            idx.passages[pid] = Passage.from_dict(pdata)

        # Load document postings
        for term, postings in data.get("index", {}).items():
            idx.index[term] = {
                doc_id: Posting.from_dict(pdata) for doc_id, pdata in postings.items()
            }

        # Load passage postings
        for term, p_postings in data.get("passage_index", {}).items():
            idx.passage_index[term] = {
                pid: PassagePosting.from_dict(ppdata) for pid, ppdata in p_postings.items()
            }

        return idx
