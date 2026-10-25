"""
PESE SQLite Safety: Transactionally consistent SQLite backup mechanism.

Guarantees:
  1. Opens source database in read-only URI mode (?mode=ro) to prevent writer starvation.
  2. Executes safe page-by-page SQLite Backup API (conn.backup()).
  3. Audits destination snapshot with PRAGMA quick_check and PRAGMA integrity_check.
  4. Never produces a torn, half-written, or locked database.
"""

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional

from .contracts import SyncError, CorruptSnapshotError


def safe_sqlite_backup(
    source_path: Path,
    dest_path: Path,
    timeout: float = 10.0
) -> None:
    """
    Produces a transactionally consistent copy of a live SQLite database.

    Uses the official SQLite Online Backup API (conn.backup), which handles
    concurrent transactions and WAL files safely without locking the application.
    """
    src = Path(source_path).resolve()
    dst = Path(dest_path).resolve()

    if not src.exists():
        raise FileNotFoundError(f"Source SQLite database does not exist: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise SyncError("SQLite backup requires a new detached destination; existing files are never replaced.")

    # Open source in read-only URI mode
    src_uri = f"{src.as_uri()}?mode=ro"

    try:
        with closing(sqlite3.connect(src_uri, uri=True, timeout=timeout)) as src_conn:
            # Check source integrity before backup
            check_cur = src_conn.cursor()
            src_check = check_cur.execute("PRAGMA quick_check").fetchone()
            if not src_check or src_check[0] != "ok":
                raise CorruptSnapshotError(f"Source SQLite database failed quick_check: {src_check}")

            # Open destination
            with closing(sqlite3.connect(str(dst), timeout=timeout)) as dst_conn:
                # Perform transactional online backup
                src_conn.backup(dst_conn, pages=100)
                dst_conn.commit()

        # Audit destination snapshot
        with closing(sqlite3.connect(str(dst), timeout=timeout)) as audit_conn:
            cur = audit_conn.cursor()
            qc = cur.execute("PRAGMA quick_check").fetchone()
            if not qc or qc[0] != "ok":
                raise CorruptSnapshotError(f"Snapshot SQLite database failed quick_check: {qc}")

            ic = cur.execute("PRAGMA integrity_check").fetchone()
            if not ic or ic[0] != "ok":
                raise CorruptSnapshotError(f"Snapshot SQLite database failed integrity_check: {ic}")

    except Exception as exc:
        if dst.exists():
            try:
                dst.unlink()
            except OSError:
                pass
        if isinstance(exc, (SyncError, FileNotFoundError)):
            raise
        raise SyncError(f"Failed to safely backup SQLite database '{src.name}': {exc}") from exc
