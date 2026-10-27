"""Contribution contract v1: reviewed coarse diagnostics only, never text/labels.

No HTTP client or background uploader exists. Export consent is distinct from
future transmission consent. Aggregates are minimized, not claimed anonymous.
"""
from copy import deepcopy
from datetime import datetime, timezone
from enum import Enum
import json
from threading import RLock
import time
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from .evidence import digest

MAX_BYTES = 16384


class Category(str, Enum):
    MODEL_HIGH_HUMAN_DISLIKE = "model_high_human_dislike"
    MODEL_LOW_HUMAN_LIKE = "model_low_human_like"
    INCOMPLETE_PROVENANCE = "incomplete_provenance"


class Diagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Category
    count_bucket: Literal["5-9", "10-19", "20-49", "50+"]


class ExportConsent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    reviewed: StrictBool
    purpose: Literal["reviewable_local_export_for_future_model_improvement"]
    includes_text: Literal[False] = False
    # No assertion of upload authorization. A future transport requires a new
    # recipient-specific preview, retention disclosure and affirmative action.
    upload_authorized: Literal[False] = False


class Contribution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["pese-contribution"] = "pese-contribution"
    version: Literal[1] = 1
    app_version: Literal["0.1.0-alpha.6"] = "0.1.0-alpha.6"
    model_version: Literal["PESE-Rel-0:frozen:shadow"] = "PESE-Rel-0:frozen:shadow"
    diagnostics: list[Diagnostic] = Field(max_length=3)
    consent: ExportConsent


def parse_package(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError("Contribution size limit exceeded")
    def unique(pairs):
        value = {}
        for k,v in pairs:
            if k in value:
                raise ValueError("Duplicate JSON field")
            value[k] = v
        return value
    data = json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")))
    if not isinstance(data,dict) or set(data) != set(Contribution.model_fields) or type(data.get("version")) is not int:
        raise ValueError("Explicit complete versioned envelope required")
    consent=data.get("consent")
    if (not isinstance(consent,dict) or set(consent) != set(ExportConsent.model_fields) or
            type(consent.get("version")) is not int or type(consent.get("includes_text")) is not bool or
            type(consent.get("upload_authorized")) is not bool):
        raise ValueError("Explicit typed review consent required")
    package = Contribution.model_validate(data)
    if not package.consent.reviewed:
        raise ValueError("Per-export review consent missing")
    if len({d.category for d in package.diagnostics}) != len(package.diagnostics):
        raise ValueError("Duplicate diagnostic category")
    return package


def bucket(count):
    return "50+" if count >= 50 else "20-49" if count >= 20 else "10-19" if count >= 10 else "5-9" if count >= 5 else None


class ExportReview:
    def __init__(self, settings_store, feedback_store):
        self.settings_store = settings_store
        self.feedback_store = feedback_store
        self._previews = {}
        self._lock = RLock()

    def preview(self):
        permissions = self.settings_store.read()
        if not permissions.community_contributions:
            raise ValueError("Community contributions are disabled")
        joins = self.feedback_store.get_feedback_with_neural_observations()
        counts = {Category.MODEL_HIGH_HUMAN_DISLIKE: 0, Category.MODEL_LOW_HUMAN_LIKE: 0,
                  Category.INCOMPLETE_PROVENANCE: 0}
        # Active votes only. Never treat repeat clicks or weak feedback as labels.
        for item in joins:
            alignment = item["diagnostic_alignment"]
            if alignment == "NEURAL HIGH / HUMAN DISLIKE":
                counts[Category.MODEL_HIGH_HUMAN_DISLIKE] += 1
            if alignment == "NEURAL LOW / HUMAN LIKE":
                counts[Category.MODEL_LOW_HUMAN_LIKE] += 1
            if item.get("provenance_status") != "VERIFIED":
                counts[Category.INCOMPLETE_PROVENANCE] += 1
        package = Contribution(diagnostics=[Diagnostic(category=k, count_bucket=bucket(v)) for k,v in counts.items() if bucket(v)],
            consent=ExportConsent(reviewed=True, purpose="reviewable_local_export_for_future_model_improvement"))
        body = package.model_dump(mode="json")
        # Do not claim review before the user affirms it on the export endpoint.
        body["consent"]["reviewed"] = False
        preview_id = uuid4().hex
        with self._lock:
            self._previews = {k:v for k,v in self._previews.items() if time.monotonic()-v[0] < 600}
            if len(self._previews) >= 8:
                self._previews.pop(next(iter(self._previews)))
            self._previews[preview_id] = (time.monotonic(), deepcopy(body), permissions.consent_revision)
        return {"preview_id": preview_id, "sha256": digest(body), "package": body,
                "destination": "Local JSON download only; no configured upload recipient",
                "retention": "You control the exported file. No server receives this export.",
                "revocation": "Turning contributions off prevents new exports. It cannot recall files you later share.",
                "privacy": "No text, queries, documents, embeddings, Brain IDs or device IDs. Minimized aggregates are not guaranteed anonymous."}

    def cancel(self, preview_id):
        with self._lock:
            self._previews.pop(preview_id, None)

    def export(self, preview_id, expected_hash, reviewed):
        with self._lock:
            permissions = self.settings_store.read()
            if not permissions.community_contributions:
                self._previews.clear()
                raise ValueError("Consent revoked")
            entry = self._previews.get(preview_id)
            if not entry or time.monotonic()-entry[0] >= 600 or entry[2] != permissions.consent_revision:
                raise ValueError("Preview expired or cancelled")
            body = deepcopy(entry[1])
            if reviewed is not True or expected_hash != digest(body):
                raise ValueError("Review the exact preview before export")
            body["consent"]["reviewed"] = True
            parse_package(json.dumps(body).encode())
            self._previews.pop(preview_id)
            return body


class ContributionEndpoint:
    """Transport seam. Production has no verified destination or credentials."""
    def submit(self, package):
        raise RuntimeError("External contribution transport is not configured or authorized")
