"""
PESE Brain Subsystem: User-Owned Portable Brain Storage Contract
"""

from .contracts import (
    BRAIN_FORMAT_IDENTIFIER,
    CURRENT_SCHEMA_VERSION,
    BRAIN_MANIFEST_FILENAME,
    BrainStatus,
    BrainIdentity,
    BrainInfo,
    BrainError,
    BrainMissingError,
    BrainNotConfiguredError,
    BrainInvalidError,
    BrainConflictError,
    BrainPermissionError,
    BrainSecurityError,
)

from .atomic import (
    atomic_write_file,
    atomic_write_json,
)

from .resolver import (
    DESKTOP_VENDOR_NAME,
    DESKTOP_APP_NAME,
    DESKTOP_SETTINGS_FILENAME,
    get_default_local_appdata_dir,
    get_desktop_settings_path,
    load_desktop_brain_pointer,
    save_desktop_brain_pointer,
    clear_desktop_brain_pointer,
    resolve_brain_path,
)

from .lifecycle import (
    DEFAULT_DOCUMENTS_FILENAME,
    DEFAULT_FEEDBACK_DB_FILENAME,
    DEFAULT_SETTINGS_FILENAME,
    DEFAULT_EVENTS_FILENAME,
    DEFAULT_SEMANTIC_INDEX_DIRNAME,
    DEFAULT_PERSONALIZATION_DIRNAME,
    initialize_brain,
    open_brain,
    verify_brain_integrity,
)

__all__ = [
    "BRAIN_FORMAT_IDENTIFIER",
    "CURRENT_SCHEMA_VERSION",
    "BRAIN_MANIFEST_FILENAME",
    "BrainStatus",
    "BrainIdentity",
    "BrainInfo",
    "BrainError",
    "BrainMissingError",
    "BrainNotConfiguredError",
    "BrainInvalidError",
    "BrainConflictError",
    "BrainPermissionError",
    "BrainSecurityError",
    "atomic_write_file",
    "atomic_write_json",
    "DESKTOP_VENDOR_NAME",
    "DESKTOP_APP_NAME",
    "DESKTOP_SETTINGS_FILENAME",
    "get_default_local_appdata_dir",
    "get_desktop_settings_path",
    "load_desktop_brain_pointer",
    "save_desktop_brain_pointer",
    "clear_desktop_brain_pointer",
    "resolve_brain_path",
    "DEFAULT_DOCUMENTS_FILENAME",
    "DEFAULT_FEEDBACK_DB_FILENAME",
    "DEFAULT_SETTINGS_FILENAME",
    "DEFAULT_EVENTS_FILENAME",
    "DEFAULT_SEMANTIC_INDEX_DIRNAME",
    "DEFAULT_PERSONALIZATION_DIRNAME",
    "initialize_brain",
    "open_brain",
    "verify_brain_integrity",
]
