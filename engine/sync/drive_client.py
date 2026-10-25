"""Bounded, streaming Drive appDataFolder transport with complete pagination."""
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from .contracts import (DriveFileRecord, DRIVE_FILES_ENDPOINT, DRIVE_UPLOAD_ENDPOINT,
                        CURRENT_APP_VERSION, CURRENT_SCHEMA_VERSION, SYNC_FORMAT_VERSION,
                        SyncNetworkError, SyncAuthenticationError, CorruptSnapshotError)
from .payload import MAX_ARCHIVE_BYTES
from .transport import open_google


class MultipartBody:
    def __init__(self, path, prefix, suffix):
        self.path, self.prefix, self.suffix = Path(path), prefix, suffix
        self.size = len(prefix) + self.path.stat().st_size + len(suffix)

    def __iter__(self):
        deadline = time.monotonic() + 60
        yield self.prefix
        with self.path.open("rb") as source:
            while chunk := source.read(65536):
                if time.monotonic() > deadline:
                    raise TimeoutError("Upload exceeded its deadline.")
                yield chunk
        yield self.suffix


class GoogleDriveClient:
    def __init__(self, token_provider):
        self.get_token = token_provider

    def _authorized_request(self, url, data=None, headers=None, method="GET", timeout=30.0, token=None):
        return urllib.request.Request(url, data=data, headers={
            "Authorization": "Bearer " + (token if token is not None else self.get_token()),
            "Accept": "application/json", **(headers or {})}, method=method)

    @contextmanager
    def _request(self, url, *, timeout=30.0, **kwargs):
        request = self._authorized_request(url, **kwargs)
        try:
            with open_google(request, timeout=timeout) as response:
                yield response
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise SyncAuthenticationError(f"Google authorization failed (HTTP {exc.code}).") from exc
            raise SyncNetworkError(f"Google request failed (HTTP {exc.code}).") from exc
        except (SyncAuthenticationError, CorruptSnapshotError):
            raise
        except Exception as exc:
            raise SyncNetworkError("Google Drive is unavailable; local search remains available.") from exc

    def _json(self, url, **kwargs):
        with self._request(url, **kwargs) as response:
            data = response.read(1024 * 1024 + 1)
            if len(data) > 1024 * 1024:
                raise SyncNetworkError("Google metadata response exceeds limit.")
            return json.loads(data)

    def list_snapshots(self, brain_id=None):
        records, page_token, seen_tokens = [], None, set()
        while True:
            params = {"spaces": "appDataFolder", "fields": "nextPageToken,files(id,name,createdTime,modifiedTime,size,properties)",
                      "orderBy": "createdTime desc", "pageSize": 100,
                      "q": "trashed = false and properties has { key='pese_format' and value='pese-snapshot' }"}
            if page_token:
                params["pageToken"] = page_token
            data = self._json(DRIVE_FILES_ENDPOINT + "?" + urllib.parse.urlencode(params), timeout=15)
            for item in data.get("files", []):
                props = item.get("properties") or {}
                if props.get("pese_format") != "pese-snapshot":
                    continue
                if brain_id and props.get("pese_brain_id") != brain_id:
                    continue
                records.append(DriveFileRecord(id=item["id"], name=item["name"], created_time=item.get("createdTime", ""),
                                               modified_time=item.get("modifiedTime"), size_bytes=int(item.get("size", 0)),
                                               properties=props))
            page_token = data.get("nextPageToken")
            if not page_token:
                return records
            if page_token in seen_tokens:
                raise SyncNetworkError("Google returned repeated pagination tokens.")
            seen_tokens.add(page_token)

    def get_latest_snapshot(self, brain_id=None):
        records = self.list_snapshots(brain_id)
        return records[0] if records else None

    def upload_snapshot(self, bundle):
        if bundle.zip_path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise SyncNetworkError("Snapshot exceeds upload limit.")
        boundary = "PESE-SNAPSHOT-" + bundle.snapshot_id
        properties = {"pese_format": "pese-snapshot", "pese_brain_id": bundle.brain_id,
                      "pese_snapshot_id": bundle.snapshot_id, "pese_app_version": CURRENT_APP_VERSION,
                      "pese_schema_version": str(CURRENT_SCHEMA_VERSION), "pese_sync_format_version": str(SYNC_FORMAT_VERSION),
                      "pese_sha256": bundle.zip_sha256, "pese_content_digest": bundle.manifest.integrity.content_digest}
        metadata = {"name": "pese-snapshot-" + bundle.snapshot_id + ".zip", "parents": ["appDataFolder"], "properties": properties}
        prefix = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
                  + json.dumps(metadata).encode() + f"\r\n--{boundary}\r\nContent-Type: application/zip\r\n\r\n".encode())
        body = MultipartBody(bundle.zip_path, prefix, f"\r\n--{boundary}--\r\n".encode())
        data = self._json(DRIVE_UPLOAD_ENDPOINT + "?uploadType=multipart&fields=id,name,createdTime",
                          data=body, headers={"Content-Type": f"multipart/related; boundary={boundary}", "Content-Length": str(body.size)},
                          method="POST", timeout=60)
        return DriveFileRecord(id=data["id"], name=data.get("name", metadata["name"]),
                               created_time=data.get("createdTime", ""), size_bytes=bundle.total_size_bytes, properties=properties)

    def download_snapshot(self, file_id, destination_path, expected_sha256=None):
        destination = Path(destination_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest, total = hashlib.sha256(), 0
        created = False
        try:
            with self._request(DRIVE_FILES_ENDPOINT + "/" + urllib.parse.quote(file_id, safe="") + "?alt=media", timeout=60) as response:
                with destination.open("xb") as target:
                    created = True
                    while chunk := response.read(65536):
                        total += len(chunk)
                        if total > MAX_ARCHIVE_BYTES:
                            raise CorruptSnapshotError("Downloaded archive exceeds size limit.")
                        digest.update(chunk)
                        target.write(chunk)
            if expected_sha256 and digest.hexdigest() != expected_sha256:
                raise CorruptSnapshotError("Downloaded archive digest differs from Drive metadata.")
            return destination
        except Exception:
            if created:
                destination.unlink(missing_ok=True)
            raise

    def delete_snapshot(self, file_id):
        with self._request(DRIVE_FILES_ENDPOINT + "/" + urllib.parse.quote(file_id, safe=""), method="DELETE", timeout=15):
            return True

    def get_about_user(self, access_token=None):
        data = self._json("https://www.googleapis.com/drive/v3/about?fields=user(emailAddress,displayName)",
                          token=access_token, timeout=10)
        return data.get("user", {})
