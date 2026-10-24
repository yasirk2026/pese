"""
PESE Unit & Integration Tests: Brain Storage Contract & Path Independence (Phase D0-C)
Covers Brain identity, initialization, opening, validation, path resolution,
missing-drive safety, path matrix, atomic persistence, and cache separation.
"""

import os
import json
import shutil
import tempfile
from pathlib import Path
import pytest

from engine.brain.contracts import (
    BRAIN_FORMAT_IDENTIFIER,
    CURRENT_SCHEMA_VERSION,
    BRAIN_MANIFEST_FILENAME,
    BrainIdentity,
    BrainStatus,
    BrainMissingError,
    BrainNotConfiguredError,
    BrainInvalidError,
    BrainConflictError,
    BrainSecurityError,
)
from engine.brain.lifecycle import (
    initialize_brain,
    open_brain,
    verify_brain_integrity,
    DEFAULT_DOCUMENTS_FILENAME,
    DEFAULT_FEEDBACK_DB_FILENAME,
    DEFAULT_SETTINGS_FILENAME,
    DEFAULT_EVENTS_FILENAME,
    DEFAULT_SEMANTIC_INDEX_DIRNAME,
    DEFAULT_PERSONALIZATION_DIRNAME,
)
from engine.brain.resolver import (
    resolve_brain_path,
    save_desktop_brain_pointer,
    load_desktop_brain_pointer,
    clear_desktop_brain_pointer,
)
from engine.brain.atomic import atomic_write_json, atomic_write_file


def test_brain_identity_schema():
    """Verify BrainIdentity format, schemaVersion, UUID, and ISO-8601 contracts."""
    identity = BrainIdentity.create_new(name="Test Brain")
    assert identity.format == BRAIN_FORMAT_IDENTIFIER
    assert identity.schema_version == CURRENT_SCHEMA_VERSION
    assert len(identity.brain_id) >= 32
    assert identity.created_at.endswith("Z")
    assert identity.name == "Test Brain"

    serialized = identity.to_dict()
    assert serialized["format"] == "pese-brain"
    assert serialized["schemaVersion"] == 1
    assert serialized["brainId"] == identity.brain_id
    assert serialized["createdAt"] == identity.created_at
    # Invariant: Zero absolute paths in identity manifest
    assert "path" not in serialized
    assert "D:" not in json.dumps(serialized)
    assert "C:" not in json.dumps(serialized)


def test_initialize_new_brain(tmp_path):
    """Verify initializing a new Brain creates required files, databases, and subdirectories."""
    brain_dir = tmp_path / "NewBrain"
    identity = initialize_brain(brain_dir, name="Genesis Brain")

    assert (brain_dir / BRAIN_MANIFEST_FILENAME).exists()
    assert (brain_dir / DEFAULT_DOCUMENTS_FILENAME).exists()
    assert (brain_dir / DEFAULT_FEEDBACK_DB_FILENAME).exists()
    assert (brain_dir / DEFAULT_SETTINGS_FILENAME).exists()
    assert (brain_dir / DEFAULT_EVENTS_FILENAME).exists()
    assert (brain_dir / DEFAULT_SEMANTIC_INDEX_DIRNAME).is_dir()
    assert (brain_dir / DEFAULT_PERSONALIZATION_DIRNAME).is_dir()

    info = open_brain(brain_dir)
    assert info.brain_id == identity.brain_id
    assert info.status == BrainStatus.ACTIVE
    assert info.schema_version == 1
    assert info.has_feedback_db is True
    assert info.has_privacy_settings is True
    assert info.has_history_log is True


def test_initialize_brain_conflict_never_overwrites(tmp_path):
    """Invariant: Attempting to initialize over an existing Brain must NEVER overwrite it."""
    brain_dir = tmp_path / "ExistingBrain"
    identity1 = initialize_brain(brain_dir, name="Original Brain")

    # Second initialization must raise BrainConflictError
    with pytest.raises(BrainConflictError):
        initialize_brain(brain_dir, name="Overwriting Brain")

    # Verify original Brain identity was untouched
    info = open_brain(brain_dir)
    assert info.brain_id == identity1.brain_id
    assert info.name == "Original Brain"


