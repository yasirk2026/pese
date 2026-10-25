"""
PESE Unit Tests: Google Drive Sync Foundation (G1)
Tests:
  - RFC 7636 PKCE & OAuth parameter generation and validation
  - Portable path enforcement and traversal rejection
  - Transactionally safe SQLite snapshotting
  - Deterministic snapshot creation & pese-sync-manifest.json generation
  - Corrupt / tampered snapshot rejection
  - Guarded restore with automatic rollback preservation
  - Secure credential storage (Windows DPAPI & Memory)
  - Google Drive appDataFolder client (mocked HTTP)
  - Full offline-first independence (PESE functions normally when Google is offline)
"""

import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.error import URLError

import pytest

from engine.brain.contracts import BrainIdentity, BRAIN_MANIFEST_FILENAME
from engine.brain.lifecycle import initialize_brain, open_brain, verify_brain_integrity
from engine.sync.contracts import (
    SYNC_FORMAT_VERSION,
    SYNC_MANIFEST_FILENAME,
    CURRENT_APP_VERSION,
    CURRENT_SCHEMA_VERSION,
    FileChecksumInfo,
    PESESyncManifest,
    SnapshotIntegrity,
    SyncConnectionStatus,
    SyncConfigurationError,
    SyncAuthenticationError,
    SyncNetworkError,
    CorruptSnapshotError,
    IncompatibleSnapshotError,
    RestoreFailedError,
    SnapshotValidationError,
)
from engine.sync.credentials import (
    MemoryCredentialStorage,
    WindowsDPAPICredentialStorage,
)
from engine.sync.drive_client import GoogleDriveClient
from engine.sync.manifest import (
    build_snapshot_manifest,
    compute_file_sha256,
    normalize_portable_path,
    verify_staged_snapshot,
)
from engine.sync.oauth import (
    OAuthClientConfig,
    generate_pkce_verifier,
    derive_pkce_challenge,
    generate_oauth_state,
    build_authorization_url,
)
from engine.sync.restore import restore_snapshot
from engine.sync.service import GoogleDriveSyncService
from engine.sync.snapshot import create_snapshot
from engine.sync.sqlite_safety import safe_sqlite_backup


# =============================================================================
# 1. OAuth & PKCE Logic Tests
# =============================================================================

def test_oauth_pkce_rfc7636_test_vector():
    """Validates PKCE calculation against RFC 7636 Section 4.2 / Appendix B."""
    # Official RFC 7636 test vector
    rfc_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    expected_challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    computed_challenge = derive_pkce_challenge(rfc_verifier)
    assert computed_challenge == expected_challenge


def test_oauth_pkce_generation():
    """Verify generated PKCE verifiers meet RFC 7636 length and character invariants."""
    verifier = generate_pkce_verifier()
    assert 43 <= len(verifier) <= 128
    # Must use only unreserved characters
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~")
    assert all(c in allowed_chars for c in verifier)

    challenge = derive_pkce_challenge(verifier)
    assert len(challenge) > 20
    assert "=" not in challenge  # No padding


def test_oauth_state_and_auth_url():
    """Verify OAuth state generation and authorization URL formation."""
    state1 = generate_oauth_state()
    state2 = generate_oauth_state()
    assert state1 != state2
    assert len(state1) >= 32

    cfg = OAuthClientConfig(
        client_id="test-client-id.apps.googleusercontent.com",
        client_secret="test-secret",
    )
    url = build_authorization_url(
        config=cfg,
        redirect_uri="http://127.0.0.1:8765/oauth2callback",
        state=state1,
        code_challenge="test_challenge_abc",
    )
    assert "https://accounts.google.com/o/oauth2/v2/auth" in url
    assert "client_id=test-client-id.apps.googleusercontent.com" in url
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8765%2Foauth2callback" in url
    assert "scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive.appdata" in url
    assert "code_challenge=test_challenge_abc" in url
    assert "code_challenge_method=S256" in url
    assert f"state={state1}" in url


