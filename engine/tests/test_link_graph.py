"""
Unit tests for PESE Link Graph: topology and bounded authority scoring.
"""

from engine.indexing.document import Document
from engine.link_graph.graph import LinkGraph
from engine.link_graph.authority import LinkAuthorityCalculator, MAX_LINK_AUTHORITY_BOOST


def test_link_graph_construction():
    doc1 = Document(
        id="d1", slug="doc-a", title="Doc A", content="Linking to [Doc B](/doc/doc-b)",
        internal_links=["doc-b"]
    )
    doc2 = Document(
        id="d2", slug="doc-b", title="Doc B", content="Linking back to [Doc A](/doc/doc-a)",
        internal_links=["doc-a"]
    )
    doc3 = Document(
        id="d3", slug="doc-c", title="Doc C", content="Also linking to [Doc B](/doc/doc-b)",
        internal_links=["doc-b"]
    )

    graph = LinkGraph()
    graph.build_from_documents([doc1, doc2, doc3])

    assert graph.in_degree("doc-b") == 2
    assert graph.in_degree("doc-a") == 1
    assert graph.in_degree("doc-c") == 0


def test_bounded_link_authority():
    docs = []
    # Create 1 hub and 10 pages pointing to it
    for i in range(10):
        docs.append(Document(
            id=f"page-{i}", slug=f"page-{i}", title=f"Page {i}",
            content="Check [Hub](/doc/hub-page)", internal_links=["hub-page"]
        ))
    docs.append(Document(
        id="hub", slug="hub-page", title="Hub Page",
        content="Welcome to the hub.", internal_links=[]
    ))

    graph = LinkGraph()
    graph.build_from_documents(docs)
    calc = LinkAuthorityCalculator(graph)
    calc.compute_scores()

    hub_auth = calc.get_authority_score("hub-page")
    # Authority must be strictly positive and strictly bounded <= MAX_LINK_AUTHORITY_BOOST
    assert 0.0 < hub_auth <= MAX_LINK_AUTHORITY_BOOST
