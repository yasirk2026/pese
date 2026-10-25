"""Default-deny Python TCP/DNS boundary with scoped Google HTTPS access."""
import asyncio
import ipaddress
import socket
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar

GOOGLE_HOSTS = frozenset({"oauth2.googleapis.com", "www.googleapis.com"})
_permission = ContextVar("pese_google_transport", default=None)
_installed = False


def _owner():
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    return threading.get_ident(), id(task)


def _current():
    permission = _permission.get()
    if permission and permission[0] == _owner() and time.monotonic() < permission[1]:
        return permission
    return None


def _loopback(host):
    if host in (None, "localhost", b"localhost"):
        return True
    try:
        return ipaddress.ip_address(host.decode() if isinstance(host, bytes) else host).is_loopback
    except (ValueError, TypeError):
        return False


@contextmanager
def allow_sync_network(timeout=60.0):
    """Only the dedicated transport enters this synchronous capability scope.

    DNS grants resolved address/port pairs to this thread/task. Nested scopes
    restore the caller; permission cannot be inherited by child threads/tasks.
    """
    token = _permission.set((_owner(), time.monotonic() + timeout, set()))
    try:
        yield
    finally:
        _permission.reset(token)


def install_offline_boundary():
    global _installed
    if _installed:
        return
    _installed = True
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_resolve = socket.getaddrinfo
    original_sendto = socket.socket.sendto

    def authorized(address):
        if _loopback(address[0]):
            return True
        permission = _current()
        return bool(permission and (address[0], address[1]) in permission[2] and address[1] == 443)

    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _loopback(address[0]) and (self.type != socket.SOCK_STREAM or not authorized(address)):
            raise OSError("External networking is disabled in PESE Local Brain")
        return original_connect(self, address)

    def connect_ex(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _loopback(address[0]) and (self.type != socket.SOCK_STREAM or not authorized(address)):
            raise OSError("External networking is disabled in PESE Local Brain")
        return original_connect_ex(self, address)

    def resolve(host, port, *args, **kwargs):
        if _loopback(host):
            return original_resolve(host, port, *args, **kwargs)
        permission = _current()
        name = host.decode() if isinstance(host, bytes) else host
        if not permission or name not in GOOGLE_HOSTS or port not in (443, "443"):
            raise OSError("External DNS is disabled in PESE Local Brain")
        results = original_resolve(host, port, *args, **kwargs)
        for family, kind, proto, canon, address in results:
            if family in (socket.AF_INET, socket.AF_INET6) and kind == socket.SOCK_STREAM and ipaddress.ip_address(address[0]).is_global:
                permission[2].add((address[0], address[1]))
        return results

    def sendto(self, data, *args):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _loopback(args[-1][0]):
            raise OSError("External networking is disabled in PESE Local Brain")
        return original_sendto(self, data, *args)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.socket.sendto = sendto
    socket.getaddrinfo = resolve