def test_initialize_brain_security_rejects_runtime_dir():
    """Invariant: Brain cannot be placed inside application or python runtime directory."""
    engine_dir = Path(__file__).resolve().parent.parent
    with pytest.raises(BrainSecurityError):
        initialize_brain(engine_dir / "unsafe_brain")


def test_open_missing_brain_raises(tmp_path):
    """Invariant: Opening a nonexistent directory raises BrainMissingError."""
    missing_dir = tmp_path / "NonexistentFolder" / "Deep"
    with pytest.raises(BrainMissingError) as exc_info:
        open_brain(missing_dir)
    assert "does not exist" in str(exc_info.value)


def test_open_corrupted_or_invalid_brain(tmp_path):
    """Invariant: Invalid or corrupted Brain structures must raise clear errors, never silently repair."""
    invalid_dir = tmp_path / "InvalidBrain"
    invalid_dir.mkdir()

    # 1. Missing pese-brain.json
    with pytest.raises(BrainInvalidError) as exc_info:
        open_brain(invalid_dir)
    assert "Missing required identity manifest" in str(exc_info.value)

    # 2. Corrupt JSON
    manifest = invalid_dir / BRAIN_MANIFEST_FILENAME
    manifest.write_text("{ this is not valid json : [", encoding="utf-8")
    with pytest.raises(BrainInvalidError) as exc_info:
        open_brain(invalid_dir)
    assert "Corrupted or unreadable" in str(exc_info.value)

    # 3. Wrong format identifier
    manifest.write_text(json.dumps({"format": "other-app", "schemaVersion": 1, "brainId": "123"}), encoding="utf-8")
    with pytest.raises(BrainInvalidError) as exc_info:
        open_brain(invalid_dir)
    assert "Unsupported format" in str(exc_info.value)

    # 4. Unsupported schema version
    manifest.write_text(json.dumps({"format": "pese-brain", "schemaVersion": 999, "brainId": "123"}), encoding="utf-8")
    with pytest.raises(BrainInvalidError) as exc_info:
        open_brain(invalid_dir)
    assert "Unsupported schemaVersion" in str(exc_info.value)


def test_missing_drive_safety(tmp_path):
    """
    CRITICAL: If a configured Brain path disappears (e.g. D: drive disconnected),
    PESE must raise BrainMissingError and NEVER silently create a replacement Brain
    or fall back to another location.
    """
    settings_file = tmp_path / "settings.json"
    unmounted_drive_path = Path("Z:\\PESE_Disconnected_SSD_Brain")

    # Persist pointer to unmounted drive
    save_desktop_brain_pointer(unmounted_drive_path, settings_file=settings_file)

    # Resolution must raise BrainMissingError
    with pytest.raises(BrainMissingError) as exc_info:
        resolve_brain_path(custom_settings_file=settings_file, allow_dev_fallback=True)

    assert "Z:\\PESE_Disconnected_SSD_Brain" in str(exc_info.value)
    assert "unmounted or disconnected" in str(exc_info.value)


def test_desktop_settings_pointer_and_windows_reset_simulation(tmp_path):
    """
    Simulate user story:
    1. Initialize Brain on custom path.
    2. Pointer written to desktop-settings.json.
    3. Simulate Windows reset by wiping desktop-settings.json.
    4. Verify Brain data is completely intact.
    5. Reconnect to existing Brain path.
    """
    custom_brain_dir = tmp_path / "MySpecialDataDrive" / "PESE Brain"
    settings_file = tmp_path / "LocalProfile" / "desktop-settings.json"

    # Step 1 & 2: Initialize and save pointer
    identity = initialize_brain(custom_brain_dir, name="Surviving Brain")
    save_desktop_brain_pointer(custom_brain_dir, settings_file=settings_file)

    loaded_pointer = load_desktop_brain_pointer(settings_file=settings_file)
    assert loaded_pointer == custom_brain_dir.resolve()

    # Step 3: Simulate Windows reset (delete pointer)
    clear_desktop_brain_pointer(settings_file=settings_file)
    assert settings_file.exists() is False
    assert load_desktop_brain_pointer(settings_file=settings_file) is None

    # Step 4: Brain survived
    assert custom_brain_dir.exists()
    assert (custom_brain_dir / BRAIN_MANIFEST_FILENAME).exists()

    # Step 5: Reconnect to surviving Brain
    reconnected_info = open_brain(custom_brain_dir)
    assert reconnected_info.brain_id == identity.brain_id
    assert reconnected_info.name == "Surviving Brain"

    # Re-save pointer
    save_desktop_brain_pointer(custom_brain_dir, settings_file=settings_file)
    assert load_desktop_brain_pointer(settings_file=settings_file) == custom_brain_dir.resolve()


