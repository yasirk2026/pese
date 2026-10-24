"""
PESE Brain Resolver: Single Authoritative Brain Path Resolution
Defines the authoritative path resolution chain and machine-local pointer
management for desktop installations.
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, Union

from .contracts import (
    BrainMissingError,
    BrainNotConfiguredError,
    BrainInvalidError,
    BRAIN_MANIFEST_FILENAME,
)
from .atomic import atomic_write_json


DESKTOP_VENDOR_NAME = "ManiacSoftwares"
DESKTOP_APP_NAME = "PESE"
DESKTOP_SETTINGS_FILENAME = "desktop-settings.json"


def get_default_local_appdata_dir() -> Path:
    """
    Returns the machine-local application profile directory.
    Windows: %LOCALAPPDATA%\\ManiacSoftwares\\PESE
    Non-Windows / Fallback: ~/.pese
    """
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / DESKTOP_VENDOR_NAME / DESKTOP_APP_NAME
    return Path.home() / ".pese"


def get_desktop_settings_path(custom_base_dir: Optional[Path] = None) -> Path:
    """
    Returns the path to the machine-local settings file storing the Brain pointer.
    """
    base = Path(custom_base_dir) if custom_base_dir else get_default_local_appdata_dir()
    return base / DESKTOP_SETTINGS_FILENAME


def load_desktop_brain_pointer(settings_file: Optional[Path] = None) -> Optional[Path]:
    """
    Reads the machine-local pointer to determine the user-configured Brain directory.
    Returns None if no pointer file exists.
    """
    path = settings_file or get_desktop_settings_path()
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            brain_path_str = data.get("brainPath")
            if brain_path_str and isinstance(brain_path_str, str):
                return Path(brain_path_str).resolve()
    except Exception:
        # Corrupt settings file treated as absent
        return None
    return None


def save_desktop_brain_pointer(
    brain_path: Union[str, Path],
    settings_file: Optional[Path] = None
) -> Path:
    """
    Persists the machine-local pointer to the selected Brain directory.
    Losing this file on Windows reset does NOT damage the Brain.
    """
    target_settings = settings_file or get_desktop_settings_path()
    resolved_brain = Path(brain_path).resolve()

    payload = {
        "brainPath": str(resolved_brain)
    }
    atomic_write_json(target_settings, payload)
    return target_settings


def clear_desktop_brain_pointer(settings_file: Optional[Path] = None) -> bool:
    """
    Removes the machine-local pointer file (simulating Windows reset or disconnect).
    """
    path = settings_file or get_desktop_settings_path()
    if path.exists():
        try:
            path.unlink()
            return True
        except OSError:
            return False
    return False


def resolve_brain_path(
    explicit_path: Optional[Union[str, Path]] = None,
    allow_dev_fallback: bool = True,
    custom_settings_file: Optional[Path] = None
) -> Path:
    """
    The Single Authoritative Brain Path Resolver.

    Resolution Priority:
      1. Explicit argument provided by Desktop Host / CLI (`explicit_path`).
      2. Environment variable (`PESE_DATA_DIR` or `PESE_BRAIN_PATH`).
      3. Machine-local pointer (`desktop-settings.json`).
      4. Development fallback ONLY when allow_dev_fallback=True and in non-production.

    CRITICAL SAFETY INVARIANT:
      If a path was explicitly provided, set via environment variable, or retrieved
      from desktop-settings.json, it MUST exist on disk.
      If it does not exist (e.g. D: drive disconnected), this function MUST raise
      BrainMissingError. It must NEVER silently fall back to another location or
      create an empty Brain.
    """
    # 1. Explicit argument
    if explicit_path is not None:
        p = Path(explicit_path).resolve()
        if not p.exists() or not p.is_dir():
            raise BrainMissingError(p, f"Explicit Brain path does not exist on disk: {p}")
        return p

    # 2. Environment variable
    env_brain = os.getenv("PESE_BRAIN_PATH") or os.getenv("PESE_DATA_DIR")
    if env_brain:
        p = Path(env_brain).resolve()
        if not p.exists() or not p.is_dir():
            raise BrainMissingError(p, f"Configured Brain environment path does not exist: {p}")
        return p

    # 3. Machine-local pointer
    pointer_path = load_desktop_brain_pointer(settings_file=custom_settings_file)
    if pointer_path is not None:
        if not pointer_path.exists() or not pointer_path.is_dir():
            raise BrainMissingError(
                pointer_path,
                f"Configured Brain at '{pointer_path}' could not be reached. The drive may be unmounted or disconnected."
            )
        return pointer_path

    # 4. Development fallback
    is_production = os.getenv("PESE_ENV", "").lower() == "production"
    if allow_dev_fallback and not is_production:
        dev_data_dir = Path(__file__).resolve().parent.parent / "data"
        if dev_data_dir.exists():
            return dev_data_dir

    # If in production or fallback disabled, require explicit configuration
    raise BrainNotConfiguredError(
        "No PESE Brain has been configured. Select an existing Brain or initialize a new Brain."
    )
