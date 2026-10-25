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

    # Recovery must be testable from public source without a personal development corpus.
    source = tmp_path / "synthetic-source.json"
    imported = {slug: dict(custom_doc, id=slug, slug=slug, title=slug)
                for slug in ("synthetic-engine-notes", "synthetic-language-notes")}
    source.write_text(json.dumps(imported), encoding="utf-8")
    result = recover_knowledge_corpus(brain_path=brain_dir, source_documents_path=source)

    assert result["brain_id"] == identity.brain_id
    assert result["existing_before"] == 1
    assert result["new_imported"] == 2
    assert result["total_after"] == 3

    # Verify custom doc survived
    with open(docs_file, "r", encoding="utf-8") as f:
        recovered = json.load(f)
    assert "my-custom-doc" in recovered
    assert recovered["my-custom-doc"]["title"] == "My Custom Doc"
    assert "synthetic-engine-notes" in recovered
    assert "synthetic-language-notes" in recovered
