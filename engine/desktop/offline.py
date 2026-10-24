"""Local Brain release never opens external Python network connections.

This also makes the installed acceptance independent of the machine's Wi-Fi.
Future sync must be an explicit, separate integration rather than a hidden model fetch.
"""
import ipaddress
import socket


def install_offline_boundary():
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_resolve = socket.getaddrinfo

    def allowed(host):
        if host is None or host in ("localhost", b"localhost"):
            return True
        try:
            return ipaddress.ip_address(host.decode() if isinstance(host, bytes) else host).is_loopback
        except ValueError:
            return False

    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not allowed(address[0]):
            raise OSError("External networking is disabled in PESE Local Brain")
        return original_connect(self, address)

    def connect_ex(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not allowed(address[0]):
            raise OSError("External networking is disabled in PESE Local Brain")
        return original_connect_ex(self, address)

    def resolve(host, *args, **kwargs):
        if not allowed(host):
            raise OSError("External DNS is disabled in PESE Local Brain")
        return original_resolve(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = resolve
