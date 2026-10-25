"""Version 1 portable Search Sync records. SQLite remains local runtime storage."""
import json
import math
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from ..brain.feedback_schema import initialize_feedback_schema
from .contracts import CorruptSnapshotError

LOGICAL_FILENAME = "search-sync-records.json"
TABLES = ("active_preferences", "feedback_audit_events", "neural_shadow_observations")


def _schema(connection):
    return {table: connection.execute(f"PRAGMA table_info({table})").fetchall() for table in TABLES}


def _expected_schema():
    with closing(sqlite3.connect(":memory:")) as connection:
        initialize_feedback_schema(connection)
        return _schema(connection)


def validate_records(payload):
    if not isinstance(payload, dict) or set(payload) != {"format", "version", "tables"}:
        raise CorruptSnapshotError("Invalid Search Sync logical envelope.")
    if payload["format"] != "pese-search-sync-records" or payload["version"] != 1:
        raise CorruptSnapshotError("Unsupported Search Sync logical version.")
    if not isinstance(payload["tables"], dict) or set(payload["tables"]) != set(TABLES):
        raise CorruptSnapshotError("Incomplete Search Sync tables.")
    schema = _expected_schema()
    for table in TABLES:
        rows = payload["tables"][table]
        if not isinstance(rows, list):
            raise CorruptSnapshotError("Logical records must be arrays.")
        keys = set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {c[1] for c in schema[table]}:
                raise CorruptSnapshotError(f"Incompatible columns in {table}.")
            for _, name, kind, required, default, pk in schema[table]:
                value = row[name]
                if value is None:
                    if required or pk:
                        raise CorruptSnapshotError(f"Missing required logical field: {name}.")
                    continue
                if kind == "TEXT" and not isinstance(value, str):
                    raise CorruptSnapshotError(f"Invalid text field: {name}.")
                if kind in ("REAL", "INTEGER") and (type(value) not in (int, float) or not math.isfinite(value)):
                    raise CorruptSnapshotError(f"Invalid numeric field: {name}.")
                if kind == "INTEGER" and type(value) is not int:
                    raise CorruptSnapshotError(f"Invalid integer field: {name}.")
                if name in ("updated_at", "created_at"):
                    try:
                        if datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
                            raise ValueError()
                    except (ValueError, TypeError):
                        raise CorruptSnapshotError("Logical timestamps require ISO-8601 timezone information.")
                if name == "metadata_json":
                    try:
                        if not isinstance(json.loads(value), dict):
                            raise ValueError()
                    except (ValueError, TypeError):
                        raise CorruptSnapshotError("Invalid logical metadata.")
            key = tuple(row[c[1]] for c in sorted(schema[table], key=lambda c: c[5]) if c[5])
            if key in keys:
                raise CorruptSnapshotError(f"Duplicate logical record in {table}.")
            keys.add(key)
            if not row.get("normalized_query") or not row.get("target_id"):
                raise CorruptSnapshotError("Logical records require stable query and target identities.")
            if row.get("target_type") not in ("SERP_RESULT", "FEATURED_ANSWER"):
                raise CorruptSnapshotError("Unsupported feedback target type.")
            if "feedback" in row and row["feedback"] not in ("LIKE", "DISLIKE"):
                raise CorruptSnapshotError("Unsupported feedback value.")
            if "authority" in row and row["authority"] != "NONE":
                raise CorruptSnapshotError("Neural observations must have no ranking authority.")
            for probability in ("answers_probability", "does_not_answer_probability", "threshold_used"):
                if probability in row and not 0 <= row[probability] <= 1:
                    raise CorruptSnapshotError("Invalid neural observation probability.")
    audit_ids = {r["event_id"] for r in payload["tables"]["feedback_audit_events"]}
    if any(r["last_event_id"] not in audit_ids for r in payload["tables"]["active_preferences"]):
        raise CorruptSnapshotError("Active preference refers to a missing audit event.")
    return payload


def export_records(source):
    source = Path(source).resolve()
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=10)) as connection:
        connection.execute("BEGIN")
        if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise CorruptSnapshotError("Search Sync database integrity failure.")
        if _schema(connection) != _expected_schema():
            raise CorruptSnapshotError("Incompatible Search Sync database schema.")
        tables_present = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables_present != set(TABLES):
            raise CorruptSnapshotError("Unrecognized Search Sync tables require an explicit portable schema.")
        tables = {}
        for table in TABLES:
            columns = [c[1] for c in _schema(connection)[table]]
            rows = [dict(zip(columns, row)) for row in connection.execute(f"SELECT * FROM {table}")]
            tables[table] = sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False))
    return validate_records({"format": "pese-search-sync-records", "version": 1, "tables": tables})


def import_records(payload, destination):
    """Create a new, detached database. Never replace or merge a live database."""
    validate_records(payload)
    destination = Path(destination)
    if destination.exists():
        raise CorruptSnapshotError("Logical import requires a new database.")
    destination.touch(exist_ok=False)
    try:
        with closing(sqlite3.connect(destination)) as connection:
            initialize_feedback_schema(connection)
            for table in TABLES:
                columns = [c[1] for c in _expected_schema()[table]]
                sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"
                connection.executemany(sql, ([row[c] for c in columns] for row in payload["tables"][table]))
            connection.commit()
            if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise CorruptSnapshotError("Imported Search Sync database integrity failure.")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
