"""Safety and integration boundaries. All Brains are disposable; no Google calls."""
import asyncio
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from engine.brain.lifecycle import initialize_brain, open_brain
from engine.brain.coordination import canonical_lock
from engine.brain.profile import save_profile
from engine.discovery.history import LocalHistoryStore
from engine.search_sync.contracts import FeedbackEvent
from engine.search_sync.feedback_store import SearchSyncFeedbackStore
from engine.sync.contracts import (CorruptSnapshotError, RestoreFailedError, IncompatibleSnapshotError,
                                   SyncAuthenticationError, SnapshotValidationError, DriveFileRecord)
from engine.sync.credentials import MemoryCredentialStorage, WindowsDPAPICredentialStorage
from engine.sync.drive_client import GoogleDriveClient, MultipartBody
from engine.sync.logical import export_records, import_records, LOGICAL_FILENAME
from engine.sync.manifest import compute_file_sha256, normalize_portable_path
from engine.sync.oauth import OAuthClientConfig, EphemeralLoopbackServer
from engine.sync.restore import restore_snapshot
from engine.sync.service import GoogleDriveSyncService
from engine.sync.snapshot import create_snapshot, canonical_state_digest


def brain(tmp_path):
    root = tmp_path / "brain"
    initialize_brain(root)
    return root


def recover(bundle, target, **kwargs):
    return restore_snapshot(bundle.zip_path, target, expected_brain_id=kwargs.get("brain_id", bundle.brain_id),
                            expected_snapshot_id=kwargs.get("snapshot_id", bundle.snapshot_id),
                            expected_zip_sha256=kwargs.get("digest", bundle.zip_sha256))


def repack(bundle, target, transform):
    with zipfile.ZipFile(bundle.zip_path) as source:
        entries = {entry.filename: source.read(entry) for entry in source.infolist()}
    transform(entries)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return bundle.model_copy(update={"zip_path": target, "zip_sha256": compute_file_sha256(target)})


@pytest.mark.parametrize("mode", ["DELETE", "WAL"])
def test_logical_roundtrip_preserves_feedback_and_audit(tmp_path, mode):
    root = brain(tmp_path)
    store = SearchSyncFeedbackStore(root / "search_sync_feedback.db")
    with closing(sqlite3.connect(store.db_path)) as connection:
        connection.execute("PRAGMA journal_mode=" + mode)
    store.record_feedback(FeedbackEvent(query="bicycle", normalized_query="bicycle", target_type="SERP_RESULT",
                                        target_id="doc", feedback="LIKE"))
    records = export_records(store.db_path)
    assert records["tables"]["active_preferences"][0]["last_event_id"] == records["tables"]["feedback_audit_events"][0]["event_id"]
    destination = tmp_path / "import.db"
    import_records(records, destination)
    assert export_records(destination) == records
    with pytest.raises(CorruptSnapshotError):
        import_records(records, destination)
    # Source and destination handles are deterministically closed on Windows.
    destination.rename(tmp_path / "closed.db")


def test_snapshot_excludes_vectors_and_preserves_avatar(tmp_path):
    root = brain(tmp_path)
    save_profile("Fixture", "", root)
    from engine.brain.profile import import_avatar
    import_avatar(b"fixture-image", "avatar.png", root)
    (root / "semantic_index/cache_store.npz").write_bytes(b"rebuildable")
    before = canonical_state_digest(root)
    bundle = create_snapshot(root, tmp_path)
    assert canonical_state_digest(root) == before
    with zipfile.ZipFile(bundle.zip_path) as archive:
        assert "profile/avatar.png" in archive.namelist()
        assert LOGICAL_FILENAME in archive.namelist()
        assert "search_sync_feedback.db" not in archive.namelist()
        assert not any(name.startswith("semantic_index/") for name in archive.namelist())
    assert not list(root.rglob("*.tmp*"))


def test_unknown_personalization_fails_closed(tmp_path):
    root = brain(tmp_path)
    (root / "personalization/unknown.pt").write_bytes(b"not-portable")
    with pytest.raises(SnapshotValidationError, match="Personalization"):
        create_snapshot(root, tmp_path)
    assert not list(tmp_path.glob("pese-snapshot-*.zip"))


