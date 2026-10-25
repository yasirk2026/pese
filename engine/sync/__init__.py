"""
PESE Google Drive Sync Foundation: Public API Exports.
"""

from .contracts import (
    SYNC_FORMAT_VERSION,
    SYNC_MANIFEST_FILENAME,
    CURRENT_APP_VERSION,
    CURRENT_SCHEMA_VERSION,
    GOOGLE_DRIVE_APPDATA_SCOPE,
    SyncStatus,
    SyncConnectionStatus,
    PESESyncManifest,
    SnapshotBundle,
    RestoreResult,
    DriveFileRecord,
    SyncError,
    SyncConfigurationError,
    SyncAuthenticationError,
    SyncNetworkError,
    CorruptSnapshotError,
    IncompatibleSnapshotError,
    RestoreFailedError,
    SnapshotValidationError,
)
from .credentials import (
    BaseCredentialStorage,
    WindowsDPAPICredentialStorage,
    MemoryCredentialStorage,
    get_credential_storage,
)
from .manifest import (
    build_snapshot_manifest,
    compute_file_sha256,
    normalize_portable_path,
    verify_staged_snapshot,
)
from .oauth import (
    OAuthClientConfig,
    load_oauth_client_config,
    generate_pkce_verifier,
    derive_pkce_challenge,
    generate_oauth_state,
    build_authorization_url,
    exchange_code_for_tokens,
    refresh_access_token,
    revoke_token,
)
from .sqlite_safety import safe_sqlite_backup
from .snapshot import create_snapshot, create_snapshot_async
from .restore import restore_snapshot, restore_snapshot_async
from .drive_client import GoogleDriveClient
from .service import GoogleDriveSyncService

__all__ = [
    "SYNC_FORMAT_VERSION",
    "SYNC_MANIFEST_FILENAME",
    "CURRENT_APP_VERSION",
    "CURRENT_SCHEMA_VERSION",
    "GOOGLE_DRIVE_APPDATA_SCOPE",
    "SyncStatus",
    "SyncConnectionStatus",
    "PESESyncManifest",
    "SnapshotBundle",
    "RestoreResult",
    "DriveFileRecord",
    "SyncError",
    "SyncConfigurationError",
    "SyncAuthenticationError",
    "SyncNetworkError",
    "CorruptSnapshotError",
    "IncompatibleSnapshotError",
    "RestoreFailedError",
    "SnapshotValidationError",
    "BaseCredentialStorage",
    "WindowsDPAPICredentialStorage",
    "MemoryCredentialStorage",
    "get_credential_storage",
    "build_snapshot_manifest",
    "compute_file_sha256",
    "normalize_portable_path",
    "verify_staged_snapshot",
    "OAuthClientConfig",
    "load_oauth_client_config",
    "generate_pkce_verifier",
    "derive_pkce_challenge",
    "generate_oauth_state",
    "build_authorization_url",
    "exchange_code_for_tokens",
    "refresh_access_token",
    "revoke_token",
    "safe_sqlite_backup",
    "create_snapshot",
    "create_snapshot_async",
    "restore_snapshot",
    "restore_snapshot_async",
    "GoogleDriveClient",
    "GoogleDriveSyncService",
]