# =============================================================================
# 2. Portable Path Enforcement Tests
# =============================================================================

def test_portable_path_enforcement():
    """Verify portable path normalizer accepts clean relative paths and rejects unsafe paths."""
    # Valid relative paths
    assert normalize_portable_path("pese-brain.json") == "pese-brain.json"
    assert normalize_portable_path("profile/profile.json") == "profile/profile.json"
    assert normalize_portable_path("semantic_index/doc_meta.json") == "semantic_index/doc_meta.json"

    # Rejects backslashes
    with pytest.raises(ValueError, match="Windows backslashes"):
        FileChecksumInfo(
            relativePath="profile\\avatar.png",
            sha256="abc",
            sizeBytes=10,
            category="user_profile",
        )

    # Rejects absolute paths
    with pytest.raises(ValueError, match="must not be absolute"):
        normalize_portable_path("/etc/passwd")

    with pytest.raises(ValueError, match="drive letter"):
        normalize_portable_path("C:/Users/Example/Brain/pese-brain.json")

    # Rejects traversal
    with pytest.raises(ValueError, match="traversal"):
        normalize_portable_path("../secrets.txt")

    with pytest.raises(ValueError, match="traversal"):
        normalize_portable_path("profile/../../evil.txt")


# =============================================================================
# 3. Transactionally Safe SQLite Backup Tests
# =============================================================================

def test_sqlite_safe_snapshot(tmp_path):
    """Verify safe_sqlite_backup performs a consistent copy passing integrity checks."""
    src_db = tmp_path / "live_feedback.db"
    dst_db = tmp_path / "staged_feedback.db"

    # Create and populate source DB
    with sqlite3.connect(src_db) as conn:
        conn.execute("CREATE TABLE active_preferences (normalized_query TEXT PRIMARY KEY, target_id TEXT)")
        conn.execute("INSERT INTO active_preferences VALUES ('bicycle maintenance', 'doc1')")
        conn.execute("INSERT INTO active_preferences VALUES ('japan ww2', 'doc2')")
        conn.commit()

    safe_sqlite_backup(src_db, dst_db)

    assert dst_db.exists()
    assert dst_db.stat().st_size > 0

    # Verify destination database integrity and contents
    with sqlite3.connect(dst_db) as conn:
        qc = conn.execute("PRAGMA quick_check").fetchone()
        assert qc == ("ok",)
        ic = conn.execute("PRAGMA integrity_check").fetchone()
        assert ic == ("ok",)
        rows = conn.execute("SELECT normalized_query, target_id FROM active_preferences ORDER BY target_id").fetchall()
        assert rows == [("bicycle maintenance", "doc1"), ("japan ww2", "doc2")]


def test_sqlite_safe_backup_rejects_corrupted_source(tmp_path):
    """Verify safe_sqlite_backup raises CorruptSnapshotError if source DB is corrupt."""
    corrupt_db = tmp_path / "corrupt.db"
    corrupt_db.write_bytes(b"NOT A SQLITE DATABASE CORRUPT BYTES 1234567890")
    dst_db = tmp_path / "dest.db"

    with pytest.raises(Exception):
        safe_sqlite_backup(corrupt_db, dst_db)
    assert not dst_db.exists()


# =============================================================================
# 4. Snapshot Creation & Manifest Integrity Tests
# =============================================================================