def test_snapshot_excludes_concurrent_canonical_writer(tmp_path):
    root = brain(tmp_path)
    paused, resume, writing, finished = (threading.Event() for _ in range(4))
    history = LocalHistoryStore(root / "behavioural_events.jsonl", root / "privacy_settings.json")
    import engine.sync.snapshot as snapshots
    copy = snapshots.shutil.copyfile
    def capture_pause(source, target, *args, **kwargs):
        if source.name == "firestore_documents.json":
            paused.set()
            assert resume.wait(5)
        return copy(source, target, *args, **kwargs)
    def writer():
        writing.set()
        history.set_history_enabled(False)
        finished.set()
    with ThreadPoolExecutor(2) as executor, patch.object(snapshots.shutil, "copyfile", capture_pause):
        capture = executor.submit(create_snapshot, root, tmp_path)
        assert paused.wait(5)
        write = executor.submit(writer)
        assert writing.wait(5)
        assert not finished.wait(.05)
        resume.set()
        bundle = capture.result(5)
        write.result(5)
    with zipfile.ZipFile(bundle.zip_path) as archive:
        assert json.loads(archive.read("privacy_settings.json"))["history_enabled"] is True
    assert json.loads((root / "privacy_settings.json").read_text())["history_enabled"] is False


@pytest.mark.parametrize("path", ["../outside", "profile\\avatar.png", "profile/avatar.png.", "CON", "a:b", "a//b"])
def test_portable_aliases_rejected(path):
    with pytest.raises(ValueError):
        normalize_portable_path(path)


@pytest.mark.parametrize("mutation", ["extra", "missing", "legacy", "identity", "schema", "privacy", "db-records"])
def test_invalid_archive_cannot_create_target(tmp_path, mutation):
    root = brain(tmp_path)
    bundle = create_snapshot(root, tmp_path)
    def transform(entries):
        manifest = json.loads(entries["pese-sync-manifest.json"])
        if mutation == "extra":
            entries["desktop-settings.json"] = b"{}"
        elif mutation == "missing":
            del entries["privacy_settings.json"]
        elif mutation == "legacy":
            manifest["syncFormatVersion"] = 1
        elif mutation in ("identity", "schema"):
            manifest["brainId" if mutation == "identity" else "schemaVersion"] = "wrong" if mutation == "identity" else 999
        else:
            name = "privacy_settings.json" if mutation == "privacy" else LOGICAL_FILENAME
            entries[name] = b'[]'
            manifest["files"][name]["sha256"] = hashlib.sha256(entries[name]).hexdigest()
            manifest["files"][name]["sizeBytes"] = len(entries[name])
            manifest["integrity"]["totalBytes"] = sum(item["sizeBytes"] for item in manifest["files"].values())
            manifest["integrity"]["contentDigest"] = hashlib.sha256("".join(k+":"+v["sha256"] for k,v in sorted(manifest["files"].items())).encode()).hexdigest()
        entries["pese-sync-manifest.json"] = json.dumps(manifest).encode()
    changed = repack(bundle, tmp_path / "invalid.zip", transform)
    with pytest.raises((CorruptSnapshotError, IncompatibleSnapshotError)):
        recover(changed, tmp_path / "target")
    assert not (tmp_path / "target").exists()
    assert open_brain(root).brain_id == bundle.brain_id


@pytest.mark.parametrize("field", ["brain_id", "snapshot_id", "digest"])
def test_selected_metadata_must_match(tmp_path, field):
    root = brain(tmp_path)
    bundle = create_snapshot(root, tmp_path)
    with pytest.raises(CorruptSnapshotError):
        recover(bundle, tmp_path / "target", **{field: "wrong"})
    assert not (tmp_path / "target").exists()


