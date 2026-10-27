"""Learning Evidence Evaluator v1. Hard provenance outranks advisory ML.

A trained advisory predictor may suggest a feedback meaning. Only an affirmative
human review bound to the immutable receipt can admit local supervised labels.
"""
from enum import Enum
import json
import math
from pathlib import Path
from ..evidence import digest


class Quality(str,Enum):
    VERIFIED="verified_training_evidence"
    CANDIDATE="high_quality_review_candidate"
    PREFERENCE="preference_only"
    AMBIGUOUS="ambiguous"
    CONTRADICTORY="contradictory"
    INVALID="invalid_or_untrusted"

RELEVANCE_REASONS={"not relevant","irrelevant","wrong result","wrong source"}
SUPPORT_REASONS={"wrong information","didn't answer my query","incomplete answer"}
PREFERENCE_REASONS={"duplicate","poor presentation","presentation","interesting","preferred layout"}


def assess(event,*,verified=False,current_revision=None,repeated=False,contradictory=False,review=None):
    receipt=event.get("receipt")
    required=("context_id","effective_query","target_type","target_id","document_revision","evidence_id","evidence_hash","model_versions")
    if not verified or not isinstance(receipt,dict) or any(not receipt.get(k) for k in required):
        return {"version":1,"quality":Quality.INVALID.value,"action":"reject","reason":"Missing server-validated presentation receipt"}
    if receipt["target_type"] not in ("SERP_RESULT","FEATURED_ANSWER"):
        return {"version":1,"quality":Quality.INVALID.value,"action":"reject","reason":"Unsupported target"}
    if current_revision is not None and current_revision!=receipt["document_revision"]:
        return {"version":1,"quality":Quality.INVALID.value,"action":"quarantine","reason":"Document revision is stale"}
    if repeated:
        return {"version":1,"quality":Quality.INVALID.value,"action":"deduplicate","reason":"Repeated action adds no independent weight"}
    if contradictory:
        return {"version":1,"quality":Quality.CONTRADICTORY.value,"action":"quarantine","reason":"Conflicting actions require explicit resolution"}
    if review:
        if (review.get("receipt_hash")==digest(event) and type(review.get("grade")) is int and
                review["grade"] in (0,1,2) and review.get("objective")=="retrieval_relevance" and
                review.get("reviewer")=="local_owner" and review.get("rationale")):
            return {"version":1,"quality":Quality.VERIFIED.value,"action":"accept_local_reviewed_supervision",
                    "reason":"Human reviewed this exact local receipt; not global authoritative truth"}
        return {"version":1,"quality":Quality.INVALID.value,"action":"reject","reason":"Review does not match this evidence"}
    reason=(event.get("reason") or "").strip().casefold()
    if reason in PREFERENCE_REASONS:
        quality,action=Quality.PREFERENCE,"preserve_preference"
    elif reason in RELEVANCE_REASONS and receipt["target_type"]=="SERP_RESULT" and event.get("evidence_text"):
        quality,action=Quality.CANDIDATE,"request_optional_review"
    elif reason in SUPPORT_REASONS or reason=="outdated":
        quality,action=Quality.AMBIGUOUS,"clarify_objective_or_revision"
    else:
        quality,action=Quality.AMBIGUOUS,"optional_clarification"
    return {"version":1,"quality":quality.value,"action":action,"reason":"A reaction/reason is not a supervised relevance label"}


def advisory_features(event):
    """No relevance predictions, raw document text or identity in quality features."""
    reason=(event.get("reason") or "").casefold()
    vocabulary=["irrelevant","not relevant","wrong result","wrong source","answer","information",
                "outdated","duplicate","presentation","interesting","layout","accident","other"]
    return [float(word in reason) for word in vocabulary]+[float(event.get("feedback")=="LIKE"),float(bool(reason))]


def advisory(event):
    path=Path(__file__).resolve().parents[2]/"neural/assets/feedback_judge_beta_v1.json"
    if not path.is_file():return {"status":"unavailable","admission_authority":"NONE"}
    data=json.loads(path.read_text(encoding="utf-8"));features=advisory_features(event)
    logits=[sum(w*x for w,x in zip(row,features))+b for row,b in zip(data["weights"],data["bias"])]
    values=[math.exp(v-max(logits)) for v in logits];probabilities=[v/sum(values) for v in values]
    index=max(range(3),key=probabilities.__getitem__)
    return {"status":"advisory_only","suggested_meaning":["relevance_review","preference","ambiguous"][index],
            "raw_confidence":probabilities[index],"calibration":"synthetic_feature_contract_only_not_independently_validated",
            "admission_authority":"NONE"}
