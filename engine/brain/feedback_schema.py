"""Canonical Search Sync SQLite DDL shared by Brain creation and runtime.

Extracted verbatim from the existing runtime; no preference mathematics changes.
"""


def initialize_feedback_schema(connection):
    cursor = connection.cursor()
    cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_preferences (
                    normalized_query TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    target_slug TEXT,
                    feedback TEXT NOT NULL,
                    reason TEXT,
                    original_query TEXT NOT NULL,
                    search_context_id TEXT,
                    rank_position INTEGER,
                    maae_base_score REAL,
                    updated_at TEXT NOT NULL,
                    last_event_id TEXT NOT NULL,
                    metadata_json TEXT,
                    PRIMARY KEY (normalized_query, target_type, target_id)
                )
            """)
    cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_active_query
                ON active_preferences (normalized_query)
            """)
    cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback_audit_events (
                    event_id TEXT PRIMARY KEY,
                    normalized_query TEXT NOT NULL,
                    original_query TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    target_slug TEXT,
                    feedback TEXT NOT NULL,
                    reason TEXT,
                    rank_position INTEGER,
                    search_context_id TEXT,
                    maae_base_score REAL,
                    search_sync_adjustment REAL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT
                )
            """)
    cursor.execute("""
                CREATE TABLE IF NOT EXISTS neural_shadow_observations (
                    observation_id TEXT PRIMARY KEY,
                    search_context_id TEXT NOT NULL,
                    normalized_query TEXT NOT NULL,
                    original_query TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    target_slug TEXT,
                    evidence_id TEXT NOT NULL,
                    evidence_summary TEXT,
                    answers_probability REAL NOT NULL,
                    does_not_answer_probability REAL NOT NULL,
                    predicted_label TEXT NOT NULL,
                    threshold_used REAL NOT NULL,
                    authority TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    checkpoint_hash TEXT NOT NULL,
                    latency_ms REAL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT
                )
            """)
    cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_shadow_context_target
                ON neural_shadow_observations (search_context_id, target_id)
            """)
    cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_shadow_query_target
                ON neural_shadow_observations (normalized_query, target_id)
            """)