def test_locked_original_and_failed_initialization_are_preserved(tmp_path):
    root = brain(tmp_path)
    bundle = create_snapshot(root, tmp_path)
    before = canonical_state_digest(root)
    with (root / ".desktop-writer.lock").open("a+b"):
        with pytest.raises(RestoreFailedError):
            recover(bundle, root)
        with patch("engine.desktop.launcher.validate_brain", side_effect=RuntimeError("initialization failed")):
            with pytest.raises(RuntimeError):
                recover(bundle, tmp_path / "failed")
    assert not (tmp_path / "failed").exists()
    assert canonical_state_digest(root) == before


def test_process_termination_cannot_replace_original(tmp_path):
    root = brain(tmp_path)
    bundle = create_snapshot(root, tmp_path)
    before = canonical_state_digest(root)
    target = tmp_path / "interrupted"
    script = """import os,sys; sys.path.insert(0,sys.argv[1]); from engine.sync.restore import restore_snapshot; os.rename=lambda *a:os._exit(23); restore_snapshot(sys.argv[2],sys.argv[3],expected_brain_id=sys.argv[4],expected_snapshot_id=sys.argv[5],expected_zip_sha256=sys.argv[6])"""
    process = subprocess.run([sys.executable, "-B", "-c", script, str(Path.cwd()), str(bundle.zip_path), str(target),
                              bundle.brain_id, bundle.snapshot_id, bundle.zip_sha256], timeout=20, capture_output=True)
    assert process.returncode == 23, process.stderr.decode(errors="replace")
    assert not target.exists()
    assert (tmp_path / ".interrupted.pese-recovery.json").exists()
    with pytest.raises(RestoreFailedError, match="interrupted"):
        recover(bundle, target)
    assert canonical_state_digest(root) == before


def test_drive_pagination_brain_filter_and_streaming(tmp_path):
    client = GoogleDriveClient(lambda: "fixture-token")
    pages = [{"files": [{"id":"other", "name":"other", "properties":{"pese_format":"pese-snapshot", "pese_brain_id":"other"}}], "nextPageToken":"next"},
             {"files": [{"id":"selected", "name":"selected", "properties":{"pese_format":"pese-snapshot", "pese_brain_id":"mine"}}]}]
    with patch.object(client, "_json", side_effect=pages) as request:
        assert [r.id for r in client.list_snapshots("mine")] == ["selected"]
        assert "pageToken=next" in request.call_args.args[0]
    data = tmp_path / "large.zip"
    data.write_bytes(b"x" * 200000)
    body = MultipartBody(data, b"prefix", b"suffix")
    chunks = list(body)
    assert sum(map(len, chunks)) == body.size
    assert max(map(len, chunks)) <= 65536


def test_upload_applies_real_timeout_and_temp_archive_cleanup(tmp_path):
    root = brain(tmp_path)
    credentials = MemoryCredentialStorage({"access_token":"fixture", "expires_at":time_future()})
    service = GoogleDriveSyncService(credentials, OAuthClientConfig("fixture"), root)
    observed = []
    def upload(bundle):
        observed.append(bundle.zip_path)
        raise RuntimeError("fixture outage")
    with patch.object(service._drive_client, "upload_snapshot", side_effect=upload):
        with pytest.raises(RuntimeError):
            service.sync_now()
    assert observed and not observed[0].exists()
    bundle = create_snapshot(root, tmp_path)
    with patch("engine.sync.drive_client.open_google") as transport:
        response = transport.return_value.__enter__.return_value
        response.read.return_value = b'{"id":"uploaded"}'
        service._drive_client.upload_snapshot(bundle)
        assert transport.call_args.kwargs["timeout"] == 60
        assert isinstance(transport.call_args.args[0].data, MultipartBody)


def time_future():
    import time
    return time.time() + 3600


