"""Cooperative CPU priority: secondary loops yield between bounded candidates."""
from contextlib import contextmanager
from threading import Lock

_lock = Lock()
_primary = 0


@contextmanager
def primary_request():
    global _primary
    with _lock:
        _primary += 1
    try:
        yield
    finally:
        with _lock:
            _primary -= 1


def primary_pending():
    with _lock:
        return _primary > 0
