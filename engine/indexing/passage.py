"""
PESE Indexing: Passage Model
Data structure for passage-level indexing and candidate passage representation.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class Passage(BaseModel):
    """
    A segmented passage from a document.
    Enables passage-level lexical indexing, relevance scoring, and featured snippet extraction.
    """
    passage_id: str             # e.g. "my-bicycle-story#p2" or "doc#faq_101"
    doc_id: str                 # Document ID
    slug: str                   # Document slug
    doc_title: str              # Document title for easy snippet rendering
    text: str                   # Clean original text of the passage
    heading_context: Optional[str] = None  # Nearest preceding heading if any
    heading_level: Optional[int] = None    # 1, 2, 3, 4
    block_type: str = "paragraph"          # "paragraph" | "heading" | "list_item" | "code" | "faq" | "quote"
    faq_id: Optional[str] = None           # Stable FAQ identifier if block_type == "faq"
    faq_question: Optional[str] = None     # Specific FAQ question text
    list_context: Optional[str] = None     # e.g. "2/5" or "bullet"
    marks: List[str] = Field(default_factory=list) # e.g. ["bold", "italic"]
    structural_metadata: dict = Field(default_factory=dict)
    tokens: List[str] = Field(default_factory=list)
    stems: List[str] = Field(default_factory=list)
    token_count: int = 0
    offset_start: int = 0
    offset_end: int = 0
    passage_index: int = 0      # Position in document (0, 1, 2, ...)

    def to_dict(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "Passage":
        return cls(**data)