def test_local_status_never_contacts_google_and_stale_snapshots_are_marked(tmp_path):
    root = brain(tmp_path)
    bundle = create_snapshot(root, tmp_path)
    service = GoogleDriveSyncService(MemoryCredentialStorage({"access_token":"fixture", "expires_at":time_future()}), OAuthClientConfig("fixture"), root)
    record = DriveFileRecord(id="explicit", name="fixture", properties={"pese_brain_id":bundle.brain_id,
                              "pese_snapshot_id":bundle.snapshot_id, "pese_sync_format_version":"2",
                              "pese_content_digest":bundle.manifest.integrity.content_digest})
    with patch.object(service._drive_client, "list_snapshots", return_value=[record]) as listing:
        service.get_status()
        listing.assert_not_called()
        assert service.list_remote_snapshots()[0]["local_changes"] is False
        LocalHistoryStore(root / "behavioural_events.jsonl", root / "privacy_settings.json").set_history_enabled(False)
        assert service.list_remote_snapshots()[0]["local_changes"] is True
    with patch.object(service._drive_client, "download_snapshot") as download:
        with pytest.raises(RestoreFailedError):
            service.restore_from_drive("explicit")
        download.assert_not_called()


def test_disconnect_during_refresh_cannot_resurrect_credentials(tmp_path):
    root = brain(tmp_path)
    credentials = MemoryCredentialStorage({"refresh_token":"fixture", "expires_at":0})
    service = GoogleDriveSyncService(credentials, OAuthClientConfig("fixture"), root)
    entered, release = threading.Event(), threading.Event()
    def refresh(*args):
        entered.set()
        assert release.wait(5)
        return {"access_token":"new"}
    with ThreadPoolExecutor(1) as pool, patch("engine.sync.service.refresh_access_token", refresh), patch("engine.sync.service.revoke_token", return_value=True):
        pending = pool.submit(service.get_valid_access_token)
        assert entered.wait(5)
        service.disconnect()
        release.set()
        with pytest.raises(SyncAuthenticationError):
            pending.result(5)
    assert credentials.load_credentials() is None


def test_disconnect_failure_is_reported_and_browser_failure_is_not_connected(tmp_path):
    root = brain(tmp_path)
    credentials = MemoryCredentialStorage()
    service = GoogleDriveSyncService(credentials, OAuthClientConfig("fixture"), root)
    with patch.object(credentials, "clear_credentials", return_value=False):
        with pytest.raises(SyncAuthenticationError):
            service.disconnect()
    with patch("engine.sync.service.webbrowser.open", return_value=False):
        with pytest.raises(SyncAuthenticationError):
            service.start_oauth_flow()
    assert not service.is_connected()


def test_disconnect_during_authorization_cannot_save_tokens(tmp_path):
    root = brain(tmp_path)
    credentials = MemoryCredentialStorage()
    service = GoogleDriveSyncService(credentials, OAuthClientConfig("fixture"), root)
    entered, release = threading.Event(), threading.Event()
    server = MagicMock()
    server.start.return_value = 54321
    server.wait_for_code.return_value = "fixture-code"
    def exchange(*args):
        entered.set()
        assert release.wait(5)
        return {"access_token":"fixture-token"}
    with patch("engine.sync.service.EphemeralLoopbackServer", return_value=server), patch("engine.sync.service.exchange_code_for_tokens", exchange), patch.object(service._drive_client, "get_about_user", return_value={"emailAddress":"fixture@example.test"}) as lookup:
        service.start_oauth_flow(open_browser=False)
        assert entered.wait(5)
        service.disconnect()
        release.set()
        service._active_auth_thread.join(5)
    assert not service._active_auth_thread.is_alive()
    assert credentials.load_credentials() is None
    lookup.assert_not_called()


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI acceptance")
def test_concurrent_dpapi_saves_are_atomic(tmp_path):
    storage = WindowsDPAPICredentialStorage(tmp_path)
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda i: storage.save_credentials({"access_token":str(i)}), range(12)))
    assert storage.load_credentials()["access_token"] in set(map(str, range(12)))
    assert not list(tmp_path.glob(".google-*"))


@pytest.fixture
def controlled_boundary(monkeypatch):
    from engine.desktop import offline
    calls = []
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    def connect(self, address):
        if address[0] in ("127.0.0.1", "::1"):
            return original_connect(self, address)
        calls.append(address)
    def connect_ex(self, address):
        if address[0] in ("127.0.0.1", "::1"):
            return original_connect_ex(self, address)
        calls.append(address)
        return 0
    monkeypatch.setattr(offline, "_installed", False)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("142.250.1.1", 443))])
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", socket.socket.sendto)
    offline.install_offline_boundary()
    return offline, calls


