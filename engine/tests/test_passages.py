"""
Unit tests for PESE Passages: extraction, scoring, and snippet generation.
"""

from engine.indexing.document import Document
from engine.indexing.inverted_index import InvertedIndex
from engine.nlp.tokenizer import QueryRepresentation
from engine.passages.extractor import PassageExtractor
from engine.passages.scorer import PassageScorer
from engine.passages.highlighter import SnippetGenerator, highlight_terms


def test_passage_extraction():
    content = """# Main Heading

First paragraph discussing bicycles and morning commute routines.

## Maintenance Section

Second paragraph detailing how to clean the chain using citrus degreaser.

Third paragraph about tire pressure.
"""
    doc = Document(id="p-test", slug="p-test", title="Test Doc", content=content)
    extractor = PassageExtractor()
    passages = extractor.extract_passages(doc)

    assert len(passages) >= 3
    # Check heading context capture
    assert passages[0].heading_context == "Main Heading"
    assert passages[1].heading_context == "Maintenance Section"


def test_passage_temporal_scoring_and_answer():
    content = """# My Story

Long unrelated introductory text about public transit and neighborhood routes.

After comparing bicycles for several months, I finally bought my first bicycle on 17 March 2024 from a local workshop.

Another concluding paragraph with general memories.
"""
    doc = Document(id="b-story", slug="b-story", title="My Story", content=content)
    index = InvertedIndex()
    extractor = PassageExtractor()
    passages = extractor.extract_passages(doc)
    index.index_document(doc, passages)

    scorer = PassageScorer(index)
    q_rep = QueryRepresentation("when did I buy my bicycle")

    scored = scorer.score_passages_for_doc("b-story", q_rep)
    assert len(scored) >= 2
    # The middle passage with date must win top score
    best_passage, score, breakdown = scored[0]
    assert "17 March 2024" in best_passage.text
    assert breakdown["temporal_bonus"] > 0

    snippet_gen = SnippetGenerator()
    snippet = snippet_gen.generate_snippet(best_passage.text, q_rep, is_featured_candidate=True)
    assert snippet["featured_answer"] == "17 March 2024"
    assert snippet["is_featured"] is True
