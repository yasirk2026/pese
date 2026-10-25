"""
PESE Google Drive Sync Contracts: Data Structures, Enums, and Domain Exceptions.
Platform-independent and neutral schema for Windows Desktop and future Android clients.
"""

from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from ..app_version import application_version


SYNC_FORMAT_VERSION = 2
SYNC_MANIFEST_FILENAME = "pese-sync-manifest.json"
CURRENT_APP_VERSION = application_version()
CURRENT_SCHEMA_VERSION = 1

GOOGLE_DRIVE_APPDATA_SCOPE = "https://www.googleapis.com/auth/drive.appdata"
OAUTH_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
OAUTH_REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
DRIVE_FILES_ENDPOINT = "https://www.googleapis.com/drive/v3/files"
DRIVE_UPLOAD_ENDPOINT = "https://www.googleapis.com/upload/drive/v3/files"


class SyncConnectionStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    NOT_CONNECTED = "not_connected"
    CONNECTED = "connected"
    SYNCING = "syncing"
    ERROR = "error"
    CONNECTING = "connecting"


class FileChecksumInfo(BaseModel):
    """File metadata and checksum inside a PESE snapshot bundle."""
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    relative_path: str = Field(..., alias="relativePath", description="Portable relative path (forward-slash only)")
    sha256: str = Field(..., pattern="^[0-9a-f]{64}$", description="SHA-256 checksum of the file")
    size_bytes: int = Field(..., ge=0, alias="sizeBytes", description="Size in bytes")
    category: str = Field(..., description="Logical data category")

    @field_validator("relative_path")
    @classmethod
    def validate_portable_path(cls, v: str) -> str:
        if "\\" in v:
            raise ValueError(f"Path must not contain Windows backslashes: {v}")
        if v.startswith("/") or (len(v) > 1 and v[1] == ":"):
            raise ValueError(f"Path must not be absolute: {v}")
        parts = v.split("/")
        if ".." in parts or "." in parts or "" in parts:
            raise ValueError(f"Path must not contain traversal or empty segments: {v}")
        return v


class SnapshotIntegrity(BaseModel):
    """Integrity summary for the entire snapshot."""
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    algorithm: str = "sha256"
    total_files: int = Field(..., alias="totalFiles")
    total_bytes: int = Field(..., alias="totalBytes")
    content_digest: Optional[str] = Field(default=None, alias="contentDigest")


class PESESyncManifest(BaseModel):
    """
    Authoritative PESE snapshot manifest ('pese-sync-manifest.json').
    Device-neutral, portable, platform-independent contract.
    """
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    sync_format_version: int = Field(..., alias="syncFormatVersion")
    app_version: str = Field(..., alias="appVersion")
    brain_id: str = Field(..., alias="brainId")
    snapshot_id: str = Field(..., alias="snapshotId")
    created_at: str = Field(..., alias="createdAt")
    schema_version: int = Field(..., alias="schemaVersion")
    categories: List[str] = Field(default_factory=list)
    files: Dict[str, FileChecksumInfo] = Field(default_factory=dict)
    integrity: SnapshotIntegrity

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True)


class SnapshotBundle(BaseModel):
    """Runtime representation of a created or inspected snapshot bundle."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    snapshot_id: str
    brain_id: str
    zip_path: Path
    zip_sha256: str
    total_size_bytes: int
    manifest: PESESyncManifest


class DriveFileRecord(BaseModel):
    """Google Drive file entry in appDataFolder."""
    id: str
    name: str
    created_time: str = ""
    modified_time: Optional[str] = None
    size_bytes: Optional[int] = None
    properties: Dict[str, str] = Field(default_factory=dict)


class SyncStatus(BaseModel):
    """Overall status of Google Drive sync for UI presentation."""
    configured: bool
    connected: bool
    account_email: Optional[str] = None
    last_synced_at: Optional[str] = None
    latest_snapshot_id: Optional[str] = None
    latest_snapshot_time: Optional[str] = None
    status: SyncConnectionStatus
    message: Optional[str] = None
    restore_enabled: bool = False
    restore_disabled_reason: str = "Desktop recovery activation is not yet verified. In-place Restore is disabled; use offline recovery to a new Brain."


class RestoreResult(BaseModel):
    """Result of a snapshot restore operation."""
    success: bool
    brain_id: str
    snapshot_id: str
    restored_at: str
    backup_path: Optional[str] = None
    files_restored: int = 0
    message: str = ""


# =============================================================================
# DOMAIN EXCEPTIONS
# =============================================================================

class SyncError(Exception):
    """Base exception for all PESE sync operations."""
    pass


class SyncConfigurationError(SyncError):
    """Raised when Google OAuth client configuration is missing or invalid."""
    pass


class SyncAuthenticationError(SyncError):
    """Raised when OAuth authentication or token refresh fails."""
    pass


class SyncNetworkError(SyncError):
    """Raised when Google APIs cannot be reached (e.g. offline, DNS failure)."""
    pass


class CorruptSnapshotError(SyncError):
    """Raised when a snapshot fails integrity, hash, or format validation."""
    pass


class IncompatibleSnapshotError(SyncError):
    """Raised when a snapshot schema or sync format version is unsupported."""
    pass


class RestoreFailedError(SyncError):
    """Raised when Brain restoration fails (triggers safe rollback)."""
    pass


class SnapshotValidationError(SyncError):
    """Raised when local snapshot generation fails local safety checks."""
    pass