def test_resolved_ip_nesting_scope_and_thread_isolation(controlled_boundary):
    offline, calls = controlled_boundary
    with pytest.raises(OSError):
        socket.create_connection(("www.googleapis.com",443))
    with offline.allow_sync_network():
        with socket.create_connection(("www.googleapis.com",443)):
            pass
        with offline.allow_sync_network():
            socket.getaddrinfo("oauth2.googleapis.com",443)
        with socket.socket() as connection:
            connection.connect(("142.250.1.1",443))
            with pytest.raises(OSError):
                connection.connect(("142.250.1.1",80))
        with ThreadPoolExecutor(1) as executor:
            future = executor.submit(socket.getaddrinfo,"www.googleapis.com",443)
            with pytest.raises(OSError):
                future.result()
        with pytest.raises(OSError):
            socket.getaddrinfo("unrelated.googleapis.com",443)
    with socket.socket() as connection:
        with pytest.raises(OSError):
            connection.connect(("142.250.1.1",443))
    assert calls == [("142.250.1.1",443),("142.250.1.1",443)]


def test_permission_expiry_and_async_inheritance(controlled_boundary):
    offline, calls = controlled_boundary
    with offline.allow_sync_network(timeout=-1):
        with pytest.raises(OSError):
            socket.getaddrinfo("www.googleapis.com",443)
    async def child():
        with pytest.raises(OSError):
            socket.getaddrinfo("www.googleapis.com",443)
    async def parent():
        with offline.allow_sync_network():
            await asyncio.create_task(child())
    asyncio.run(parent())
    assert calls == []


@pytest.mark.parametrize("url", ["http://www.googleapis.com/drive/v3/files", "https://evil.googleapis.com/drive/v3/files",
                                  "https://www.googleapis.com:444/drive/v3/files", "https://oauth2.googleapis.com/other",
                                  "https://www.googleapis.com/drive/v3/../other"])
def test_remote_endpoint_allowlist(url):
    from engine.sync.transport import validate_google_url
    from engine.sync.contracts import SyncConfigurationError
    with pytest.raises(SyncConfigurationError):
        validate_google_url(url)


def test_real_loopback_socket_resolution_under_boundary(monkeypatch):
    """Exercise socket.create_connection and actual TCP I/O; no external host is contacted."""
    import socketserver
    from engine.desktop import offline
    class Echo(socketserver.BaseRequestHandler):
        def handle(self):
            self.request.sendall(self.request.recv(16))
    original_connect = socket.socket.connect
    with socketserver.TCPServer(("127.0.0.1", 0), Echo) as server:
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        def connect(self, address):
            return original_connect(self, server.server_address if address == ("142.250.1.1",443) else address)
        monkeypatch.setattr(offline, "_installed", False)
        monkeypatch.setattr(socket.socket, "connect", connect)
        monkeypatch.setattr(socket.socket, "connect_ex", socket.socket.connect_ex)
        monkeypatch.setattr(socket.socket, "sendto", socket.socket.sendto)
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET,socket.SOCK_STREAM,6,"",("142.250.1.1",443))])
        offline.install_offline_boundary()
        with offline.allow_sync_network(), socket.create_connection(("www.googleapis.com",443), timeout=2) as connection:
            connection.sendall(b"controlled")
            assert connection.recv(16) == b"controlled"
        thread.join(2)
        assert not thread.is_alive()


def test_importing_portable_sync_has_no_runtime_storage_side_effects(tmp_path):
    environment = dict(os.environ)
    environment.update(PESE_ENV="production", PESE_BRAIN_PATH=str(tmp_path / "missing"))
    script = "import sys; sys.path.insert(0,sys.argv[1]); import engine.sync; assert 'engine.search_sync.feedback_store' not in sys.modules"
    process = subprocess.run([sys.executable,"-B","-c",script,str(Path.cwd())], env=environment, capture_output=True, timeout=10)
    assert process.returncode == 0, process.stderr.decode(errors="replace")
    assert not (tmp_path / "missing").exists()