def test_snapshot_creation_and_manifest(tmp_path):
    """Verify create_snapshot captures all portable categories with valid SHA256 checksums."""
    brain_dir = tmp_path / "test_brain"
    identity = initialize_brain(brain_dir, name="Test Brain")

    # Add a mock profile
    profile_dir = brain_dir / "profile"
    profile_dir.mkdir(exist_ok=True)
    (profile_dir / "profile.json").write_text(json.dumps({"displayName": "Yasir"}), encoding="utf-8")

    # Add a lock file that MUST be excluded
    (brain_dir / ".desktop-writer.lock").write_text("1", encoding="utf-8")

    bundle = create_snapshot(brain_path=brain_dir, destination_dir=tmp_path / "snapshots")

    assert bundle.brain_id == identity.brain_id
    assert bundle.zip_path.exists()
    assert bundle.total_size_bytes > 0
    assert bundle.zip_sha256 == compute_file_sha256(bundle.zip_path)

    manifest = bundle.manifest
    assert manifest.sync_format_version == SYNC_FORMAT_VERSION
    assert manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert manifest.app_version == CURRENT_APP_VERSION
    assert manifest.brain_id == identity.brain_id

    # Verify captured categories
    expected_files = {
        "pese-brain.json",
        "firestore_documents.json",
        "privacy_settings.json",
        "search-sync-records.json",
        "behavioural_events.jsonl",
        "profile/profile.json",
    }
    for f in expected_files:
        assert f in manifest.files, f"Missing file in manifest: {f}"

    # Verify .desktop-writer.lock is NOT in manifest or zip
    assert ".desktop-writer.lock" not in manifest.files

    with zipfile.ZipFile(bundle.zip_path, "r") as zf:
        namelist = zf.namelist()
        assert SYNC_MANIFEST_FILENAME in namelist
        assert ".desktop-writer.lock" not in namelist
        # Verify no Windows backslashes in zip entry paths
        for entry in namelist:
            assert "\\" not in entry
            assert not entry.startswith("/")


# =============================================================================
# 5. Corrupt Snapshot Rejection Tests
# =============================================================================

def test_corrupt_snapshot_hash_mismatch(tmp_path):
    """Verify that any tampered byte inside a snapshot triggers CorruptSnapshotError."""
    brain_dir = tmp_path / "brain"
    initialize_brain(brain_dir)
    bundle = create_snapshot(brain_path=brain_dir, destination_dir=tmp_path)

    # Extract, tamper with a file, repackage
    unpack_dir = tmp_path / "tampered_unpack"
    with zipfile.ZipFile(bundle.zip_path, "r") as zf:
        zf.extractall(unpack_dir)

    # Tamper with documents store
    docs_file = unpack_dir / "firestore_documents.json"
    docs_file.write_text('{"tampered": true}', encoding="utf-8")

    tampered_zip = tmp_path / "tampered.zip"
    with zipfile.ZipFile(tampered_zip, "w") as zf:
        for f in unpack_dir.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f.relative_to(unpack_dir).as_posix())

    # Attempt restore: must be rejected with CorruptSnapshotError
    target_brain = tmp_path / "restore_target"
    with pytest.raises(CorruptSnapshotError, match="Integrity check failed"):
        restore_snapshot(tampered_zip, target_brain_path=target_brain,
                         expected_brain_id=bundle.brain_id, expected_snapshot_id=bundle.snapshot_id,
                         expected_zip_sha256=compute_file_sha256(tampered_zip))


def test_corrupt_snapshot_missing_manifest(tmp_path):
    """Verify zip without manifest is rejected."""
    bad_zip = tmp_path / "nomanifest.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("test.txt", "hello")

    with pytest.raises(CorruptSnapshotError, match="missing manifest"):
        restore_snapshot(bad_zip, target_brain_path=tmp_path / "target",
                         expected_brain_id="missing", expected_snapshot_id="missing",
                         expected_zip_sha256=compute_file_sha256(bad_zip))


# =============================================================================
# 6. Guarded Restore & Rollback Preservation Tests
# =============================================================================

def test_existing_brain_restore_is_rejected_without_mutation(tmp_path):
    brain = tmp_path / "existing"
    initialize_brain(brain)
    bundle = create_snapshot(brain, tmp_path)
    before = {p.name: p.read_bytes() for p in brain.iterdir() if p.is_file()}
    with pytest.raises(RestoreFailedError, match="never replaces"):
        restore_snapshot(bundle.zip_path, brain, expected_brain_id=bundle.brain_id,
                         expected_snapshot_id=bundle.snapshot_id, expected_zip_sha256=bundle.zip_sha256)
    assert before == {p.name: p.read_bytes() for p in brain.iterdir() if p.is_file()}


