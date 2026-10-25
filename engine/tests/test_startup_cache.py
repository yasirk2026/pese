"""Rebuild cache durability/readiness tests; no active Brain or network."""
import asyncio
import json
from types import SimpleNamespace

import numpy as np
import pytest
from engine.indexing.document import Document
from engine.passages.extractor import PassageExtractor
from engine.semantic.index import VectorIndex
from engine.semantic.provider import DeterministicMockProvider, FastembedProvider
from engine.startup_progress import embedding_phase


def test_completed_cache_survives_a_new_index_instance(tmp_path):
    class Counted(DeterministicMockProvider):
        calls = 0
        def embed_texts(self, texts):
            self.calls += 1
            return super().embed_texts(texts)
    provider = Counted(64)
    doc = Document(id="x", slug="x", title="Synthetic engine", content="A synthetic engine keeps local notes.")
    passages = {doc.id: PassageExtractor().extract_passages(doc)}
    original = VectorIndex(provider, tmp_path)
    original.build_index([doc], passages, persist=False)
    assert provider.calls > 0
    assert original._save_cache()
    restarted = VectorIndex(provider, tmp_path)
    provider.calls = 0
    restarted.build_index([doc], passages, persist=False)
    assert provider.calls == 0 and restarted.cache_misses == 0
    np.testing.assert_array_equal(original.passage_vectors, restarted.passage_vectors)
    np.testing.assert_array_equal(original.doc_vectors, restarted.doc_vectors)


def test_failed_cache_replace_preserves_old_bytes(tmp_path, monkeypatch):
    index = VectorIndex(DeterministicMockProvider(4), tmp_path)
    index._hash_cache = {"a" * 64: np.ones(4, dtype=np.float32)}
    assert index._save_cache()
    old = (tmp_path / "cache_store.npz").read_bytes()
    index._hash_cache = {"b" * 64: np.zeros(4, dtype=np.float32)}
    def fail(*args):
        raise OSError("controlled replacement failure")
    monkeypatch.setattr("engine.semantic.index.os.replace", fail)
    assert not index._save_cache()
    assert (tmp_path / "cache_store.npz").read_bytes() == old
    assert not list(tmp_path.glob(".cache-*.npz"))


def test_interrupted_cache_write_preserves_previous_generation(tmp_path, monkeypatch):
    index = VectorIndex(DeterministicMockProvider(4), tmp_path)
    index._hash_cache = {"a" * 64: np.ones(4, dtype=np.float32)}
    assert index._save_cache()
    old = (tmp_path / "cache_store.npz").read_bytes()
    def interrupt(stream, **kwargs):
        stream.write(b"partial")
        raise KeyboardInterrupt()
    monkeypatch.setattr("engine.semantic.index.np.savez_compressed", interrupt)
    with pytest.raises(KeyboardInterrupt):
        index._save_cache()
    assert (tmp_path / "cache_store.npz").read_bytes() == old
    assert not list(tmp_path.glob(".cache-*.npz"))


def test_progress_preserves_vector_values_and_contains_no_text(monkeypatch, capsys):
    rows = [np.array([1, 2, 3], dtype=np.float32), np.array([3, 2, 1], dtype=np.float32)]
    class Model:
        def embed(self, texts):
            yield from rows
    provider = FastembedProvider()
    provider._model = Model()
    monkeypatch.setenv("PESE_STARTUP_PROGRESS", "1")
    with embedding_phase("passages"):
        actual = provider.embed_texts(["synthetic private phrase", "another synthetic phrase"])
    expected = np.array(rows, dtype=np.float32)
    expected /= np.linalg.norm(expected, axis=1, keepdims=True)
    np.testing.assert_array_equal(actual, expected)
    output = capsys.readouterr().out
    assert "phrase" not in output
    events = [json.loads(line.removeprefix("PESE_STARTUP ")) for line in output.splitlines()]
    assert events == [{"stage": "passages", "completed": 0, "total": 2}, {"stage": "passages", "completed": 2, "total": 2}]


def test_unusable_semantic_model_never_reaches_readiness(monkeypatch):
    from engine.api import main as api
    def fail(query):
        raise RuntimeError("controlled local model failure")
    monkeypatch.setattr(api, "store", SimpleNamespace(list_documents=lambda: ["synthetic"]))
    monkeypatch.setattr(api, "reload_search_pipeline", lambda: None)
    monkeypatch.setattr(api, "vector_index", SimpleNamespace(provider=SimpleNamespace(embed_query=fail)))
    async def run():
        async with api.lifespan(api.app):
            pytest.fail("readiness must not be reached")
    with pytest.raises(RuntimeError, match="search is not ready"):
        asyncio.run(run())


def test_private_empty_brain_stays_empty_during_startup(tmp_path, monkeypatch):
    from engine.api import main as api
    from engine.indexing.store import DocumentStore
    for name in ("store", "vector_index", "index", "graph", "link_auth", "engine", "active_snapshot",
                 "autocomplete_engine", "related_engine", "paa_engine", "family_registry", "publication_state"):
        monkeypatch.setattr(api, name, getattr(api, name))
    store = DocumentStore(tmp_path / "documents.json")
    monkeypatch.setattr(api, "store", store)
    monkeypatch.setattr(api, "vector_index", VectorIndex(DeterministicMockProvider(), tmp_path / "vectors"))
    monkeypatch.setattr(api, "publication_state", dict(api.publication_state))
    monkeypatch.setattr(api, "DEMO", False)
    def unexpected_seed(*args):
        pytest.fail("Private Brain contents must not be replaced by demo notes")
    monkeypatch.setattr(api, "seed_demo", unexpected_seed)
    async def run():
        async with api.lifespan(api.app):
            assert store.list_documents() == []
            assert api.health_check()["status"] == "healthy"
            assert api.health_check()["documents_indexed"] == 0
    asyncio.run(run())