def test_recovery_download_cleanup_and_confirmation(tmp_path):
    import shutil
    root = brain(tmp_path)
    bundle = create_snapshot(root, tmp_path)
    service = GoogleDriveSyncService(MemoryCredentialStorage({"access_token":"fixture","expires_at":time_future()}), OAuthClientConfig("fixture"), root)
    properties = {"pese_brain_id":bundle.brain_id,"pese_snapshot_id":bundle.snapshot_id,
                  "pese_sync_format_version":"2","pese_sha256":bundle.zip_sha256,"pese_schema_version":"1",
                  "pese_app_version":bundle.manifest.app_version,"pese_content_digest":bundle.manifest.integrity.content_digest}
    record = DriveFileRecord(id="explicit",name="fixture",properties=properties)
    observed = []
    def download(file_id, destination, **kwargs):
        observed.append(destination)
        shutil.copyfile(bundle.zip_path, destination)
    arguments = dict(file_id="explicit",snapshot_id=bundle.snapshot_id,brain_id=bundle.brain_id,
                     archive_sha256=bundle.zip_sha256,confirmed_local_digest=canonical_state_digest(root))
    with patch.object(service._drive_client,"list_snapshots",return_value=[record]), patch.object(service._drive_client,"download_snapshot",side_effect=download):
        with pytest.raises(RestoreFailedError,match="Local state changed"):
            service.recover_to_new_brain(**{**arguments,"confirmed_local_digest":"stale"},target=tmp_path/"stale")
        assert not observed
        result = service.recover_to_new_brain(**arguments,target=tmp_path/"recovered")
        assert result.success
    assert observed and not observed[0].exists()
    assert canonical_state_digest(root) == arguments["confirmed_local_digest"]


def test_oauth_loopback_requires_state_and_does_not_prematurely_claim_connection():
    import urllib.request
    import urllib.error
    server = EphemeralLoopbackServer("correct-state")
    port = server.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with pytest.raises(urllib.error.HTTPError):
            opener.open(f"http://127.0.0.1:{port}/oauth2callback?state=wrong&code=no",timeout=2)
        assert not server._shutdown_event.is_set()
        with opener.open(f"http://127.0.0.1:{port}/oauth2callback?state=correct-state&code=fixture",timeout=2) as response:
            assert b"Google Drive Connected" not in response.read()
        assert server.wait_for_code(2) == "fixture"
    finally:
        server.close()