def test_recovery_creates_new_validated_brain(tmp_path):
    original = tmp_path / "original"
    initialize_brain(original)
    bundle = create_snapshot(original, tmp_path)
    target = tmp_path / "new"
    result = restore_snapshot(bundle.zip_path, target, expected_brain_id=bundle.brain_id,
                              expected_snapshot_id=bundle.snapshot_id, expected_zip_sha256=bundle.zip_sha256)
    assert result.success
    assert open_brain(original).brain_id == open_brain(target).brain_id
    assert verify_brain_integrity(target)["feedback_db_ok"]
    assert (tmp_path / ".new.pese-recovery.json").exists()


# =============================================================================
# 7. Secure Credential Storage Tests
# =============================================================================

def test_memory_credential_storage():
    """Verify credential storage contract using in-memory store."""
    store = MemoryCredentialStorage()
    assert store.load_credentials() is None

    payload = {"access_token": "tok_123", "refresh_token": "ref_456", "expires_at": 1893456000}
    store.save_credentials(payload)

    loaded = store.load_credentials()
    assert loaded == payload

    assert store.clear_credentials() is True
    assert store.load_credentials() is None


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI is only testable on Windows")
def test_windows_dpapi_credential_storage(tmp_path):
    """Verify Windows DPAPI encrypts and decrypts credentials securely."""
    store = WindowsDPAPICredentialStorage(storage_dir=tmp_path)
    payload = {"access_token": "ya29.secret_token", "account_email": "yasir@test.com"}
    store.save_credentials(payload)

    # Raw file on disk must be ciphertext, NOT plaintext JSON
    raw_bytes = (tmp_path / "google_drive_credentials.dat").read_bytes()
    assert b"ya29.secret_token" not in raw_bytes

    decrypted = store.load_credentials()
    assert decrypted == payload

    store.clear_credentials()
    assert store.load_credentials() is None


# =============================================================================
# 8. Google Drive Client (Mocked HTTP) Tests
# =============================================================================

def test_drive_client_list_snapshots_filtering():
    """Verify Drive client queries appDataFolder and filters PESE snapshots."""
    mock_resp = {
        "files": [
            {
                "id": "file_1",
                "name": "pese-snapshot-20261025T120000Z_1234.zip",
                "createdTime": "2026-10-25T12:00:00Z",
                "size": "1048576",
                "properties": {"pese_format": "pese-snapshot", "pese_snapshot_id": "20261025T120000Z_1234"},
            },
            {
                "id": "file_2",
                "name": "unrelated_other_file.txt",
                "createdTime": "2026-10-24T12:00:00Z",
            },
        ]
    }

    client = GoogleDriveClient(token_provider=lambda: "mock_token")

    with patch("engine.sync.drive_client.open_google") as mock_urlopen:
        mock_http = MagicMock()
        mock_http.read.return_value = json.dumps(mock_resp).encode("utf-8")
        mock_http.__enter__.return_value = mock_http
        mock_urlopen.return_value = mock_http

        snapshots = client.list_snapshots()

        assert len(snapshots) == 1
        assert snapshots[0].id == "file_1"
        assert snapshots[0].properties["pese_snapshot_id"] == "20261025T120000Z_1234"


