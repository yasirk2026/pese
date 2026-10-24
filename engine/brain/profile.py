"""
PESE Brain Profile: Local-first, portable User Profile & Account Infrastructure.

Stores user identity metadata alongside the selected Brain:
  Brain/profile/profile.json
  Brain/profile/avatar.<ext>

All paths in profile.json are relative and platform-independent to guarantee portability
across Local Sync, Google Drive Sync, and future platforms.
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from .atomic import atomic_write_json
from .resolver import resolve_brain_path

PROFILE_DIR_NAME = "profile"
PROFILE_JSON_FILENAME = "profile.json"
ALLOWED_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


class ProfileAvatar(BaseModel):
    relative_path: Optional[str] = None


class UserProfile(BaseModel):
    schema_version: int = 1
    display_name: str = "Local User"
    about: str = ""
    avatar: Optional[ProfileAvatar] = None
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _get_profile_dir(brain_path: Optional[Path] = None) -> Path:
    base = Path(brain_path) if brain_path else resolve_brain_path(allow_dev_fallback=True)
    pdir = base / PROFILE_DIR_NAME
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir


def load_profile(brain_path: Optional[Path] = None) -> UserProfile:
    """Load the current profile from the selected Brain or return default if uninitialized."""
    pdir = _get_profile_dir(brain_path)
    pfile = pdir / PROFILE_JSON_FILENAME
    if not pfile.exists():
        return UserProfile()
    try:
        with open(pfile, "r", encoding="utf-8") as f:
            data = json.load(f)
        return UserProfile(**data)
    except Exception:
        return UserProfile()


def save_profile(
    display_name: str,
    about: str,
    brain_path: Optional[Path] = None
) -> UserProfile:
    """Update profile metadata (display name and about) preserving avatar."""
    current = load_profile(brain_path)
    updated = UserProfile(
        schema_version=current.schema_version,
        display_name=display_name.strip() or "Local User",
        about=about.strip(),
        avatar=current.avatar,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    pdir = _get_profile_dir(brain_path)
    atomic_write_json(pdir / PROFILE_JSON_FILENAME, updated.model_dump())
    return updated


def import_avatar(
    image_bytes: bytes,
    original_filename: str,
    brain_path: Optional[Path] = None
) -> UserProfile:
    """Import/copy image bytes into Brain-owned storage and update profile."""
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        ext = ".png"

    pdir = _get_profile_dir(brain_path)

    # Clean up any existing avatars
    for existing in pdir.glob("avatar.*"):
        try:
            existing.unlink()
        except Exception:
            pass

    avatar_filename = f"avatar{ext}"
    avatar_file = pdir / avatar_filename
    temp_file = pdir / f"avatar_tmp{ext}"

    with open(temp_file, "wb") as f:
        f.write(image_bytes)
        f.flush()
        os.fsync(f.fileno())
    temp_file.replace(avatar_file)

    current = load_profile(brain_path)
    updated = UserProfile(
        schema_version=current.schema_version,
        display_name=current.display_name,
        about=current.about,
        avatar=ProfileAvatar(relative_path=f"{PROFILE_DIR_NAME}/{avatar_filename}"),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    atomic_write_json(pdir / PROFILE_JSON_FILENAME, updated.model_dump())
    return updated


def remove_avatar(brain_path: Optional[Path] = None) -> UserProfile:
    """Delete avatar image from Brain and clear reference."""
    pdir = _get_profile_dir(brain_path)
    for existing in pdir.glob("avatar.*"):
        try:
            existing.unlink()
        except Exception:
            pass

    current = load_profile(brain_path)
    updated = UserProfile(
        schema_version=current.schema_version,
        display_name=current.display_name,
        about=current.about,
        avatar=None,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    atomic_write_json(pdir / PROFILE_JSON_FILENAME, updated.model_dump())
    return updated


def get_avatar_file(brain_path: Optional[Path] = None) -> Optional[Path]:
    """Get absolute path to avatar image file if exists in Brain."""
    profile = load_profile(brain_path)
    if not profile.avatar or not profile.avatar.relative_path:
        return None
    base = Path(brain_path) if brain_path else resolve_brain_path(allow_dev_fallback=True)
    # Ensure no path traversal
    rel = Path(profile.avatar.relative_path)
    if ".." in rel.parts or rel.is_absolute():
        return None
    candidate = (base / rel).resolve()
    # Confirm it resides inside Brain
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    if candidate.exists():
        return candidate
    return None
