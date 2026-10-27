"""Experimental ordinal neural adjustment, after evidence eligibility only.

Model probabilities are not calibrated score units. Relative candidate order is
mapped onto a bounded fraction of the median adjacent deterministic score gap.
All adjustments commit atomically; any failure preserves the exact baseline.
"""
import math
import statistics
import sys
from pathlib import Path
from threading import Lock
from .isolation import infer_process


def bounded_adjustments(base_scores, neural_scores, *, relative_cap, gap_cap):
    if len(base_scores) != len(neural_scores) or not base_scores:
        raise ValueError("Model must score every budgeted candidate")
    if (any(not math.isfinite(s) or s < 0 for s in base_scores) or
            any(not math.isfinite(s) or not 0 <= s <= 1 for s in neural_scores) or
            not 0 <= relative_cap <= .03 or not 0 <= gap_cap <= .75):
        raise ValueError("Invalid model output or ranking bounds")
    unique = sorted(set(base_scores))
    gaps = [b-a for a,b in zip(unique, unique[1:])]
    scale = statistics.median(gaps) if gaps else 0
    n = len(neural_scores)
    result = []
    for base, score in zip(base_scores, neural_scores):
        # Ties receive their shared midrank. Monotonic calibration has no effect.
        below = sum(s < score for s in neural_scores)
        equal = sum(s == score for s in neural_scores)
        ordinal = 2*(below+(equal-1)/2)/(n-1)-1 if n > 1 else 0
        result.append(ordinal*min(abs(base)*relative_cap, scale*gap_cap))
    return result


class NeuralReranker:
    def __init__(self, approved_model=None, predictor=None):
        self.approved = approved_model
        self._predictor = predictor
        self._busy = Lock()

    @property
    def available(self):
        return self.approved is not None

    def adjust(self, candidates, query, *, enabled=False):
        if not enabled or not self.available:
            return {"status": "DISABLED", "authority": "NONE"}
        if not self._busy.acquire(blocking=False):
            return {"status": "BUSY_FALLBACK", "authority": "NONE"}
        try:
            budget = sorted(candidates, key=lambda c: c["base_score"], reverse=True)[:6]
            if not budget:
                return {"status": "EMPTY", "authority": "NONE"}
            if any(getattr(c["trace"], "evidence_gate_passed", False) is not True for c in budget):
                raise ValueError("Candidate was not admitted by the hard evidence gate")
            model = self.approved  # immutable request lease during model replacement
            command = [sys.executable, str(Path(__file__).with_name("worker.py"))]
            runner = self._predictor or infer_process
            scores, metrics = runner(command, {"directory": str(model.directory), "query": query[:500],
                      "evidence": [c["passage_text"][:8000] for c in budget],
                      "checkpoint_hash": model.checkpoint_hash, "tokenizer_hash": model.tokenizer_hash})
            changes = bounded_adjustments([c["base_score"] for c in budget], scores,
                                         relative_cap=model.relative_cap, gap_cap=model.gap_cap)
            for c, delta in zip(budget, changes):
                c["neural_adjustment"] = delta
                c["final_score"] = round(max(0, c["base_score"]+delta+c["search_sync_adjustment"]), 4)
                c["trace"].final_score = c["final_score"]
                c["trace"].neural_adjustment = delta
                c["trace"].neural_model_version = model.identity
            return {"status": "APPLIED", "authority": "BOUNDED_RANKING_ONLY", "model": model.identity,
                    "adjustments": {c["doc_id"]: d for c,d in zip(budget, changes)}, **metrics}
        except Exception:
            # No query, evidence, filesystem paths or native exception in logs.
            return {"status": "MODEL_FAILURE_FALLBACK", "authority": "NONE"}
        finally:
            self._busy.release()
