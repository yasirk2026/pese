"""
PESE Brain Storage Contract: Data Structures and Identity Schema
Defines the portable, platform-neutral PESE Brain identity format, status types,
and domain exceptions.
"""

from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict


BRAIN_FORMAT_IDENTIFIER = "pese-brain"
CURRENT_SCHEMA_VERSION = 1
BRAIN_MANIFEST_FILENAME = "pese-brain.json"


class BrainStatus(str, Enum):
    """Runtime lifecycle status of a PESE Brain."""
    ACTIVE = "active"
    MISSING = "missing"
    INVALID = "invalid"
    UNINITIALIZED = "uninitialized"
    READ_ONLY = "read_only"


class BrainIdentity(BaseModel):
    """
    Portable, platform-neutral Brain identity manifest.
    Stored on disk as 'pese-brain.json'.
    Contains ZERO machine-specific or absolute path data.
    """
    model_config = ConfigDict(populate_by_name=True)

    format: str = Field(default=BRAIN_FORMAT_IDENTIFIER, description="Format magic identifier")
    schema_version: int = Field(default=CURRENT_SCHEMA_VERSION, alias="schemaVersion", description="Brain contract schema version")
    brain_id: str = Field(..., alias="brainId", description="Globally unique canonical Brain UUID")
    created_at: str = Field(..., alias="createdAt", description="UTC ISO-8601 creation timestamp")
    name: Optional[str] = Field(default=None, description="Optional user-facing friendly name for this Brain")
    app_compatibility: Optional[Dict[str, Any]] = Field(default=None, alias="appCompatibility", description="Optional minimal application compatibility metadata")

    @classmethod
    def create_new(cls, name: Optional[str] = None) -> "BrainIdentity":
        """Factory for generating a new Brain identity with fresh UUID and UTC timestamp."""
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return cls(
            brain_id=uuid4().hex,
            created_at=now_iso,
            name=name
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict with camelCase keys matching the on-disk JSON contract."""
        data = {
            "format": self.format,
            "schemaVersion": self.schema_version,
            "brainId": self.brain_id,
            "createdAt": self.created_at
        }
        if self.name is not None:
            data["name"] = self.name
        if self.app_compatibility is not None:
            data["appCompatibility"] = self.app_compatibility
        return data


class BrainInfo(BaseModel):
    """Structured information returned when opening an existing Brain."""
    brain_id: str
    schema_version: int
    created_at: str
    name: Optional[str] = None
    path: str
    status: BrainStatus
    document_count: int = 0
    has_feedback_db: bool = False
    has_privacy_settings: bool = False
    has_history_log: bool = False


# =============================================================================
# DOMAIN EXCEPTIONS (Strict separation of error states)
# =============================================================================

class BrainError(Exception):
    """Base exception for all PESE Brain storage and lifecycle operations."""
    pass


class BrainMissingError(BrainError):
    """
    Raised when a configured Brain path does not exist on disk
    (e.g. external drive disconnected, unmounted, or changed drive letter).
    CRITICAL: Must NEVER trigger silent fallback or auto-creation of a new Brain.
    """
    def __init__(self, path: Path, message: Optional[str] = None):
        self.path = Path(path)
        default_msg = f"Configured PESE Brain path could not be found at: {self.path}. Drive may be disconnected or unmounted."
        super().__init__(message or default_msg)


class BrainNotConfiguredError(BrainError):
    """Raised when no Brain path has been configured on the local system."""
    pass


class BrainInvalidError(BrainError):
    """Raised when a directory exists but does not contain a valid or supported PESE Brain."""
    def __init__(self, path: Path, reason: str):
        self.path = Path(path)
        self.reason = reason
        super().__init__(f"Invalid PESE Brain at '{self.path}': {reason}")


class BrainConflictError(BrainError):
    """Raised when attempting to initialize a new Brain in a directory that already contains one."""
    def __init__(self, path: Path):
        self.path = Path(path)
        super().__init__(f"Cannot initialize new Brain: An existing PESE Brain was detected at '{self.path}'. Existing data must not be overwritten.")


class BrainPermissionError(BrainError):
    """Raised when the process does not have read/write access to the Brain directory."""
    def __init__(self, path: Path, reason: str):
        self.path = Path(path)
        self.reason = reason
        super().__init__(f"Permission error accessing Brain at '{self.path}': {reason}")


class BrainSecurityError(BrainError):
    """Raised when an unsafe directory (such as application installation or runtime) is selected."""
    def __init__(self, path: Path, reason: str):
        self.path = Path(path)
        self.reason = reason
        super().__init__(f"Security violation for Brain directory '{self.path}': {reason}")
