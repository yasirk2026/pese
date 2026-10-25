"""
PESE Secure Credential Storage: Windows DPAPI Protection for OAuth Tokens.
Tokens are stored encrypted under the user's Windows profile, outside Brain and Git.
"""

import json
import os
import sys
import tempfile
import threading
from copy import deepcopy
from functools import wraps
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional

from ..brain.resolver import get_default_local_appdata_dir

CREDENTIALS_FILENAME = "google_drive_credentials.dat"


_storage_lock = threading.RLock()


def credential_operation(function):
    @wraps(function)
    def locked(*args, **kwargs):
        with _storage_lock:
            return function(*args, **kwargs)
    return locked


class BaseCredentialStorage(ABC):
    """Abstract interface for secure token storage."""

    @abstractmethod
    def save_credentials(self, token_data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def load_credentials(self) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def clear_credentials(self) -> bool:
        pass


class WindowsDPAPICredentialStorage(BaseCredentialStorage):
    """
    Encrypts OAuth credentials using the Windows Data Protection API (DPAPI).
    The ciphertext can only be decrypted by the current logged-in Windows user account.
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = Path(storage_dir) if storage_dir else get_default_local_appdata_dir()
        self.storage_path = self.storage_dir / CREDENTIALS_FILENAME

    def _protect_bytes(self, data: bytes) -> bytes:
        if sys.platform != "win32":
            raise RuntimeError("Secure platform credential storage is required; plaintext fallback is forbidden.")

        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        data_bytes = (ctypes.c_byte * len(data))(*data)
        in_blob = DATA_BLOB(len(data), data_bytes)
        out_blob = DATA_BLOB()

        if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(in_blob), "PESE Google Drive Credential", None, None, None, 0, ctypes.byref(out_blob)
        ):
            raise ctypes.WinError()

        res = bytes(ctypes.cast(out_blob.pbData, ctypes.POINTER(ctypes.c_byte * out_blob.cbData)).contents)
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return res

    def _unprotect_bytes(self, cipher: bytes) -> bytes:
        if sys.platform != "win32":
            raise RuntimeError("Secure platform credential storage is required.")

        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        data_bytes = (ctypes.c_byte * len(cipher))(*cipher)
        in_blob = DATA_BLOB(len(cipher), data_bytes)
        out_blob = DATA_BLOB()

        if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
        ):
            raise ctypes.WinError()

        res = bytes(ctypes.cast(out_blob.pbData, ctypes.POINTER(ctypes.c_byte * out_blob.cbData)).contents)
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return res

    @credential_operation
    def save_credentials(self, token_data: Dict[str, Any]) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        raw_json = json.dumps(token_data, ensure_ascii=False).encode("utf-8")
        encrypted = self._protect_bytes(raw_json)

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.storage_dir, prefix=".google-", delete=False) as handle:
                temp_path = Path(handle.name)
                handle.write(encrypted)
                handle.flush()
                os.fsync(handle.fileno())
            temp_path.replace(self.storage_path)
        finally:
            if temp_path:
                temp_path.unlink(missing_ok=True)

    @credential_operation
    def load_credentials(self) -> Optional[Dict[str, Any]]:
        if not self.storage_path.exists():
            return None
        try:
            with open(self.storage_path, "rb") as f:
                encrypted = f.read()
            if not encrypted:
                return None
            decrypted = self._unprotect_bytes(encrypted)
            return json.loads(decrypted.decode("utf-8"))
        except Exception:
            # Corrupted or un-decryptable credentials treated as absent
            return None

    @credential_operation
    def clear_credentials(self) -> bool:
        if self.storage_path.exists():
            try:
                self.storage_path.unlink()
                return True
            except OSError:
                return False
        return True


class MemoryCredentialStorage(BaseCredentialStorage):
    """In-memory credential store for tests and simulations."""

    def __init__(self, initial_data: Optional[Dict[str, Any]] = None):
        self._data: Optional[Dict[str, Any]] = deepcopy(initial_data) if initial_data else None

    @credential_operation
    def save_credentials(self, token_data: Dict[str, Any]) -> None:
        self._data = deepcopy(token_data)

    @credential_operation
    def load_credentials(self) -> Optional[Dict[str, Any]]:
        return deepcopy(self._data) if self._data is not None else None

    @credential_operation
    def clear_credentials(self) -> bool:
        self._data = None
        return True


def get_credential_storage(custom_dir: Optional[Path] = None) -> BaseCredentialStorage:
    """Default factory returning Windows DPAPI secure credential storage."""
    return WindowsDPAPICredentialStorage(storage_dir=custom_dir)