def test_brain_identity_portability_move(tmp_path):
    """
    Invariant: A Brain folder can be moved to an entirely different path.
    Its brainId and identity remain intact because the Brain does not store its own path.
    """
    brain_a = tmp_path / "BrainLocationA"
    brain_b = tmp_path / "BrainLocationB"

    identity = initialize_brain(brain_a, name="Movable Brain")
    assert open_brain(brain_a).brain_id == identity.brain_id

    # Move directory
    shutil.move(str(brain_a), str(brain_b))

    # Old path missing, new path opens cleanly with exact same brainId
    with pytest.raises(BrainMissingError):
        open_brain(brain_a)

    info_b = open_brain(brain_b)
    assert info_b.brain_id == identity.brain_id
    assert info_b.name == "Movable Brain"


def test_cache_separation_and_rebuild(tmp_path):
    """
    Invariant: Derived semantic/vector caches can be deleted without deleting
    canonical documents, Search Sync feedback, or privacy settings.
    """
    brain_dir = tmp_path / "CacheTestBrain"
    initialize_brain(brain_dir)

    # Populate dummy document
    docs_path = brain_dir / DEFAULT_DOCUMENTS_FILENAME
    docs_path.write_text(json.dumps({"doc-1": {"title": "Important Document", "slug": "doc-1"}}), encoding="utf-8")

    # Populate derived cache
    cache_dir = brain_dir / DEFAULT_SEMANTIC_INDEX_DIRNAME
    cache_file = cache_dir / "cache_store.npz"
    cache_file.write_bytes(b"dummy binary cache content")

    assert cache_file.exists()
    assert docs_path.exists()

    # Delete the derived cache
    shutil.rmtree(cache_dir)
    cache_dir.mkdir()

    # Documents and settings are completely preserved
    assert docs_path.exists()
    info = open_brain(brain_dir)
    assert info.document_count == 1
    assert (brain_dir / DEFAULT_SETTINGS_FILENAME).exists()
    assert (brain_dir / DEFAULT_FEEDBACK_DB_FILENAME).exists()


def test_path_matrix_normal_spaces_deep_unicode(tmp_path):
    """
    Path matrix verification:
    1. Normal path
    2. Path with spaces
    3. Deeply nested path
    4. Unicode path
    """
    paths = [
        tmp_path / "StandardPath" / "Brain",
        tmp_path / "Folder With Spaces" / "My PESE Brain",
        tmp_path / "Deep" / "Nested" / "Directory" / "Level4" / "Level5" / "PESE_Brain",
        tmp_path / "Unicode_測試_🧠" / "PESE_Brain",
    ]

    for p in paths:
        identity = initialize_brain(p, name=f"Brain at {p.name}")
        info = open_brain(p)
        assert info.brain_id == identity.brain_id
        assert info.status == BrainStatus.ACTIVE
        integrity = verify_brain_integrity(p)
        assert integrity["manifest_ok"] is True
        assert integrity["documents_ok"] is True
        assert integrity["feedback_db_ok"] is True


def test_atomic_write_safety(tmp_path):
    """Verify atomic_write_json replaces safely and flushes."""
    target_file = tmp_path / "atomic_test.json"
    atomic_write_json(target_file, {"key": "initial_value"})

    with open(target_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["key"] == "initial_value"

    # Atomic update
    atomic_write_json(target_file, {"key": "updated_value"})
    with open(target_file, "r", encoding="utf-8") as f:
        data2 = json.load(f)
    assert data2["key"] == "updated_value"
