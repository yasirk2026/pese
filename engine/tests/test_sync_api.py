"""
PESE Unit Tests: Google Drive Sync API Endpoints
Validates FastAPI integration for:
  - GET /api/sync/status
  - POST /api/sync/connect
  - POST /api/sync/disconnect
  - POST /api/sync/now
  - POST /api/sync/restore
  - GET /api/sync/snapshots
"""

import json
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from engine.api.main import app, get_sync_service
from engine.sync.contracts import SyncConnectionStatus, RestoreResult
from engine.sync.credentials import MemoryCredentialStorage
from engine.sync.oauth import OAuthClientConfig


@pytest.fixture
def client():
    return TestClient(app)


def test_api_sync_status_unconfigured(client):
    """Verify status reports unconfigured when no OAuth client config is set."""
    service = get_sync_service()
    with patch.object(service, "get_oauth_config", return_value=None):
        resp = client.get("/api/sync/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is False
        assert data["connected"] is False
        assert data["status"] == "not_configured"


def test_api_sync_status_not_connected(client):
    """Verify status reports not connected when configured but no tokens."""
    service = get_sync_service()
    mock_cfg = OAuthClientConfig(client_id="mock_id")
    with patch.object(service, "get_oauth_config", return_value=mock_cfg):
        with patch.object(service.credentials, "load_credentials", return_value=None):
            resp = client.get("/api/sync/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["configured"] is True
            assert data["connected"] is False
            assert data["status"] == "not_connected"


def test_api_sync_disconnect(client):
    """Verify disconnect endpoint clears credentials."""
    service = get_sync_service()
    with patch.object(service, "disconnect", return_value={"ok": True, "message": "Disconnected"}):
        resp = client.post("/api/sync/disconnect")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


def test_api_sync_now_mock(client):
    """Verify sync now creates and uploads snapshot."""
    service = get_sync_service()
    mock_result = {
        "ok": True,
        "snapshot_id": "snap_123",
        "drive_file_id": "drive_abc",
        "last_synced_at": "2026-10-25T12:00:00Z",
        "message": "Snapshot snap_123 uploaded successfully.",
    }
    with patch.object(service, "sync_now", return_value=mock_result):
        resp = client.post("/api/sync/now")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["snapshot_id"] == "snap_123"


def test_api_sync_restore_rejects_before_io(client):
    service = get_sync_service()
    with patch.object(service, "restore_from_drive") as restore:
        with patch("engine.api.main.reload_search_pipeline") as reload:
            response = client.post("/api/sync/restore", json={"snapshot_id": "explicit"})
            assert response.status_code == 409
            restore.assert_not_called()
            reload.assert_not_called()


def test_api_sync_snapshots_list(client):
    """Verify snapshots listing endpoint returns Drive records."""
    service = get_sync_service()
    mock_snaps = [
        {"id": "file1", "name": "pese-snapshot-1.zip", "created_time": "2026-10-25T12:00:00Z", "size_bytes": 1024}
    ]
    with patch.object(service, "list_remote_snapshots", return_value=mock_snaps):
        resp = client.get("/api/sync/snapshots")
        assert resp.status_code == 200
        assert len(resp.json()["snapshots"]) == 1
