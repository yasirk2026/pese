"""
PESE Tests: Semantic Retrieval & Hybrid Search (Phase 2B)
Tests local embedding providers, vector indexing, incremental caching,
candidate fusion (RRF), semantic rescues, drift safeguards, and hybrid traces.
"""

import pytest
import numpy as np
from engine.indexing.document import Document
from engine.indexing.passage import Passage
from engine.indexing.store import DocumentStore
from engine.indexing.inverted_index import InvertedIndex
from engine.link_graph.graph import LinkGraph
from engine.link_graph.authority import LinkAuthorityCalculator
from engine.ranking.scorer import RankingEngine
from engine.semantic.provider import DeterministicMockProvider, FastembedProvider
from engine.semantic.models import SemanticCandidate, FusedCandidate
from engine.semantic.index import VectorIndex
from engine.semantic.drift import SemanticDriftDetector
from engine.semantic.retriever import SemanticRetriever
from engine.semantic.fusion import HybridCandidateFuser


def test_deterministic_mock_provider():
    provider = DeterministicMockProvider(dimension=128)
    vec = provider.embed_query("two-wheeled vehicle upkeep")
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (128,)
    norm = np.linalg.norm(vec)
    assert abs(norm - 1.0) < 1e-4

    matrix = provider.embed_texts(["hello world", "bicycle maintenance"])
    assert matrix.shape == (2, 128)
    for row in matrix:
        assert abs(np.linalg.norm(row) - 1.0) < 1e-4


def test_vector_index_incremental_caching(tmp_path):
    provider = DeterministicMockProvider(dimension=64)
    vindex = VectorIndex(provider=provider, index_dir=tmp_path)

    doc = Document(
        id="test-doc-1",
        slug="test-doc-1",
        title="Test Document",
        content="This is the first paragraph about cycling.\n\nThis is the second paragraph.",
        keywords=["cycling", "test"],
    )
    p1 = Passage(
        passage_id="test-doc-1#p0",
        doc_id="test-doc-1",
        slug="test-doc-1",
        doc_title="Test Document",
        text="This is the first paragraph about cycling.",
    )
    p2 = Passage(
        passage_id="test-doc-1#p1",
        doc_id="test-doc-1",
        slug="test-doc-1",
        doc_title="Test Document",
        text="This is the second paragraph.",
    )

    # First build
    vindex.build_index([doc], {doc.id: [p1, p2]})
    assert len(vindex.passage_meta) == 2
    assert len(vindex.doc_meta) == 1
    assert vindex.cache_misses >= 3
    initial_hits = vindex.cache_hits

    # Second build with identical content -> should hit cache 100%
    vindex.build_index([doc], {doc.id: [p1, p2]})
    assert vindex.cache_hits > initial_hits


def test_hybrid_fusion_rrf():
    fuser = HybridCandidateFuser(rrf_k=60, lexical_weight=1.0, semantic_weight=0.85)

    lex_candidates = [
        {"doc_id": "docA", "slug": "doc-a", "title": "Doc A", "preliminary_score": 10.0, "bm25f_data": {}},
        {"doc_id": "docB", "slug": "doc-b", "title": "Doc B", "preliminary_score": 5.0, "bm25f_data": {}},
    ]
    sem_candidates = [
        SemanticCandidate(
            doc_id="docB",
            slug="doc-b",
            title="Doc B",
            semantic_score=0.75,
            semantic_rank=1,
        ),
        SemanticCandidate(
            doc_id="docC",
            slug="doc-c",
            title="Doc C",
            semantic_score=0.70,
            semantic_rank=2,
            is_semantic_rescue=True,
        ),
    ]

    fused = fuser.fuse(lex_candidates, sem_candidates)
    fused_map = {f.doc_id: f for f in fused}

    # docB was rank 2 in lexical and rank 1 in semantic -> strong combined RRF
    assert "docB" in fused_map
    assert fused_map["docB"].bm25_rank == 2
    assert fused_map["docB"].semantic_rank == 1
    expected_docB_rrf = (1.0 / (60 + 2)) + (0.85 / (60 + 1))
    assert abs(fused_map["docB"].rrf_score - expected_docB_rrf) < 1e-5

    # docC was only in semantic -> semantic rescue
    assert "docC" in fused_map
    assert fused_map["docC"].is_semantic_rescue is True
    assert fused_map["docC"].bm25_rank is None