@pytest.mark.skipif(os.name != "nt", reason="Desktop cross-process writer ownership")
def test_separate_process_cannot_capture_an_active_desktop_brain(tmp_path):
    root = brain(tmp_path)
    command = "import sys,msvcrt; h=open(sys.argv[1],'a+b'); h.write(b'0'); h.flush(); h.seek(0); msvcrt.locking(h.fileno(),msvcrt.LK_NBLCK,1); print('locked',flush=True); sys.stdin.readline(); h.close()"
    child = subprocess.Popen([sys.executable,"-B","-u","-c",command,str(root/".desktop-writer.lock")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "locked"
        with pytest.raises(RuntimeError,match="active in another process"):
            create_snapshot(root,tmp_path)
    finally:
        child.stdin.write("stop\n")
        child.stdin.flush()
        child.wait(timeout=5)


def test_downloaded_desktop_client_normalizes_official_legacy_auth_uri():
    config = OAuthClientConfig.from_dict({"installed":{"client_id":"fixture", "auth_uri":"https://accounts.google.com/o/oauth2/auth", "token_uri":"https://oauth2.googleapis.com/token"}})
    assert config.auth_uri == "https://accounts.google.com/o/oauth2/v2/auth"


def test_download_never_removes_an_existing_destination(tmp_path):
    from engine.sync.contracts import SyncNetworkError
    destination = tmp_path / "existing"
    destination.write_bytes(b"preserve-existing-data")
    client = GoogleDriveClient(lambda:"fixture")
    with patch("engine.sync.drive_client.open_google"):
        with pytest.raises(SyncNetworkError):
            client.download_snapshot("fixture",destination)
    assert destination.read_bytes() == b"preserve-existing-data"


def test_sqlite_backup_cannot_replace_source_or_existing_file(tmp_path):
    from engine.sync.sqlite_safety import safe_sqlite_backup
    from engine.sync.contracts import SyncError
    source = tmp_path / "source.db"
    with closing(sqlite3.connect(source)) as connection:
        connection.execute("CREATE TABLE preserved (id INTEGER)")
        connection.commit()
    before = source.read_bytes()
    with pytest.raises(SyncError):
        safe_sqlite_backup(source,source)
    assert source.read_bytes() == before
    destination = tmp_path / "existing.db"
    destination.write_bytes(b"existing")
    with pytest.raises(SyncError):
        safe_sqlite_backup(source,destination)
    assert destination.read_bytes() == b"existing"


def test_snapshot_destination_cannot_write_into_brain(tmp_path):
    root = brain(tmp_path)
    with pytest.raises(SnapshotValidationError,match="outside the Brain"):
        create_snapshot(root,root/"backups")
    assert not (root/"backups").exists()


def test_failed_authorized_upload_sets_local_error_state(tmp_path):
    root = brain(tmp_path)
    service = GoogleDriveSyncService(MemoryCredentialStorage({"access_token":"fixture","expires_at":time_future()}), OAuthClientConfig("fixture"), root)
    with patch.object(service._drive_client,"upload_snapshot",side_effect=SyncAuthenticationError("Authorization expired; reconnect.")):
        with pytest.raises(SyncAuthenticationError):
            service.sync_now()
    assert service.get_status().status.value == "error"
    assert "reconnect" in service.get_status().message


def test_reconnect_uses_new_account_and_waits_for_persistence(tmp_path):
    root = brain(tmp_path)
    credentials = MemoryCredentialStorage({"access_token":"old-fixture","expires_at":time_future(),"account_email":"old@example.test"})
    service = GoogleDriveSyncService(credentials,OAuthClientConfig("fixture"),root)
    entered, release = threading.Event(), threading.Event()
    server = MagicMock()
    server.start.return_value = 54321
    def wait_for_code(**kwargs):
        entered.set()
        assert release.wait(5)
        return "fixture-code"
    server.wait_for_code.side_effect = wait_for_code
    with patch("engine.sync.service.EphemeralLoopbackServer",return_value=server), patch("engine.sync.service.exchange_code_for_tokens",return_value={"access_token":"new-fixture"}), patch.object(service._drive_client,"get_about_user",return_value={"emailAddress":"new@example.test"}) as account:
        service.start_oauth_flow(open_browser=False)
        assert entered.wait(5)
        assert not service.get_status().connected
        assert service.get_status().status.value == "connecting"
        release.set()
        service._active_auth_thread.join(5)
    assert service.get_status().account_email == "new@example.test"
    assert service.get_status().connected
    assert account.call_args.kwargs["access_token"] == "new-fixture"


def test_failed_credential_persistence_never_reports_connected(tmp_path):
    root = brain(tmp_path)
    credentials = MemoryCredentialStorage()
    service = GoogleDriveSyncService(credentials,OAuthClientConfig("fixture"),root)
    server = MagicMock()
    server.start.return_value = 54321
    server.wait_for_code.return_value = "fixture"
    with patch("engine.sync.service.EphemeralLoopbackServer",return_value=server), patch("engine.sync.service.exchange_code_for_tokens",return_value={"access_token":"fixture"}), patch.object(service._drive_client,"get_about_user",return_value={"emailAddress":"fixture@example.test"}), patch.object(credentials,"save_credentials",side_effect=OSError("fixture storage failure")):
        service.start_oauth_flow(open_browser=False)
        service._active_auth_thread.join(5)
    assert not service.get_status().connected
    assert service.get_status().status.value == "error"


def test_service_account_configuration_is_rejected():
    from engine.sync.contracts import SyncConfigurationError
    with pytest.raises(SyncConfigurationError):
        OAuthClientConfig.from_dict({"type":"service_account","client_id":"fixture"})
