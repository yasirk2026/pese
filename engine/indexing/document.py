"""
PESE Indexing: Document Model
Canonical document data structure for authored and external sources.
"""

import re
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


# Pattern to extract internal markdown links: [anchor text](/doc/some-slug)
MARKDOWN_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\((/doc/[a-zA-Z0-9\-_]+|\./[a-zA-Z0-9\-_]+|[a-zA-Z0-9\-_]+)\)')

# Pattern to extract markdown headings: # Heading, ## Heading, etc.
MARKDOWN_HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)


class Document(BaseModel):
    """Canonical document model in PESE."""
    id: str
    slug: str
    title: str
    meta_description: str = ""
    content: str
    content_schema_version: int = 1   # 1 = legacy plaintext/markdown, 2 = structured AST + FAQs
    structured_content: Optional[dict] = None  # ProseMirror / TipTap JSON block AST
    faqs: List[dict] = Field(default_factory=list)  # PESE-native structured FAQ items: [{ id, question, answer }]
    headings: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    internal_links: List[str] = Field(default_factory=list)
    source_type: str = "authored"  # 'authored' | 'external'
    status: str = "published"       # 'published' | 'draft'
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    indexed_at: Optional[str] = None

    def extract_headings_from_content(self) -> List[str]:
        """Extract markdown headings from content if explicit headings list is empty."""
        extracted = []
        for match in MARKDOWN_HEADING_PATTERN.finditer(self.content):
            heading_text = match.group(2).strip()
            if heading_text:
                extracted.append(heading_text)
        return extracted

    def extract_links_from_content(self) -> List[str]:
        """Extract markdown link targets pointing to other PESE documents."""
        links = []
        for match in MARKDOWN_LINK_PATTERN.finditer(self.content):
            target = match.group(2).strip()
            # Clean to slug format
            target_slug = target.replace("/doc/", "").replace("./", "").strip("/")
            if target_slug and target_slug != self.slug:
                links.append(target_slug)

        # Also extract from structured_content AST if present
        if self.structured_content and isinstance(self.structured_content, dict):
            def walk_nodes(node):
                if isinstance(node, dict):
                    marks = node.get("marks", [])
                    for m in marks:
                        if isinstance(m, dict) and m.get("type") == "link":
                            href = m.get("attrs", {}).get("href", "")
                            if "/doc/" in href or href.startswith("./"):
                                slug = href.replace("/doc/", "").replace("./", "").strip("/")
                                if slug and slug != self.slug:
                                    links.append(slug)
                    for child in node.get("content", []):
                        walk_nodes(child)
            walk_nodes(self.structured_content)

        return list(set(links))

    def get_all_headings(self) -> List[str]:
        """Combine authored headings, extracted markdown headings, and FAQ questions."""
        combined = list(self.headings)
        extracted = self.extract_headings_from_content()
        for h in extracted:
            if h not in combined:
                combined.append(h)

        # Include FAQ section header and questions
        if self.faqs:
            if "Frequently Asked Questions" not in combined:
                combined.append("Frequently Asked Questions")
            for faq in self.faqs:
                q = faq.get("question", "").strip()
                if q and q not in combined:
                    combined.append(q)

        return combined

    def get_all_internal_links(self) -> List[str]:
        """Combine authored internal links with content markdown links."""
        all_links = set()
        for link in self.internal_links:
            clean = link.replace("/doc/", "").replace("./", "").strip("/")
            if clean:
                all_links.add(clean)
        for link in self.extract_links_from_content():
            all_links.add(link)
        return list(all_links)

    def to_dict(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "Document":
        return cls(**data)
