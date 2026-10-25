"""Manual backup orchestration; destructive desktop restore is unavailable."""
import logging
import shutil
import tempfile
import threading
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from .contracts import (SyncStatus, SyncConnectionStatus, SyncConfigurationError,
                        SyncAuthenticationError, SyncNetworkError, RestoreFailedError, SYNC_FORMAT_VERSION)
from .credentials import get_credential_storage
from .drive_client import GoogleDriveClient
from .oauth import (load_oauth_client_config, generate_pkce_verifier, derive_pkce_challenge,
                    generate_oauth_state, build_authorization_url, EphemeralLoopbackServer,
                    exchange_code_for_tokens, refresh_access_token, revoke_token)
from .snapshot import create_snapshot, canonical_state_digest
from ..brain.lifecycle import open_brain
from ..brain.resolver import resolve_brain_path

logger = logging.getLogger(__name__)
RESTORE_DISABLED_REASON = "Desktop Restore is disabled until host-controlled activation is verified. Offline recovery creates a new Brain and never overwrites the current one."


class GoogleDriveSyncService:
    def __init__(self, credential_storage=None, oauth_config=None, brain_path=None):
        self.credentials = credential_storage or get_credential_storage()
        self._oauth_config_override = oauth_config
        self.brain_path = brain_path
        self._drive_client = GoogleDriveClient(self.get_valid_access_token)
        self._state_lock = threading.RLock()
        self._operation_lock = threading.Lock()
        self._refresh_lock = threading.Lock()
        self._generation = 0
        self._connecting = False
        self._active_server = None
        self._active_auth_thread = None
        self._last_auth_error = None

    def _brain(self):
        return Path(self.brain_path) if self.brain_path else resolve_brain_path()

    def get_oauth_config(self):
        return self._oauth_config_override or load_oauth_client_config()

    def is_configured(self):
        return self.get_oauth_config() is not None

    def is_connected(self):
        with self._state_lock:
            creds = self.credentials.load_credentials()
            return bool(creds and (creds.get("access_token") or creds.get("refresh_token")))

    def get_valid_access_token(self):
        with self._refresh_lock:
            return self._get_valid_access_token()

    def _record_auth_error(self, error, generation):
        with self._state_lock:
            if generation == self._generation and self.is_connected():
                self._last_auth_error = str(error)

    def _get_valid_access_token(self):
        with self._state_lock:
            generation = self._generation
            creds = self.credentials.load_credentials()
            if not creds:
                raise SyncAuthenticationError("Google Drive is disconnected.")
            if creds.get("access_token") and creds.get("expires_at", 0) - time.time() > 60:
                return creds["access_token"]
            refresh = creds.get("refresh_token")
            if not refresh:
                raise SyncAuthenticationError("Authorization expired. Reconnect Google Drive.")
            config = self.get_oauth_config()
            if not config:
                raise SyncConfigurationError("Desktop OAuth configuration is missing.")
        try:
            tokens = refresh_access_token(refresh, config)
        except SyncAuthenticationError as exc:
            self._record_auth_error(exc, generation)
            raise
        with self._state_lock:
            if generation != self._generation:
                raise SyncAuthenticationError("Authorization was cancelled.")
            current = self.credentials.load_credentials()
            if not current:
                raise SyncAuthenticationError("Google Drive was disconnected.")
            current.update(access_token=tokens["access_token"], expires_at=time.time() + tokens.get("expires_in", 3600))
            if tokens.get("refresh_token"):
                current["refresh_token"] = tokens["refresh_token"]
            self.credentials.save_credentials(current)
            self._last_auth_error = None
            return current["access_token"]

    def get_status(self):
        """Local-only status. Opening Settings never starts Google requests."""
        with self._state_lock:
            try:
                configured = self.is_configured()
            except SyncConfigurationError:
                return SyncStatus(configured=False, connected=False, status=SyncConnectionStatus.ERROR,
                                  message="Desktop OAuth configuration is invalid.")
            creds = self.credentials.load_credentials() or {}
            connected = bool(creds.get("access_token") or creds.get("refresh_token"))
            status = (SyncConnectionStatus.CONNECTING if self._connecting else
                      SyncConnectionStatus.ERROR if self._last_auth_error else
                      SyncConnectionStatus.CONNECTED if connected else
                      SyncConnectionStatus.NOT_CONNECTED if configured else SyncConnectionStatus.NOT_CONFIGURED)
            brain_id = open_brain(self._brain()).brain_id if self.brain_path else None
            last = creds.get("backups", {}).get(brain_id, {})
            message = self._last_auth_error
            if not configured:
                message = "Configure a Google Desktop OAuth client in the external google-oauth-config.json."
            return SyncStatus(configured=configured, connected=connected, status=status, account_email=creds.get("account_email"),
                              last_synced_at=last.get("time"), latest_snapshot_id=last.get("snapshot_id"),
                              message=message, restore_disabled_reason=RESTORE_DISABLED_REASON)

    def start_oauth_flow(self, open_browser=True, authorization_timeout=120.0):
        config = self.get_oauth_config()
        if not config:
            raise SyncConfigurationError("Place your Desktop OAuth client JSON in the external google-oauth-config.json.")
        verifier, state = generate_pkce_verifier(), generate_oauth_state()
        with self._state_lock:
            self._generation += 1
            generation = self._generation
            if self._active_server:
                self._active_server.close()
            # A reconnect cannot accidentally display the previous account as connected.
            if not self.credentials.clear_credentials():
                raise SyncAuthenticationError("Could not clear the previous authorization.")
            self._connecting, self._last_auth_error = True, None
            server = EphemeralLoopbackServer(expected_state=state)
            port = server.start()
            self._active_server = server
        redirect = f"http://127.0.0.1:{port}/oauth2callback"
        url = build_authorization_url(config, redirect, state, derive_pkce_challenge(verifier))

        def complete_auth():
            try:
                code = server.wait_for_code(timeout_seconds=authorization_timeout)
                with self._state_lock:
                    if generation != self._generation:
                        return
                tokens = exchange_code_for_tokens(code, verifier, redirect, config)
                with self._state_lock:
                    if generation != self._generation:
                        return
                user = self._drive_client.get_about_user(access_token=tokens["access_token"])
                if not user.get("emailAddress"):
                    raise SyncAuthenticationError("Google did not return the connected account identity.")
                payload = {"access_token": tokens["access_token"], "refresh_token": tokens.get("refresh_token"),
                           "expires_at": time.time() + tokens.get("expires_in", 3600), "scope": tokens.get("scope"),
                           "account_email": user["emailAddress"], "connected_at": datetime.now(timezone.utc).isoformat()}
                with self._state_lock:
                    if generation != self._generation:
                        return
                    self.credentials.save_credentials(payload)
                    self._connecting, self._last_auth_error = False, None
            except Exception as exc:
                with self._state_lock:
                    if generation == self._generation:
                        self._connecting = False
                        self._last_auth_error = (str(exc) if isinstance(exc, (SyncAuthenticationError, SyncNetworkError, SyncConfigurationError))
                                                 else "Google authorization did not complete. Retry connection.")
            finally:
                server.close()

        if open_browser:
            try:
                launched = webbrowser.open(url)
            except Exception:
                launched = False
            if not launched:
                with self._state_lock:
                    self._generation += 1
                    self._connecting = False
                    self._last_auth_error = "The system browser could not open. Retry connection."
                server.close()
                raise SyncAuthenticationError(self._last_auth_error)
        thread = threading.Thread(target=complete_auth, daemon=True)
        self._active_auth_thread = thread
        thread.start()
        return {"status": "pending", "auth_url": url, "port": port,
                "message": "Complete authorization in the system browser, then wait for PESE to confirm connection."}

    def sync_now(self):
        if not self._operation_lock.acquire(blocking=False):
            raise SyncNetworkError("Another Google Drive operation is already running.")
        try:
            with self._state_lock:
                generation = self._generation
                if not self.is_connected():
                    raise SyncAuthenticationError("Connect Google Drive before uploading.")
            with tempfile.TemporaryDirectory(prefix="pese-upload-") as directory:
                bundle = create_snapshot(self._brain(), directory)
                record = self._drive_client.upload_snapshot(bundle)
            now = datetime.now(timezone.utc).isoformat()
            with self._state_lock:
                if generation != self._generation:
                    raise SyncAuthenticationError("Authorization changed during upload; completion was not recorded.")
                creds = self.credentials.load_credentials()
                if not creds:
                    raise SyncAuthenticationError("Google Drive was disconnected.")
                creds.setdefault("backups", {})[bundle.brain_id] = {"time": now, "snapshot_id": bundle.snapshot_id,
                                                                  "digest": bundle.manifest.integrity.content_digest}
                self.credentials.save_credentials(creds)
                self._last_auth_error = None
            return {"ok": True, "snapshot_id": bundle.snapshot_id, "drive_file_id": record.id,
                    "last_synced_at": now, "message": "Canonical Brain backup uploaded successfully."}
        except SyncAuthenticationError as exc:
            self._record_auth_error(exc, generation)
            raise
        finally:
            self._operation_lock.release()

    def restore_from_drive(self, snapshot_id=None):
        # Reject before network, download, or filesystem mutation.
        raise RestoreFailedError(RESTORE_DISABLED_REASON)

    def recover_to_new_brain(self, *, file_id, snapshot_id, brain_id, archive_sha256,
                             confirmed_local_digest, target):
        """Explicit offline-tool boundary. No activation/pointer change is performed.

        Selection and local-state confirmation are mandatory. Divergent cloud
        content is recovered separately; the original history remains intact.
        """
        from .restore import restore_snapshot
        if not all((file_id, snapshot_id, brain_id, archive_sha256, confirmed_local_digest)):
            raise RestoreFailedError("Explicit snapshot metadata and local-state confirmation are required.")
        if Path(target).exists():
            raise RestoreFailedError("Recovery requires a new directory.")
        with self._operation_lock:
            if open_brain(self._brain()).brain_id != brain_id:
                raise RestoreFailedError("Cross-Brain recovery is refused.")
            if canonical_state_digest(self._brain()) != confirmed_local_digest:
                raise RestoreFailedError("Local state changed since confirmation; inspect and confirm again.")
            records = self._drive_client.list_snapshots(brain_id)
            selected = next((record for record in records if record.id == file_id), None)
            expected = {"pese_brain_id": brain_id, "pese_snapshot_id": snapshot_id,
                        "pese_sha256": archive_sha256, "pese_sync_format_version": str(SYNC_FORMAT_VERSION)}
            if not selected or any(selected.properties.get(key) != value for key, value in expected.items()):
                raise RestoreFailedError("Selected Drive metadata changed or uses an incompatible format.")
            with tempfile.TemporaryDirectory(prefix="pese-download-") as directory:
                archive = Path(directory) / "selected.zip"
                self._drive_client.download_snapshot(file_id, archive, expected_sha256=archive_sha256)
                if canonical_state_digest(self._brain()) != confirmed_local_digest:
                    raise RestoreFailedError("Local state changed during download; recovery refused.")
                return restore_snapshot(archive, target, expected_brain_id=brain_id,
                                        expected_snapshot_id=snapshot_id, expected_zip_sha256=archive_sha256,
                                        expected_metadata=selected.properties)

    def list_remote_snapshots(self):
        if not self.is_connected():
            return []
        if not self._operation_lock.acquire(blocking=False):
            raise SyncNetworkError("Another Google Drive operation is already running.")
        generation = self._generation
        try:
            brain_id = open_brain(self._brain()).brain_id
            local_digest = canonical_state_digest(self._brain())
            records = self._drive_client.list_snapshots(brain_id)
            with self._state_lock:
                if generation == self._generation:
                    self._last_auth_error = None
            return [{"id": r.id, "name": r.name, "created_time": r.created_time, "size_bytes": r.size_bytes,
                     "brain_id": r.properties.get("pese_brain_id"), "snapshot_id": r.properties.get("pese_snapshot_id"),
                     "compatible": r.properties.get("pese_sync_format_version") == str(SYNC_FORMAT_VERSION),
                     "local_changes": r.properties.get("pese_content_digest") != local_digest,
                     "archive_sha256": r.properties.get("pese_sha256")} for r in records]
        except SyncAuthenticationError as exc:
            self._record_auth_error(exc, generation)
            raise
        finally:
            self._operation_lock.release()

    def disconnect(self):
        with self._state_lock:
            self._generation += 1
            self._connecting = False
            if self._active_server:
                self._active_server.close()
                self._active_server = None
            creds = self.credentials.load_credentials() or {}
            if not self.credentials.clear_credentials():
                self._last_auth_error = "Local authorization could not be removed. Disconnect failed."
                raise SyncAuthenticationError(self._last_auth_error)
            self._last_auth_error = None
        token = creds.get("refresh_token") or creds.get("access_token")
        revoked = revoke_token(token) if token else True
        return {"ok": True, "message": "Local authorization removed. Brain preserved." +
                ("" if revoked else " Google was unreachable; remote revocation could not be confirmed.")}
