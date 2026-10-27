from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import time
from unittest.mock import patch
import pytest
from engine.intelligence.evaluation import ranking_metrics, paired_report, calibration
from engine.intelligence.reranking import bounded_adjustments, NeuralReranker
from engine.intelligence.isolation import infer_process
from engine.intelligence.model_release import ApprovedModel
from engine.tests.test_neural_shadow import synthetic_shadow_engine, temp_sync_store


def approved():
    return ApprovedModel(Path("fixture"), "fixture:1", "a"*64, "b"*64, .03, .75)


def test_bounded_ordinal_normalization():
    assert bounded_adjustments([10,9.9], [.1,.9], relative_cap=.03, gap_cap=.75) == pytest.approx([-.075,.075])
    assert bounded_adjustments([10,9.9], [.1,.9], relative_cap=.03, gap_cap=.75) == pytest.approx(
        bounded_adjustments([10,9.9], [.001,.999], relative_cap=.03, gap_cap=.75))
    assert bounded_adjustments([10,10], [.1,.9], relative_cap=.03, gap_cap=.75) == [0,0]
    assert bounded_adjustments([10,9.9], [.9,.9], relative_cap=.03, gap_cap=.75) == [0,0]
    for scores in ([float("nan"),1], [float("inf"),1], [1.1,.5], [.3]):
        with pytest.raises(ValueError):
            bounded_adjustments([10,9.9], scores, relative_cap=.03, gap_cap=.75)


def test_disabled_no_process_and_failure_atomicity():
    rows = [{"doc_id": str(i), "base_score": 10-i*.1, "final_score": 10-i*.1,
             "passage_text": "synthetic", "search_sync_adjustment": 0,
             "trace": SimpleNamespace(final_score=10-i*.1,evidence_gate_passed=True)} for i in range(2)]
    before = deepcopy(rows)
    ranker = NeuralReranker(approved())
    with patch("engine.intelligence.reranking.infer_process", side_effect=AssertionError("should not load")) as loader:
        assert ranker.adjust(rows,"q")["status"] == "DISABLED"
        loader.assert_not_called()
    for failure in (TimeoutError(), RuntimeError(), ValueError()):
        with patch("engine.intelligence.reranking.infer_process", side_effect=failure):
            assert ranker.adjust(rows,"q",enabled=True)["authority"] == "NONE"
        assert rows == before
    rejected=deepcopy(rows); rejected[0]["trace"].evidence_gate_passed=False
    with patch("engine.intelligence.reranking.infer_process") as loader:
        assert ranker.adjust(rejected,"q",enabled=True)["authority"] == "NONE"
        loader.assert_not_called()
    for scores in ([.2], [.2,float("nan")], [.5,1.01]):
        with patch("engine.intelligence.reranking.infer_process", return_value=(scores, {})):
            assert ranker.adjust(rows,"q",enabled=True)["authority"] == "NONE"
        assert rows == before


def test_justified_fixture_changes_actual_eligible_order(synthetic_shadow_engine, monkeypatch):
    # Controlled integration proof only. This is not model quality/acceptance evidence.
    engine, *_ = synthetic_shadow_engine
    monkeypatch.setenv("PESE_REL_SHADOW_ENABLED", "false")
    query = "Who repaired the station clock?"
    baseline = engine.search(query, skip_qa=True)
    assert len(baseline) >= 2
    ranker = NeuralReranker(approved())
    engine.neural_ranker = ranker
    monkeypatch.setattr(engine,"_neural_search_enabled",lambda:True)
    # Gap-bounded adjustment can only swap close candidates. Scale their base
    # scores inside the scorer by a test seam, preserving eligibility membership.
    original = ranker.adjust
    def close_scores(candidates, q, **kwargs):
        for i,c in enumerate(candidates):
            c["base_score"] = 10-i*.1
            c["final_score"] = c["base_score"]
            c["search_sync_adjustment"] = 0
        return original(candidates,q,**kwargs)
    monkeypatch.setattr(ranker,"adjust",close_scores)
    engine.invalidate_query_cache()
    with patch("engine.intelligence.reranking.infer_process", return_value=([.01,.99],{})):
        changed = engine.search(query,skip_qa=True)
    assert changed[0].doc_id == baseline[1].doc_id
    assert set(r.doc_id for r in changed) == set(r.doc_id for r in baseline)
    assert all(r.trace.evidence_gate_passed for r in changed)
    assert changed.hybrid_trace["neural_ranking"]["authority"] == "BOUNDED_RANKING_ONLY"


def test_true_native_hang_crash_invalid_output_and_memory_budget():
    start = time.monotonic()
    with pytest.raises(Exception):
        infer_process([sys.executable,"-c","import time; time.sleep(60)"],{},timeout_seconds=.15)
    assert time.monotonic()-start < 5
    with pytest.raises(RuntimeError):
        infer_process([sys.executable,"-c","raise SystemExit(7)"],{})
    with pytest.raises(ValueError):
        infer_process([sys.executable,"-c","print('invalid')"],{})
    with pytest.raises(RuntimeError):
        infer_process([sys.executable,"-c","import time; x=bytearray(20*1024*1024); time.sleep(2)"],{},memory_bytes=1)
    scores, metrics = infer_process([sys.executable,"-c","print('[0.2,0.8]')"],{})
    assert scores == [.2,.8] and metrics["latency_ms"] > 0


def test_metrics_require_judgments_and_paired_uncertainty():
    assert ranking_metrics(["a","b"],{"a":1,"b":0})["mrr"] == 1
    with pytest.raises(ValueError):
        ranking_metrics(["a","unclicked"],{"a":1})
    report = paired_report([{"baseline":["b","a"],"candidate":["a","b"],"judgments":{"a":1,"b":0},"category":"fixture","group":"fixture"}])
    assert report["paired_lower95"] > 0
    assert calibration([0,1],[0,1])["ece"] == 0
