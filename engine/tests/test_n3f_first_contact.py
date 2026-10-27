"""FIRST CONTACT admission and recoverability, using disposable Brains only."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from research.first_contact_english import draft
from scripts.n3f_evaluate import validate
from scripts.n3f_owner_safety import inventory, run


def test_protected_evaluation_refuses_unreviewed_and_incomplete_truth():
    packet = draft()
    assert validate(packet, diagnostic=True)
    with pytest.raises(ValueError, match="human review"):
        validate(packet)
    # A labelled policy fixture, never an actual human review or evaluation result.
    packet["role"] = "protected_evaluation_never_train"
    packet["human_review"] = {"approved": True, "reviewer": "fixture reviewer", "reviewed_at": "2026-10-27T00:00:00Z",
                              "basis": "human_checked_source_evidence_and_all_labels"}
    for q in packet["questions"]:
        q.update(grades=q["proposed_grades"].copy(), answer_reviewed=True, expected_answer=q["proposed_expected_answer"])
    assert validate(packet)
    broken = deepcopy(packet)
    broken["human_review"]["reviewer"] = "Neural Genesis"
    with pytest.raises(ValueError, match="named human"):
        validate(broken)
    broken = deepcopy(packet)
    broken["questions"][0]["grades"].pop("keys-b")
    with pytest.raises(ValueError, match="unjudged"):
        validate(broken)
    broken = deepcopy(packet)
    broken["questions"][0]["answer_reviewed"] = False
    with pytest.raises(ValueError, match="abstention"):
        validate(broken)


def test_protected_evaluation_rejects_exposed_development_wording():
    from engine.intelligence.beta.data import build_splits
    packet = draft()
    packet["questions"][0]["question"] = build_splits()["train"][0]["question"]
    with pytest.raises(ValueError, match="overlaps"):
        validate(packet, diagnostic=True)


def test_metadata_only_g1_roundtrip_preserves_original_and_pointer(tmp_path, monkeypatch):
    # The CLI intentionally isolates its environment; restore it for other tests.
    import os
    for name in ("LOCALAPPDATA", "PESE_BRAIN_PATH", "PESE_DATA_DIR"):
        monkeypatch.setenv(name, os.getenv(name, ""))
    from engine.brain import initialize_brain
    from engine.indexing.document import Document
    from engine.indexing.store import DocumentStore
    brain = tmp_path / "original"
    initialize_brain(brain)
    DocumentStore(brain / "firestore_documents.json").save_document(
        Document(id="fixture", slug="fixture", title="Private sentinel", content="SENTINEL_TEXT_MUST_NOT_APPEAR_IN_RECEIPT"))
    pointer = tmp_path / "desktop-settings.json"
    pointer.write_text(json.dumps({"brainPath": str(brain)}))
    install = tmp_path / "install"
    install.mkdir()
    for name in ("PESE.exe", "PESE.dll"):
        (install / name).write_bytes(b"synthetic fixture")
    (install / "source-provenance.json").write_text(json.dumps({"version": "fixture", "commit": "0" * 40}))
    before = inventory(brain)
    assert run(pointer, install, tmp_path / "safety") == 0
    assert before == inventory(brain)
    receipt = (tmp_path / "safety/safety-receipt.json").read_text()
    assert "SENTINEL_TEXT" not in receipt and "Private sentinel" not in receipt
    assert all(json.loads(receipt)["checks"].values())
    with pytest.raises(ValueError, match="fresh"):
        run(pointer, install, tmp_path / "safety")
