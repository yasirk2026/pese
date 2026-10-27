"""Evidence readiness v1: preference, provenance and reviewed truth stay separate.

Standalone: python -m engine.intelligence.evidence records.json
The caller supplies its trusted reviewer registry; records cannot self-authorize.
"""
import argparse
from dataclasses import dataclass
from enum import Enum
import hashlib
import json

VERSION = 1
RANKING_VERSION = "maae-alpha6-n3-contract1"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False, separators=(",", ":")).encode()).hexdigest()


class Readiness(str, Enum):
    PREFERENCE_ONLY = "preference_only"
    INCOMPLETE = "incomplete_or_ambiguous_provenance"
    ADJUDICATION = "eligible_for_human_adjudication"
    ADJUDICATED = "adjudicated_evidence"


@dataclass(frozen=True)
class Verdict:
    classification: Readiness
    reason: str
    version: int = VERSION


def validate(record, *, trusted_reviewers=frozenset(), verified_contexts=None):
    """Only a separately verified search receipt can establish provenance.

    A local UI vote never becomes a relevance/support label. A reviewed label is
    bound to a content fingerprint; changing evidence invalidates the review.
    """
    p = record.get("provenance")
    if not p:
        return Verdict(Readiness.PREFERENCE_ONLY, "No verified search receipt; vote is preference only")
    required = ("context_id", "effective_query", "target_type", "target_id", "document_revision",
                "evidence_id", "evidence_hash", "ranking_version", "generation", "model_versions")
    if p.get("version") != VERSION or any(not p.get(k) for k in required):
        return Verdict(Readiness.INCOMPLETE, "Missing versioned provenance")
    if p["target_type"] not in ("SERP_RESULT", "FEATURED_ANSWER"):
        return Verdict(Readiness.INCOMPLETE, "Invalid target type")
    if record.get("ambiguous") or record.get("context_verified") is not True:
        return Verdict(Readiness.INCOMPLETE, "Unverified or ambiguous search context")
    fingerprint = digest(p)
    if verified_contexts is None or fingerprint not in verified_contexts:
        return Verdict(Readiness.INCOMPLETE, "Receipt not in independently verified context registry")
    a = record.get("adjudication")
    if not a:
        return Verdict(Readiness.ADJUDICATION, "Verified context; human relevance review still required")
    if (a.get("reviewer") not in trusted_reviewers or a.get("receipt_hash") != fingerprint
            or a.get("objective") not in ("retrieval_relevance", "answer_support")
            or type(a.get("label")) is not int or a["label"] not in (0, 1)
            or not a.get("reviewed_at") or not a.get("rationale")):
        return Verdict(Readiness.INCOMPLETE, "Invalid or unauthorized adjudication")
    return Verdict(Readiness.ADJUDICATED, "Reviewed label bound to verified evidence")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records")
    args = parser.parse_args()
    # CLI intentionally cannot promote self-asserted receipts/reviewer identities.
    for record in json.loads(open(args.records, encoding="utf-8").read()):
        print(json.dumps(validate(record).__dict__))
