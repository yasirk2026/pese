"""CMS/API freshness acceptance with an isolated local store, never user data."""
from pathlib import Path
from fastapi.testclient import TestClient
from engine.indexing.store import DocumentStore
from engine.semantic.index import VectorIndex
from engine.semantic.provider import DeterministicMockProvider
import pytest


def test_cms_publish_edit_unpublish_updates_all_indexes(tmp_path,monkeypatch):
    import engine.api.main as api
    from engine.ranking.scorer import RankingEngine
    store=DocumentStore(storage_path=tmp_path/"documents.json")
    provider=DeterministicMockProvider()
    def vectors(**kwargs):
        return VectorIndex(provider=provider,index_dir=tmp_path/"vectors")
    # Preserve the module's original globals even though reload assigns them.
    for name in ["index","graph","link_auth","engine","autocomplete_engine","related_engine","paa_engine","family_registry","active_snapshot","publication_state"]:
        monkeypatch.setattr(api,name,getattr(api,name))
    monkeypatch.setattr(api,"publication_state",dict(api.publication_state))
    monkeypatch.setattr(api,"store",store)
    monkeypatch.setattr(api,"vector_index",vectors())
    monkeypatch.setattr(api,"VectorIndex",vectors)
    monkeypatch.setattr(RankingEngine,"_get_qa_reader",lambda self:None)
    client=TestClient(api.app)
    doc=dict(id="audit-temporary",slug="audit-temporary",title="Zinnia instrument",content="The Zinnia instrument launched in 2013.",status="published",
        faqs=[dict(id="f",question="When did the Zinnia instrument launch?",answer="The Zinnia instrument launched in 2013.")])
    assert client.post("/api/documents",json=doc).status_code==200
    first_engine=api.engine
    first=client.get("/api/search",params={"q":"When did Zinnia launch?"}).json()
    assert first["results"][0]["slug"]==doc["slug"]
    assert api.index.passages and api.vector_index.passage_meta and api.paa_engine._cached_candidates
    generation=first["index_versions"]["document_version"]
    doc["content"]="The Zinnia instrument launched in 2018."
    doc["faqs"][0]["answer"]="The Zinnia instrument launched in 2018."
    assert client.post("/api/documents",json=doc).status_code==200
    assert api.engine is not first_engine
    assert first_engine.index.documents[doc["id"]]["content"].endswith("2013.")
    assert api.engine.index_versions["document_version"] != generation
    edited=client.get("/api/search",params={"q":"When did Zinnia launch?"}).json()
    assert "2018" in edited["results"][0]["featured_answer"]
    assert all("2013" not in p.text for p in api.index.passages.values())
    assert all("2013" not in p.text for p in api.vector_index.passage_meta)
    assert any("2018" in c.get("direct_answer","") for c in api.paa_engine._cached_candidates)
    doc["status"]="draft"
    assert client.post("/api/documents",json=doc).status_code==200
    assert api.index.total_docs==0
    assert not api.index.passages and not api.vector_index.passage_meta and not api.graph.nodes
    assert not api.paa_engine._cached_candidates
    assert client.get("/api/search",params={"q":"Zinnia"}).json()["results"]==[]


def test_hash_covers_exact_embedded_summary_and_model(tmp_path):
    from engine.indexing.document import Document
    doc=Document(id="x",slug="x",title="X",content="a"*550+"first")
    index=VectorIndex(DeterministicMockProvider(64),index_dir=tmp_path)
    original=index._hash_document(doc)
    doc.content="a"*550+"second"
    assert index._hash_document(doc)!=original
    other=VectorIndex(DeterministicMockProvider(128),index_dir=tmp_path)
    assert other._hash_document(doc)!=index._hash_document(doc)


def test_external_local_store_edit_invalidates_memory(tmp_path):
    from engine.indexing.document import Document
    a=DocumentStore(storage_path=tmp_path/"docs.json")
    b=DocumentStore(storage_path=tmp_path/"docs.json")
    doc=Document(id="x",slug="x",title="X",content="old value")
    a.save_document(doc)
    assert a.get_document("x").content=="old value"
    doc.content="new value with a different length"
    b.save_document(doc)
    assert a.get_document("x").content==doc.content


@pytest.mark.parametrize("stage", ["lexical", "semantic", "faq"])
def test_failed_publication_is_observable_and_recovers(tmp_path, monkeypatch, stage):
    import engine.api.main as api
    from engine.indexing.document import Document
    from engine.indexing.inverted_index import InvertedIndex
    for name in ["index", "graph", "link_auth", "engine", "vector_index", "autocomplete_engine",
                 "related_engine", "paa_engine", "family_registry", "active_snapshot", "publication_state"]:
        monkeypatch.setattr(api, name, getattr(api, name))
    monkeypatch.setattr(api, "publication_state", dict(api.publication_state))
    store = DocumentStore(tmp_path / "docs.json")
    monkeypatch.setattr(api, "store", store)
    monkeypatch.setattr(api, "vector_index", VectorIndex(DeterministicMockProvider(), tmp_path / "vectors"))
    store.save_document(Document(id="x", slug="x", title="Zinnia", content="Zinnia opened in 2001.", status="published"))
    store.save_document(Document(id="other", slug="other", title="Mercury", content="Mercury is a planet near the Sun.", status="published"))
    api.reload_search_pipeline()
    old = api.active_snapshot
    client = TestClient(api.app)
    def fail(*args, **kwargs):
        raise RuntimeError("injected failure")
    with monkeypatch.context() as injected:
        if stage == "lexical": injected.setattr(InvertedIndex, "index_document", fail)
        elif stage == "semantic": injected.setattr(VectorIndex, "build_index", fail)
        else: injected.setattr(api, "PAAQuestionEngine", fail)
        response = client.post("/api/documents", json=dict(id="x", slug="x", title="Zinnia", content="Zinnia opened in 2012.", status="draft"))
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "SAVED_NOT_INDEXED"
        assert api.active_snapshot is old
        assert old.index.documents["x"]["content"].endswith("2001.")
        assert client.get("/api/search", params={"q":"Zinnia"}).status_code == 503
        health = client.get("/health").json()
        assert health["status"] == "degraded"
        assert health["canonical_document_version"] != old.generation
        assert health["publication"]["last_error"] == "RuntimeError"
    api.reload_search_pipeline()
    assert client.get("/api/search", params={"q":"Zinnia"}).json()["results"] == []
    assert client.get("/health").json()["status"] == "healthy"
