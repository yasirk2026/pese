"""
PESE Link Graph: Internal Document Graph
Builds and maintains directed link topology across published documents.
"""

from typing import Dict, Set, List
from ..indexing.document import Document


class LinkGraph:
    """Directed graph representing internal linkages between PESE documents."""

    def __init__(self):
        # slug -> set of target slugs
        self.adj_list: Dict[str, Set[str]] = {}
        # slug -> set of source slugs
        self.rev_adj_list: Dict[str, Set[str]] = {}
        # All known nodes
        self.nodes: Set[str] = set()

    def build_from_documents(self, documents: List[Document]) -> None:
        """Reconstruct the entire link graph from a collection of documents."""
        self.adj_list.clear()
        self.rev_adj_list.clear()
        self.nodes.clear()

        # Register all known document slugs
        for doc in documents:
            if doc.status == "published":
                self.nodes.add(doc.slug)
                self.adj_list[doc.slug] = set()
                self.rev_adj_list[doc.slug] = set()

        # Connect edges
        for doc in documents:
            if doc.status != "published":
                continue
            targets = doc.get_all_internal_links()
            for target_slug in targets:
                # Only link to known internal documents, ignore self-links
                if target_slug in self.nodes and target_slug != doc.slug:
                    self.adj_list[doc.slug].add(target_slug)
                    self.rev_adj_list[target_slug].add(doc.slug)

    def in_degree(self, slug: str) -> int:
        """Number of distinct documents linking into this slug."""
        return len(self.rev_adj_list.get(slug, set()))

    def out_degree(self, slug: str) -> int:
        """Number of distinct documents this slug links out to."""
        return len(self.adj_list.get(slug, set()))

    def get_in_links(self, slug: str) -> List[str]:
        """List of document slugs that link to this slug."""
        return sorted(list(self.rev_adj_list.get(slug, set())))

    def get_out_links(self, slug: str) -> List[str]:
        """List of document slugs that this slug links to."""
        return sorted(list(self.adj_list.get(slug, set())))
