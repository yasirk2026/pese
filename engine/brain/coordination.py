"""One process-local boundary shared by canonical writers and snapshot capture.

The desktop launcher owns the cross-process writer lock. External editors are
unsupported while a Brain is open; they are never made safe by this lock.
"""
from functools import wraps
from threading import RLock
from pathlib import Path
import os

canonical_lock = RLock()
_desktop_writers = set()


def register_desktop_writer(path):
    _desktop_writers.add(Path(path).resolve())


def unregister_desktop_writer(path):
    _desktop_writers.discard(Path(path).resolve())


def ensure_capture_process(path):
    """A separate CLI cannot borrow the desktop process's in-memory barrier."""
    root = Path(path).resolve()
    lock_path = root / ".desktop-writer.lock"
    if root in _desktop_writers or not lock_path.exists():
        return
    if os.name == "nt":
        import msvcrt
        try:
            with lock_path.open("r+b") as handle:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError as exc:
            raise RuntimeError("This Brain is active in another process; capture/recovery must run in its owning runtime or after shutdown.") from exc
    else:
        raise RuntimeError("External writer-lock ownership is unsupported on this platform.")


def canonical_write(function):
    @wraps(function)
    def coordinated(*args, **kwargs):
        with canonical_lock:
            return function(*args, **kwargs)
    return coordinated