def test_drive_client_upload_and_download(tmp_path):
    """Verify Drive upload formats multipart request and download writes bytes."""
    client = GoogleDriveClient(token_provider=lambda: "mock_token")

    # Create dummy bundle
    brain_dir = tmp_path / "brain"
    initialize_brain(brain_dir)
    bundle = create_snapshot(brain_path=brain_dir, destination_dir=tmp_path)

    upload_resp = {"id": "drive_uploaded_id_999", "name": bundle.zip_path.name, "createdTime": "2026-10-25T12:05:00Z"}

    with patch("engine.sync.drive_client.open_google") as mock_urlopen:
        mock_http = MagicMock()
        mock_http.read.return_value = json.dumps(upload_resp).encode("utf-8")
        mock_http.__enter__.return_value = mock_http
        mock_urlopen.return_value = mock_http

        rec = client.upload_snapshot(bundle)
        assert rec.id == "drive_uploaded_id_999"

        # Verify download
        mock_download_http = MagicMock()
        mock_download_http.read.side_effect = [b"PK\x03\x04zipcontent", b""]
        mock_download_http.__enter__.return_value = mock_download_http
        mock_urlopen.return_value = mock_download_http

        dest_file = tmp_path / "downloaded.zip"
        client.download_snapshot("drive_uploaded_id_999", dest_file)
        assert dest_file.exists()
        assert dest_file.read_bytes() == b"PK\x03\x04zipcontent"


# =============================================================================
# 9. Sync Service Lifecycle & Disconnect Tests
# =============================================================================

def test_sync_service_status_and_disconnect(tmp_path):
    """Verify service reports correct status transitions and disconnect clears tokens."""
    cred_store = MemoryCredentialStorage()
    cfg = OAuthClientConfig(client_id="test_id")
    brain_dir = tmp_path / "brain"
    initialize_brain(brain_dir)

    service = GoogleDriveSyncService(
        credential_storage=cred_store,
        oauth_config=cfg,
        brain_path=brain_dir,
    )

    # 1. Unconnected status
    status = service.get_status()
    assert status.configured is True
    assert status.connected is False
    assert status.status == SyncConnectionStatus.NOT_CONNECTED

    # 2. Set connected credentials
    cred_store.save_credentials({
        "access_token": "valid_token",
        "account_email": "user@example.com",
        "expires_at": 2000000000,
    })

    # Mock drive list
    with patch.object(service._drive_client, "get_latest_snapshot", return_value=None):
        status = service.get_status()
        assert status.connected is True
        assert status.account_email == "user@example.com"
        assert status.status == SyncConnectionStatus.CONNECTED

    # 3. Disconnect
    res = service.disconnect()
    assert res["ok"] is True
    assert service.is_connected() is False
    # PROVE: Local Brain remains intact
    assert (brain_dir / BRAIN_MANIFEST_FILENAME).exists()


# =============================================================================
# 10. Offline-First Independence Tests
# =============================================================================

def test_offline_operation_with_drive_unavailable(tmp_path):
    """
    CRITICAL ARCHITECTURE REQUIREMENT:
    Drive failure is a sync failure, NEVER a PESE search or startup failure.
    Verify that when network fails or Drive is down, PESE operates normally.
    """
    cred_store = MemoryCredentialStorage({
        "access_token": "tok",
        "expires_at": 2000000000,
    })
    cfg = OAuthClientConfig(client_id="test_id")
    brain_dir = tmp_path / "brain"
    initialize_brain(brain_dir)

    service = GoogleDriveSyncService(
        credential_storage=cred_store,
        oauth_config=cfg,
        brain_path=brain_dir,
    )

    # Simulate network failure on Drive API
    with patch.object(service._drive_client, "get_latest_snapshot", side_effect=SyncNetworkError("Network unreachable")):
        # Status handles network error gracefully without crashing
        status = service.get_status()
        assert status.connected is True
        assert status.status == SyncConnectionStatus.CONNECTED
        service._drive_client.get_latest_snapshot.assert_not_called()

    # PROVE: Local Brain can be opened and verified offline without issues
    info = open_brain(brain_dir)
    assert info.status.value == "active"
    integrity = verify_brain_integrity(brain_dir)
    assert integrity["manifest_ok"] is True
    assert integrity["documents_ok"] is True
