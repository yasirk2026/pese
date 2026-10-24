"""Match the documented CPU runtime; standalone neural tests must not oversubscribe."""
import pytest


@pytest.fixture
def public_discovery_store(tmp_path):
    from engine.indexing.store import DocumentStore
    from engine.evaluation.phase2f_support import document
    store = DocumentStore(tmp_path / "public-documents.json")
    docs = [
        document("what-is-pese", "What is PESE?", "PESE is a hybrid search engine using lexical and semantic retrieval.",
                 faqs=[{"id":"creator", "question":"Who created PESE?", "answer":"PESE was created by Morgan Vale."}]),
        document("what-is-pese-developed-with", "PESE implementation", "PESE is developed with Python. PESE uses a local web interface."),
        document("japanese-beginner-roadmap", "Japanese beginner roadmap", "## Hiragana vocabulary\nJapanese learners study hiragana vocabulary.\n\n## Kanji practice\nJapanese learners practice kanji.", internal_links=["hiragana-notes", "kanji-notes"]),
        document("kanji-notes", "Japanese kanji vocabulary", "Japanese kanji vocabulary practice supports reading.", internal_links=["japanese-beginner-roadmap"]),
        document("hiragana-notes", "Japanese hiragana notes", "## Japanese vocabulary\nHiragana represents Japanese syllables. Japanese vocabulary practice helps reading.", internal_links=["japanese-beginner-roadmap"]),
        document("bicycle", "Bicycle maintenance", "A bicycle has two wheels. Bicycle maintenance includes cleaning a chain."),
    ]
    for doc in docs: store.save_document(doc)
    return store


@pytest.fixture(scope="session",autouse=True)
def local_inference_thread_budget():
    import torch
    previous=torch.get_num_threads()
    torch.set_num_threads(2)
    yield
    torch.set_num_threads(previous)
