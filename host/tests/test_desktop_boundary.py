"""Desktop-specific tests, separate from the frozen 322-test engine baseline."""
import asyncio
import json
import pytest
from pathlib import Path
from engine.desktop.security import DesktopBoundary
from engine.desktop.launcher import brain_command, validate_brain


async def request(path, token=None, origin=None, host="127.0.0.1:12345", stopping=False):
    output = []

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def send(message):
        output.append(message)

    headers = [(b"host", host.encode())]
    if token is not None:
        headers.append((b"x-pese-token", token.encode()))
    if origin:
        headers.append((b"origin", origin.encode()))
    boundary = DesktopBoundary(app, "a" * 64, "http://127.0.0.1:12345", is_stopping=lambda: stopping)
    await boundary({"type": "http", "path": path, "headers": headers}, None, send)
    return output[0]


@pytest.mark.parametrize("path", ["/api/search", "/api/documents", "/api/search/feedback", "/health", "/desktop/shutdown"])
def test_private_endpoints_require_launch_token(path):
    assert asyncio.run(request(path))["status"] == 401
    assert asyncio.run(request(path, "bad"))["status"] == 401
    assert asyncio.run(request(path, "a" * 64))["status"] == 200


def test_foreign_origin_and_dns_rebinding_rejected():
    assert asyncio.run(request("/api/search", "a" * 64, "https://evil.example"))["status"] == 403
    assert asyncio.run(request("/", host="evil.example:12345"))["status"] == 403
    assert asyncio.run(request("/_next/static/a.js"))["status"] == 200


def test_security_headers():
    result = asyncio.run(request("/api/search", "a" * 64))
    headers = dict(result["headers"])
    assert headers[b"cache-control"] == b"no-store"
    assert b"frame-ancestors 'none'" in headers[b"content-security-policy"]
    assert b"connect-src 'self'" in headers[b"content-security-policy"]


def test_nonempty_folder_never_modified(tmp_path):
    target = tmp_path / "arbitrary"
    target.mkdir()
    file = target / "important.txt"
    file.write_text("preserve")
    with pytest.raises(ValueError, match="not empty"):
        brain_command({"action": "create", "brainPath": str(target)})
    assert file.read_text() == "preserve"
    assert not (target / "pese-brain.json").exists()


def test_desktop_rejects_incomplete_brain_without_repair(tmp_path):
    from engine.brain import initialize_brain
    target = tmp_path / "brain"
    initialize_brain(target)
    (target / "privacy_settings.json").unlink()
    with pytest.raises(Exception, match="Missing required Brain file"):
        validate_brain(target)
    assert not (target / "privacy_settings.json").exists()


def test_initialize_and_reconnect_identity(tmp_path, monkeypatch):
    # Redirect only the machine pointer, keeping the actual public Brain APIs.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    path = tmp_path / "Brain with spaces — علم"
    first = brain_command({"action": "create", "brainPath": str(path)})
    second = brain_command({"action": "connect", "brainPath": str(path)})
    assert first["brain"]["brain_id"] == second["brain"]["brain_id"]
    pointer = tmp_path / "profile/ManiacSoftwares/PESE/desktop-settings.json"
    assert json.loads(pointer.read_text(encoding="utf-8"))["brainPath"] == str(path.resolve())
    pointer.unlink()  # Reinstall/reset loses only a pointer, not knowledge.
    third = brain_command({"action": "connect", "brainPath": str(path)})
    assert third["brain"]["brain_id"] == first["brain"]["brain_id"]


def test_fresh_brain_uses_runtime_search_sync_schema(tmp_path):
    import sqlite3
    from engine.brain import initialize_brain
    path = tmp_path / "fresh"
    initialize_brain(path)
    validate_brain(path)
    with sqlite3.connect(path / "search_sync_feedback.db") as db:
        assert "metadata_json" in {row[1] for row in db.execute("PRAGMA table_info(active_preferences)")}
        assert "search_context_id" in {row[1] for row in db.execute("PRAGMA table_info(neural_shadow_observations)")}
        assert db.execute("SELECT count(*) FROM feedback_audit_events").fetchone()[0] == 0


def test_external_python_connections_are_blocked(monkeypatch):
    import socket
    from engine.desktop.offline import install_offline_boundary
    for cls, name in ((socket.socket, "connect"), (socket.socket, "connect_ex"), (socket, "getaddrinfo")):
        monkeypatch.setattr(cls, name, getattr(cls, name))
    install_offline_boundary()
    with socket.socket() as connection:
        with pytest.raises(OSError, match="External networking"):
            connection.connect(("192.0.2.1", 443))
    with pytest.raises(OSError, match="External DNS"):
        socket.getaddrinfo("example.com", 443)


def test_entire_velopack_install_tree_is_forbidden(tmp_path, monkeypatch):
    from engine.desktop import launcher
    install = tmp_path / "ManiacSoftwares.PESE"
    current = install / "current"
    current.mkdir(parents=True)
    (install / "Update.exe").write_bytes(b"installer marker")
    monkeypatch.setattr(launcher, "APP_ROOT", current)
    unsafe = install / "Brain beside current"
    with pytest.raises(ValueError, match="outside the PESE installation"):
        launcher.brain_command({"action": "create", "brainPath": str(unsafe)})
    assert not unsafe.exists()
    with pytest.raises(ValueError, match="outside the PESE installation"):
        launcher.validate_brain(install)


def test_update_shutdown_rejects_new_operations_but_preserves_auth():
    assert asyncio.run(request("/api/search", "a" * 64, stopping=True))["status"] == 503
    assert asyncio.run(request("/api/search/feedback", "a" * 64, stopping=True))["status"] == 503
    assert asyncio.run(request("/api/search", "bad", stopping=True))["status"] == 401
    assert asyncio.run(request("/desktop/shutdown", "a" * 64, stopping=True))["status"] == 200
    assert asyncio.run(request("/health", "a" * 64, stopping=True))["status"] == 200
