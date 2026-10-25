"""
PESE Google OAuth 2.0 PKCE Flow for Desktop (RFC 7636).
Implements Authorization Code flow with PKCE, loopback ephemeral server on 127.0.0.1,
and system browser launch.
"""

import base64
import hashlib
import json
import os
import secrets
import threading
import urllib.parse
import urllib.request
import html
from .transport import open_google
from dataclasses import dataclass
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from ..brain.resolver import get_default_local_appdata_dir
from .contracts import (
    GOOGLE_DRIVE_APPDATA_SCOPE,
    OAUTH_AUTH_ENDPOINT,
    OAUTH_TOKEN_ENDPOINT,
    OAUTH_REVOKE_ENDPOINT,
    SyncConfigurationError,
    SyncAuthenticationError,
    SyncNetworkError,
)

OAUTH_CONFIG_FILENAME = "google-oauth-config.json"


@dataclass
class OAuthClientConfig:
    client_id: str
    client_secret: Optional[str] = None
    auth_uri: str = OAUTH_AUTH_ENDPOINT
    token_uri: str = OAUTH_TOKEN_ENDPOINT
    revoke_uri: str = OAUTH_REVOKE_ENDPOINT
    scope: str = GOOGLE_DRIVE_APPDATA_SCOPE

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OAuthClientConfig":
        # Desktop client JSON only; flat source-development configuration is also supported.
        if "web" in data or data.get("type") == "service_account" or "private_key" in data:
            raise SyncConfigurationError("Use a Google Desktop OAuth client, not a Web client.")
        installed = data.get("installed") or data
        client_id = installed.get("client_id")
        if not client_id:
            raise SyncConfigurationError("Invalid Google OAuth configuration: missing 'client_id'.")
        auth_uris = {OAUTH_AUTH_ENDPOINT, "https://accounts.google.com/o/oauth2/auth"}
        if installed.get("auth_uri", OAUTH_AUTH_ENDPOINT) not in auth_uris or installed.get("token_uri", OAUTH_TOKEN_ENDPOINT) != OAUTH_TOKEN_ENDPOINT:
            raise SyncConfigurationError("Unsupported OAuth endpoints.")
        return cls(
            client_id=client_id,
            client_secret=installed.get("client_secret"),
            auth_uri=OAUTH_AUTH_ENDPOINT,
            token_uri=installed.get("token_uri", OAUTH_TOKEN_ENDPOINT),
            revoke_uri=OAUTH_REVOKE_ENDPOINT,
            scope=GOOGLE_DRIVE_APPDATA_SCOPE,
        )


def load_oauth_client_config(custom_path: Optional[Path] = None) -> Optional[OAuthClientConfig]:
    """
    Loads OAuth client configuration from:
      1. Environment variables (PESE_GOOGLE_CLIENT_ID / PESE_GOOGLE_CLIENT_SECRET)
      2. Configuration file (google-oauth-config.json) outside Git/Brain
      Returns None if no client configuration is found.
    """
    env_id = os.environ.get("PESE_GOOGLE_CLIENT_ID")
    if env_id:
        return OAuthClientConfig(
            client_id=env_id.strip(),
            client_secret=os.environ.get("PESE_GOOGLE_CLIENT_SECRET", "").strip() or None,
        )

    config_path = Path(custom_path) if custom_path else get_default_local_appdata_dir() / OAUTH_CONFIG_FILENAME
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return OAuthClientConfig.from_dict(data)
        except Exception as exc:
            raise SyncConfigurationError(f"Failed to parse OAuth config at {config_path}: {exc}") from exc

    return None


def generate_pkce_verifier() -> str:
    """Generates an RFC 7636 compliant high-entropy code_verifier."""
    # 64 bytes urlsafe yields an 86-character string in [A-Za-z0-9_-]
    return secrets.token_urlsafe(64)


