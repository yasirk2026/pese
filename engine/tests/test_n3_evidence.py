from copy import deepcopy
from unittest.mock import patch
import pytest
from engine.intelligence.evidence import validate, digest, Readiness
from engine.intelligence.contexts import SearchContexts
from engine.search_sync.contracts import FeedbackEvent, NeuralShadowObservation, FeedbackSubmission
from engine.search_sync.feedback_store import SearchSyncFeedbackStore
from engine.search_sync.neural_shadow import PESERelationShadowAdapter
from engine.tests.test_neural_shadow import synthetic_shadow_engine, temp_sync_store


def record():
    return {"context_verified": True, "provenance": {"version": 1, "context_id": "c", "effective_query": "clock",
            "target_type": "SERP_RESULT", "target_id": "d", "document_revision": "rev",
            "evidence_id": "p", "evidence_hash": "hash", "ranking_version": "maae", "generation": "g",
            "model_versions": {"relation": "disabled"}}}


def test_evidence_does_not_invent_labels():
    assert validate({"feedback": "LIKE"}).classification == Readiness.PREFERENCE_ONLY
    r = record()
    assert validate(r).classification == Readiness.INCOMPLETE
    registry = {digest(r["provenance"])}
    assert validate(r, verified_contexts=registry).classification == Readiness.ADJUDICATION
    r["adjudication"] = {"reviewer": "editor", "receipt_hash": digest(r["provenance"]),
        "objective": "retrieval_relevance", "label": 1, "reviewed_at": "2026-10-27T00:00:00Z", "rationale": "Direct evidence"}
    assert validate(r, verified_contexts=registry).classification == Readiness.INCOMPLETE
    assert validate(r, verified_contexts=registry, trusted_reviewers={"editor"}).classification == Readiness.ADJUDICATED
    r["provenance"]["document_revision"] = "edited"
    assert validate(r, verified_contexts=registry, trusted_reviewers={"editor"}).classification == Readiness.INCOMPLETE


def observation(context="c", target_type="SERP_RESULT", evidence_id="p", probability=.99):
    return NeuralShadowObservation(search_context_id=context, target_type=target_type, target_id="d",
        query="clock", normalized_query="clock", checkpoint_hash="fixture", evidence_id=evidence_id,
        answers_probability=probability, does_not_answer_probability=1-probability, predicted_label="ANSWERS")


def vote(context="c", target_type="SERP_RESULT", feedback="DISLIKE"):
    return FeedbackEvent(search_context_id=context, target_type=target_type, target_id="d",
                         query="clock", normalized_query="clock", feedback=feedback)


def test_exact_diagnostics_and_repeats():
    s = SearchSyncFeedbackStore(":memory:")
    s.record_feedback(vote())
    s.record_neural_observations([observation("other"), observation(target_type="FEATURED_ANSWER")])
    assert s.get_neural_shadow_statistics()["linked_feedback_count"] == 0
    s.record_neural_observations([observation()])
    for _ in range(4):
        s.record_feedback(vote())
    stats = s.get_neural_shadow_statistics()
    assert stats["linked_feedback_count"] == 1
    assert stats["neural_human_agreements"] == 0
    assert stats["neural_human_disagreements"] == 1
    s.record_neural_observations([observation(evidence_id="p2")])
    assert s.get_feedback_with_neural_observations()[0]["provenance_status"] == "AMBIGUOUS"
    assert s.get_neural_shadow_statistics()["linked_feedback_count"] == 0


def test_disabled_observability_never_loads(monkeypatch):
    monkeypatch.setenv("PESE_REL_SHADOW_ENABLED", "false")
    a = PESERelationShadowAdapter()
    with patch.object(a, "_load_model_and_tokenizer", side_effect=AssertionError("disabled load")) as load:
        assert a.checkpoint_hash == "UNAVAILABLE"
        assert a.observe_candidates("q", "q", "c", [{"target_id": "d"}])[1] == []
        load.assert_not_called()


def test_cache_receipts_and_context_verification(synthetic_shadow_engine, monkeypatch):
    monkeypatch.setenv("PESE_REL_SHADOW_ENABLED", "false")
    engine, *_ = synthetic_shadow_engine
    query = "Who repaired the station clock?"
    first = engine.search(query, skip_qa=True, search_context_id="first")
    second = engine.search(query, skip_qa=True, search_context_id="second")
    assert [r.final_score for r in first] == [r.final_score for r in second]
    assert first[0].evidence_provenance["context_id"] == "first"
    assert second[0].evidence_provenance["context_id"] == "second"
    assert second.neural_shadow_trace["status"] == "CACHED_NOT_OBSERVED"
    contexts = SearchContexts()
    contexts.remember("second", query, second)
    request = FeedbackSubmission(query=query, target_type="SERP_RESULT", target_id=second[0].doc_id,
                                 search_context_id="second", feedback="LIKE")
    assert contexts.resolve(request)[0]["document_revision"]
    request.target_type = "FEATURED_ANSWER"
    request.target_id = "forged"
    with pytest.raises(ValueError):
        contexts.resolve(request)
    request.search_context_id = "expired"
    assert contexts.resolve(request) is None
