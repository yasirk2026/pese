"""Per-Brain privacy permissions, outside canonical snapshot allowlists.

No research collection, journal training, parameter update or upload is implied
by indexing. Existing exact-query Search Sync preferences retain compatibility.
"""
from pathlib import Path
from threading import RLock
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from ..brain.atomic import atomic_write_json

_PERMISSION_LOCK = RLock()


class IntelligenceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(default=1, ge=1, le=1)
    neural_search: StrictBool = False
    learn_from_feedback: StrictBool = True  # existing N3-A explicit preference behavior
    collect_research_feedback: StrictBool = False
    allow_journal_learning: StrictBool = False
    community_contributions: StrictBool = False
    consent_revision: int = Field(default=0, ge=0)
    excluded_document_ids: list[str] = Field(default_factory=list, max_length=10000)

    def permits_document(self, doc_id, *, journal=False):
        return (self.collect_research_feedback and self.learn_from_feedback and
                doc_id not in self.excluded_document_ids and (not journal or self.allow_journal_learning))


class SettingsStore:
    def __init__(self, brain_root):
        self.root = Path(brain_root) / ".pese-intelligence-v1"
        self.path = self.root / "permissions.json"
        self._lock = _PERMISSION_LOCK

    def read(self):
        with self._lock:
            if not self.path.exists():
                return IntelligenceSettings()
            try:
                return IntelligenceSettings.model_validate_json(self.path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                # Corrupt permissions never grant processing or transmission.
                return IntelligenceSettings(learn_from_feedback=False)

    def update(self, changes, *, neural_available=False):
        with self._lock:
            if "consent_revision" in changes or "version" in changes:
                raise ValueError("Permission version/revision are server-owned")
            previous = self.read()
            settings = IntelligenceSettings.model_validate({**previous.model_dump(), **changes})
            if settings.community_contributions != previous.community_contributions:
                settings.consent_revision += 1
            if settings.neural_search and not neural_available:
                raise ValueError("No independently accepted neural relevance model is installed")
            atomic_write_json(self.path, settings.model_dump())
            return settings


def runtime_settings():
    from ..config import RUNTIME_ROOT
    return SettingsStore(RUNTIME_ROOT)


# Lazy proxy; merely importing the module must not resolve or mutate a Brain.
class _RuntimeSettings:
    def read(self):
        return runtime_settings().read()
    def update(self, *args, **kwargs):
        return runtime_settings().update(*args, **kwargs)


intelligence_settings = _RuntimeSettings()