def derive_pkce_challenge(verifier: str) -> str:
    """Derives S256 code_challenge from code_verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def generate_oauth_state() -> str:
    """Generates a secure random OAuth state string for CSRF mitigation."""
    return secrets.token_hex(24)


def build_authorization_url(
    config: OAuthClientConfig,
    redirect_uri: str,
    state: str,
    code_challenge: str,
) -> str:
    """Constructs the Google OAuth 2.0 authorization URL."""
    params = {
        "client_id": config.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": config.scope,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{config.auth_uri}?{urllib.parse.urlencode(params)}"


class EphemeralLoopbackServer:
    """
    Temporary single-request HTTP server listening on loopback (127.0.0.1:0)
    for Google OAuth authorization code redirect.
    """

    def __init__(self, expected_state: str):
        self.expected_state = expected_state
        self.auth_code: Optional[str] = None
        self.error: Optional[str] = None
        self.server: Optional[HTTPServer] = None
        self.port: int = 0
        self._shutdown_event = threading.Event()

    def start(self) -> int:
        parent = self

        class Handler(BaseHTTPRequestHandler):
            timeout = 2.0
            def log_message(self, format, *args):
                pass  # Suppress console logging

            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != "/oauth2callback":
                    self.send_error(404)
                    return
                query = urllib.parse.parse_qs(parsed.query)

                received_state = query.get("state", [""])[0]
                if received_state != parent.expected_state:
                    # Ignore unrelated requests instead of cancelling valid authorization.
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"<h1>Authentication Failed</h1><p>State validation failed.</p>")
                    return

                if "error" in query:
                    parent.error = query.get("error", ["Unknown error"])[0]
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(f"<h1>Authentication Error</h1><p>{html.escape(parent.error)}</p>".encode("utf-8"))
                    parent._shutdown_event.set()
                    return

                code = query.get("code", [""])[0]
                if not code:
                    parent.error = "No authorization code returned from Google."
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"<h1>Authentication Failed</h1><p>No code returned.</p>")
                    parent._shutdown_event.set()
                    return

                parent.auth_code = code
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                html = (
                    "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                    "<title>PESE — Connected</title>"
                    "<style>body{background:#090d16;color:#f1f5f9;font-family:system-ui,sans-serif;"
                    "display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}"
                    ".card{background:#111827;padding:36px;border-radius:16px;border:1px solid #1f293d;"
                    "text-align:center;max-width:440px;box-shadow:0 10px 25px rgba(0,0,0,0.5);}"
                    "h2{margin-top:0;color:#60a5fa;}p{color:#94a3b8;font-size:14px;}</style></head>"
                    "<body><div class='card'><h2>Authorization Received</h2>"
                    "<p>Authorization received. Return to PESE to check whether connection completes.</p>"
                    "<p>You can close this tab and return to PESE.</p></div></body></html>"
                )
                self.wfile.write(html.encode("utf-8"))
                parent._shutdown_event.set()

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.server.timeout = 0.2
        self.port = self.server.server_port

        def run():
            while not self._shutdown_event.is_set():
                self.server.handle_request()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return self.port

    def wait_for_code(self, timeout_seconds: float = 120.0) -> str:
        """Blocks until the browser redirects with the code, or times out."""
        finished = self._shutdown_event.wait(timeout=timeout_seconds)
        self.close()

        if not finished:
            raise SyncAuthenticationError("OAuth authorization timed out. Please try again.")
        if self.error:
            raise SyncAuthenticationError(f"OAuth authorization error: {self.error}")
        if not self.auth_code:
            raise SyncAuthenticationError("OAuth authorization failed to capture code.")
        return self.auth_code

    def close(self):
        self._shutdown_event.set()
        if self.server:
            try:
                self.server.server_close()
            except Exception:
                pass


def exchange_code_for_tokens(
    code: str,
    code_verifier: str,
    redirect_uri: str,
    config: OAuthClientConfig,
) -> Dict[str, Any]:
    """Exchanges an authorization code and PKCE verifier for OAuth tokens."""
    data = {
        "client_id": config.client_id,
        "code": code,
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    if config.client_secret:
        data["client_secret"] = config.client_secret

    encoded_data = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        config.token_uri,
        data=encoded_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with open_google(req, timeout=15.0) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as http_err:
        err_msg = "Google rejected the authorization request"
        raise SyncAuthenticationError(f"Failed to exchange OAuth code: HTTP {http_err.code} - {err_msg}") from http_err
    except Exception as exc:
        raise SyncNetworkError(f"Network error during OAuth token exchange: {exc}") from exc


def refresh_access_token(
    refresh_token: str,
    config: OAuthClientConfig,
) -> Dict[str, Any]:
    """Uses refresh_token to obtain a fresh access token."""
    data = {
        "client_id": config.client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    if config.client_secret:
        data["client_secret"] = config.client_secret

    encoded_data = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        config.token_uri,
        data=encoded_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with open_google(req, timeout=15.0) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as http_err:
        err_msg = "Google rejected the authorization request"
        raise SyncAuthenticationError(f"Failed to refresh OAuth token: HTTP {http_err.code} - {err_msg}") from http_err
    except Exception as exc:
        raise SyncNetworkError(f"Network error during OAuth token refresh: {exc}") from exc


def revoke_token(token: str) -> bool:
    """Revokes an access or refresh token with Google."""
    params = urllib.parse.urlencode({"token": token})
    url = f"{OAUTH_REVOKE_ENDPOINT}?{params}"
    req = urllib.request.Request(url, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")

    try:
        with open_google(req, timeout=10.0) as resp:
            return resp.status == 200
    except Exception:
        # Best effort revocation
        return False
