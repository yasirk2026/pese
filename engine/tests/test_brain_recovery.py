import json
import pytest
from pathlib import Path
from engine.brain.recovery import recover_knowledge_corpus
from engine.brain.lifecycle import initialize_brain


def test_recover_knowledge_corpus_into_fresh_brain(tmp_path: Path):
    # Initialize a new brain
    brain_dir = tmp_path / "test_brain"
    identity = initialize_brain(brain_dir, name="Test Recovery Brain", seed_documents=False)

    # Put a custom existing document in
    docs_file = brain_dir / "firestore_documents.json"
    custom_doc = {
        "id": "my-custom-doc",
        "slug": "my-custom-doc",
        "title": "My Custom Doc",
        "content": "Custom notes that must never be deleted",
        "content_schema_version": 1,
        "headings": [],
        "keywords": [],
        "internal_links": [],
        "source_type": "authored",
        "status": "published",
        "created_at": "2026-10-24T00:00:00Z",
        "updated_at": "2026-10-24T00:00:00Z"
    }
    with open(docs_file, "w", encoding="utf-8") as f:
        json.dump({"my-custom-doc": custom_doc}, f)

    # Run recovery
    result = recover_knowledge_corpus(brain_path=brain_dir)

    assert result["brain_id"] == identity.brain_id
    assert result["existing_before"] == 1
    assert result["new_imported"] == 212
    assert result["total_after"] == 213

    # Verify custom doc survived
    with open(docs_file, "r", encoding="utf-8") as f:
        recovered = json.load(f)
    assert "my-custom-doc" in recovered
    assert recovered["my-custom-doc"]["title"] == "My Custom Doc"
    assert "my-bicycle-story" in recovered
    assert "hiragana-notes" in recovered