def test_semantic_drift_safeguard():
    detector = SemanticDriftDetector()

    # Polysemy drift: Query specifies 'snake' (reptile domain), but doc is programming code
    penalty, reason = detector.evaluate_drift(
        query="python snake care and feeding",
        query_terms=["python", "snake", "care", "feeding"],
        doc_title="Python Virtual Environments with pip and venv",
        doc_content="Learn how to install pip packages, import libraries, and execute Python 3 code in isolated environments.",
        doc_keywords=["python", "pip", "virtualenv", "code"],
        semantic_score=0.68,
    )
    assert penalty > 0.50
    assert "Topical drift" in reason

    # Non-drift case: Query specifies 'bicycle upkeep' and doc is bicycle maintenance
    penalty2, reason2 = detector.evaluate_drift(
        query="two-wheeled vehicle upkeep",
        query_terms=["two-wheeled", "vehicle", "upkeep"],
        doc_title="Bicycle Maintenance Notes",
        doc_content="Clean the chain with degreaser and inspect tire pressure regularly.",
        doc_keywords=["bicycle", "maintenance", "chain"],
        semantic_score=0.72,
    )
    assert penalty2 == 0.0
    assert reason2 is None


def test_end_to_end_hybrid_rescue(tmp_path):
    store = DocumentStore(storage_path=tmp_path / "test_docs.json")
    doc_bike = Document(
        id="bike-upkeep",
        slug="bike-upkeep",
        title="Bicycle Cleaning and Chain Lubrication Guide",
        content="Preventative maintenance for your commuter bike involves keeping the drivetrain grit-free and lubing the chain links every week.",
        keywords=["bicycle", "cleaning", "chain", "maintenance"],
        status="published",
    )
    doc_vocab = Document(
        id="city-transit",
        slug="city-transit",
        title="City Transit and Vehicle Upkeep",
        content="Urban travel includes two-wheeled vehicle upkeep and bus systems.",
        keywords=["transit", "vehicle", "upkeep"],
        status="published",
    )
    store.save_document(doc_bike)
    store.save_document(doc_vocab)

    index = InvertedIndex()
    p1 = Passage(
        passage_id="bike-upkeep#p0",
        doc_id="bike-upkeep",
        slug="bike-upkeep",
        doc_title="Bicycle Cleaning Guide",
        text=doc_bike.content,
    )
    p2 = Passage(
        passage_id="city-transit#p0",
        doc_id="city-transit",
        slug="city-transit",
        doc_title="City Transit",
        text=doc_vocab.content,
    )
    index.index_document(doc_bike, [p1])
    index.index_document(doc_vocab, [p2])

    # Build local vector index with real Fastembed in isolated tmp_path
    vindex = VectorIndex(index_dir=tmp_path / "vindex")
    vindex.build_index([doc_bike, doc_vocab], {doc_bike.id: [p1], doc_vocab.id: [p2]})

    graph = LinkGraph()
    graph.build_from_documents([doc_bike, doc_vocab])
    auth = LinkAuthorityCalculator(graph)
    auth.compute_scores()

    engine = RankingEngine(index, auth, vector_index=vindex, doc_store=store)

    # Paraphrase search with zero lexical overlap on doc_bike:
    results = engine.search("two-wheeled vehicle upkeep", limit=5)
    assert len(results) > 0
    rescued_bike = next((r for r in results if r.slug == "bike-upkeep"), None)
    assert rescued_bike is not None
    assert rescued_bike.is_semantic_rescue is True
    assert rescued_bike.trace.semantic_similarity > 0.50
    assert rescued_bike.trace.retrieval_mode == "hybrid"


def test_retrieval_mode_ablation(tmp_path):
    store = DocumentStore(storage_path=tmp_path / "test_docs_ablation.json")
    doc = Document(
        id="test-doc",
        slug="test-doc",
        title="Test Document",
        content="Content containing exact phrase unique_foobar_word.",
        keywords=["test"],
        status="published",
    )
    store.save_document(doc)

    index = InvertedIndex()
    p = Passage(passage_id="test-doc#p0", doc_id="test-doc", slug="test-doc", doc_title="Test", text=doc.content)
    index.index_document(doc, [p])

    vindex = VectorIndex(index_dir=tmp_path / "vindex_ablation")
    vindex.build_index([doc], {doc.id: [p]})

    graph = LinkGraph()
    graph.build_from_documents([doc])
    auth = LinkAuthorityCalculator(graph)
    auth.compute_scores()

    engine = RankingEngine(index, auth, vector_index=vindex, doc_store=store)

    # Lexical only mode
    res_lex = engine.search("unique_foobar_word", retrieval_mode="lexical_only")
    assert len(res_lex) > 0
    assert res_lex.hybrid_trace["retrieval_mode"] == "lexical_only"
    assert res_lex.hybrid_trace["semantic_candidates_count"] == 0

    # Semantic only mode
    res_sem = engine.search("unique_foobar_word", retrieval_mode="semantic_only")
    assert res_sem.hybrid_trace["retrieval_mode"] == "semantic_only"
    assert res_sem.hybrid_trace["lexical_candidates_count"] == 0
