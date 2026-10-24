"""Reusable isolated public-corpus construction for release evaluation."""
from pathlib import Path
from engine.indexing.document import Document
from engine.indexing.inverted_index import InvertedIndex
from engine.indexing.snapshot import SnapshotStore
from engine.passages.extractor import PassageExtractor
from engine.link_graph.graph import LinkGraph
from engine.link_graph.authority import LinkAuthorityCalculator
from engine.ranking.scorer import RankingEngine
from engine.semantic.index import VectorIndex


def build_engine(documents, root, semantic=True):
    index = InvertedIndex()
    passages = {}
    for doc in documents:
        passages[doc.id] = PassageExtractor().extract_passages(doc)
        index.index_document(doc, passages[doc.id])
    graph = LinkGraph()
    graph.build_from_documents(documents)
    auth = LinkAuthorityCalculator(graph)
    auth.compute_scores()
    vectors = VectorIndex(index_dir=Path(root)/"vectors") if semantic else None
    if vectors:
        vectors.build_index(documents, passages, persist=False)
    return RankingEngine(index, auth, vectors, SnapshotStore(documents))


def document(slug, title, content, **kwargs):
    return Document(id=slug, slug=slug, title=title, content=content, status="published", **kwargs)


def closure_documents():
    return [
        document("owned", "My camera specifications", "My camera weighs 530 grams and uses a magnesium frame. My camera has a mechanical shutter."),
        document("generic", "Camera specifications", "A camera captures images. Many camera specifications depend on the model. Camera maintenance can prevent damage."),
        document("seo", "Specific information", "Providing specific information about camera specifications improves search engine optimization."),
        document("coref", "Mira and NOVA", "Mira created NOVA. She envisioned the idea in 2022."),
        document("ambiguous", "Cora and Lyle", "Cora spoke to Lyle. She launched the project in 2016."),
        document("payment", "Cobalt Clinic policy", "Cobalt Clinic clients may pay the fee in two equal installments."),
        document("schedule", "Cobalt Clinic scheduling", "Cobalt Clinic offers flexible appointment scheduling. The Cobalt Clinic fee is 90 coins."),
        document("short", "Kestrel creator", "Kestrel was created by Rowan Vale."),
        document("current", "Citrine policy", "## Old policy\nCitrine permitted installment payments in 2011.\n\n## Current policy\nCitrine does not offer installment payments."),
        document("nearby", "Morrow policy", "Morrow permitted installment payments. Morrow does not offer installment payments."),
        document("long", "Linden history", "## Geography\nLinden is a coastal town.\n\n## Railway\nThe Linden railway opened in 1903.\n\n## Museum\nThe Linden museum opened in 1972.\n\n## Economy\nLinden exports pottery."),
    ]
