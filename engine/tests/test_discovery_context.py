"""Real retrieval and Answerability Gate integration on a public fixture corpus."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def discovery_client(public_discovery_store, monkeypatch):
    from engine.api import main
    for name in ("store", "index", "graph", "link_auth", "engine", "vector_index", "active_snapshot",
                 "autocomplete_engine", "related_engine", "paa_engine", "family_registry", "publication_state"):
        monkeypatch.setattr(main, name, getattr(main, name))
    monkeypatch.setattr(main, "store", public_discovery_store)
    monkeypatch.setattr(main, "publication_state", dict(main.publication_state))
    main.reload_search_pipeline()
    return TestClient(main.app)


@pytest.mark.parametrize("debug", [False, True])
def test_primary_context_feeds_grounded_discovery(discovery_client, debug):
    client = discovery_client
    primary = client.get("/api/search", params={"q":"what is PESE", "debug":debug})
    assert primary.status_code == 200
    assert primary.json()["results"]
    search_id = primary.json()["search_id"]
    questions = client.get("/api/questions", params={"q":"what is PESE", "search_id":search_id})
    related = client.get("/api/related", params={"q":"what is PESE", "search_id":search_id})
    assert questions.status_code == related.status_code == 200
    for item in questions.json()["questions"]:
        assert item["answerability_status"] == "PASS"
        assert item["source_slug"] and item["answer"]
        verified = client.get("/api/search", params={"q":item["question"]}).json()["results"][0]
        assert verified["is_featured"]
        assert verified["slug"] == item["source_slug"]
    # This fixture's PESE document has no graph neighbors; emptiness is legitimate.
    assert isinstance(related.json()["related_searches"], list)


def test_related_searches_renderable_for_graph_connected_corpus(discovery_client):
    query = "Japanese beginner roadmap"
    primary = discovery_client.get("/api/search", params={"q":query}).json()
    related = discovery_client.get("/api/related", params={"q":query,"search_id":primary["search_id"]})
    assert related.status_code == 200
    assert related.json()["related_searches"]


def test_discovery_context_rejects_wrong_query_and_unknown_generation(discovery_client):
    search_id = discovery_client.get("/api/search", params={"q":"Japanese beginner roadmap"}).json()["search_id"]
    for path in ("/api/questions", "/api/related"):
        assert discovery_client.get(path, params={"q":"other", "search_id":search_id}).status_code == 409
        assert discovery_client.get(path, params={"q":"Japanese beginner roadmap", "search_id":"unknown"}).status_code == 409


def test_unanswerable_discovery_remains_empty(discovery_client):
    query = "which planet contains my nonexistent secret spaceship"
    primary = discovery_client.get("/api/search", params={"q":query}).json()
    result = discovery_client.get("/api/questions", params={"q":query,"search_id":primary["search_id"]})
    assert result.status_code == 200
    assert result.json()["questions"] == []
