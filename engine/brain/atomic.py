"""
PESE Brain Storage: Atomic Filesystem Utilities
Ensures crash-safe writes for documents, settings, and manifests using
atomic temporary writes, forced disk flushes (fsync), and rename replacement.
"""

import os
import json
from pathlib import Path
from typing import Any, Union


def atomic_write_file(
    target_path: Union[str, Path],
    content: str,
    encoding: str = "utf-8"
) -> Path:
    """
    Writes text content to target_path atomically:
    1. Writes to temporary sibling file (.tmp.pid.timestamp)
    2. Flushes application buffers
    3. Issues OS-level fsync to ensure disk persistence
    4. Atomically replaces target file using os.replace
    """
    target = Path(target_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    # Use unique temporary filename in the same directory (required for atomic rename)
    temp_path = target.parent / f".{target.name}.tmp.{os.getpid()}"

    try:
        with open(temp_path, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, target)
        return target
    except Exception:
        # Cleanup temporary file if replace failed
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def atomic_write_json(
    target_path: Union[str, Path],
    data: Any,
    indent: int = 2
) -> Path:
    """
    Serializes data to formatted JSON and writes atomically.
    """
    json_str = json.dumps(data, indent=indent, ensure_ascii=False) + "\n"
    return atomic_write_file(target_path, json_str, encoding="utf-8")
