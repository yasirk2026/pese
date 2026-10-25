"""Bounded Google HTTPS transport: no proxies, redirects or wildcard hosts."""
from contextlib import contextmanager
import urllib.parse
import urllib.request
import time
from ..desktop.offline import allow_sync_network
from .contracts import SyncConfigurationError


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_google_url(url):
    parsed = urllib.parse.urlsplit(url)
    valid_path = (
        parsed.hostname == "oauth2.googleapis.com" and parsed.path in ("/token", "/revoke")
        or parsed.hostname == "www.googleapis.com" and
        (parsed.path.startswith("/drive/v3/") or parsed.path.startswith("/upload/drive/v3/"))
    )
    if (parsed.scheme != "https" or parsed.port not in (None, 443) or
            parsed.username or parsed.password or parsed.fragment or not valid_path or
            ".." in parsed.path.split("/")):
        raise SyncConfigurationError("Only supported Google OAuth/Drive HTTPS endpoints are permitted.")


@contextmanager
def open_google(request, timeout=30.0):
    validate_google_url(request.full_url)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    deadline = time.monotonic() + timeout
    with allow_sync_network(timeout=timeout + 5):
        with opener.open(request, timeout=timeout) as response:
            class BoundedResponse:
                def read(self, *args):
                    if time.monotonic() > deadline:
                        raise TimeoutError("Google operation exceeded its deadline.")
                    data = response.read(*args)
                    if time.monotonic() > deadline:
                        raise TimeoutError("Google operation exceeded its deadline.")
                    return data

                def __getattr__(self, name):
                    return getattr(response, name)
            yield BoundedResponse()
