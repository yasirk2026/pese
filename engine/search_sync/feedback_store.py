"""
PESE Search Sync: Persistent Local Feedback Store
Phase N3-A: SQLite-Backed Thread-Safe Feedback Storage

Stores user preference evidence (LIKE / DISLIKE) locally and provides sub-millisecond
indexed lookup for active query preferences during MAAE candidate ranking.
"""

from ..brain.coordination import canonical_write

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone

from .contracts import (
    FeedbackType,
    TargetType,
    FeedbackEvent,
    NeuralShadowObservation,
    classify_diagnostic_alignment,
)
from ..config import RUNTIME_ROOT


DEFAULT_DB_PATH = RUNTIME_ROOT / "search_sync_feedback.db"


class SearchSyncFeedbackStore:
    """
    Local-first, thread-safe SQLite store for Search Sync user feedback.
    Maintains an active state table (1 record per query-target pair) and an
    append-only audit log for future offline ranking analysis.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns SQLite connection with row factory configured."""
        if str(self.db_path) == ":memory:":
            if not hasattr(self, "_mem_conn") or self._mem_conn is None:
                self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._mem_conn.row_factory = sqlite3.Row
            return self._mem_conn

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @canonical_write
    def _init_db(self):
        """Initializes database schema with required tables and indexes."""
        with self._lock:
            conn = self._get_connection()
            from ..brain.feedback_schema import initialize_feedback_schema
            initialize_feedback_schema(conn)

            conn.commit()
            if str(self.db_path) != ":memory:":
                conn.close()

    @canonical_write
    def record_feedback(self, event: FeedbackEvent) -> FeedbackEvent:
        """
        Records a feedback event.
        - Updates active_preferences atomically (idempotent; replaces prior vote if toggled).
        - Appends to feedback_audit_events for future training dataset generation.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            meta_json = json.dumps({**event.metadata, "model_versions": event.model_versions})

            # 1. Upsert active preference
            cursor.execute("""
                INSERT INTO active_preferences (
                    normalized_query, target_type, target_id, target_slug,
                    feedback, reason, original_query, search_context_id,
                    rank_position, maae_base_score, updated_at, last_event_id, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(normalized_query, target_type, target_id) DO UPDATE SET
                    feedback = excluded.feedback,
                    reason = COALESCE(excluded.reason, active_preferences.reason),
                    target_slug = COALESCE(excluded.target_slug, active_preferences.target_slug),
                    rank_position = COALESCE(excluded.rank_position, active_preferences.rank_position),
                    search_context_id = excluded.search_context_id,
                    maae_base_score = COALESCE(excluded.maae_base_score, active_preferences.maae_base_score),
                    updated_at = excluded.updated_at,
                    last_event_id = excluded.last_event_id,
                    metadata_json = excluded.metadata_json
            """, (
                event.normalized_query,
                event.target_type.value,
                event.target_id,
                event.target_slug,
                event.feedback.value,
                event.reason,
                event.query,
                event.search_context_id,
                event.rank_position,
                event.maae_base_score,
                now_iso,
                event.event_id,
                meta_json
            ))

            # 2. Append to audit log
            cursor.execute("""
                INSERT INTO feedback_audit_events (
                    event_id, normalized_query, original_query, target_type, target_id,
                    target_slug, feedback, reason, rank_position, search_context_id,
                    maae_base_score, search_sync_adjustment, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id,
                event.normalized_query,
                event.query,
                event.target_type.value,
                event.target_id,
                event.target_slug,
                event.feedback.value,
                event.reason,
                event.rank_position,
                event.search_context_id,
                event.maae_base_score,
                event.search_sync_adjustment,
                event.created_at,
                meta_json
            ))

            conn.commit()
            if str(self.db_path) != ":memory:":
                conn.close()

            return event

    def get_active_preferences_for_query(
        self,
        normalized_query: str,
        target_type: Optional[TargetType] = None,
    ) -> Dict[str, FeedbackEvent]:
        """
        Retrieves all active feedback records for a given normalized query.
        Optionally filters by target_type (e.g. TargetType.SERP_RESULT).
        Returns a dictionary mapping target_id -> FeedbackEvent.
        Ultra-fast single indexed query (< 0.2 ms).
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            if target_type is not None:
                type_val = target_type.value if hasattr(target_type, "value") else str(target_type)
                cursor.execute("""
                    SELECT * FROM active_preferences
                    WHERE normalized_query = ? AND target_type = ?
                """, (normalized_query, type_val))
            else:
                cursor.execute("""
                    SELECT * FROM active_preferences
                    WHERE normalized_query = ?
                """, (normalized_query,))
            rows = cursor.fetchall()
            results = {}

            for row in rows:
                meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                event = FeedbackEvent(
                    event_id=row["last_event_id"],
                    query=row["original_query"],
                    normalized_query=row["normalized_query"],
                    target_type=TargetType(row["target_type"]),
                    target_id=row["target_id"],
                    target_slug=row["target_slug"],
                    rank_position=row["rank_position"],
                    feedback=FeedbackType(row["feedback"]),
                    reason=row["reason"],
                    created_at=row["updated_at"],
                    search_context_id=row["search_context_id"],
                    maae_base_score=row["maae_base_score"],
                    model_versions=meta.get("model_versions", {}),
                    metadata=meta,
                )
                results[row["target_id"]] = event
                # Also index by slug if target_slug is present
                if row["target_slug"] and row["target_slug"] != row["target_id"]:
                    results[row["target_slug"]] = event

            if str(self.db_path) != ":memory:":
                conn.close()

            return results

    def get_featured_answer_preference(
        self,
        normalized_query: str,
        target_id: Optional[str] = None
    ) -> Optional[FeedbackEvent]:
        """
        Checks if there is an active feedback state for a Featured Answer on this query.
        If target_id is provided, checks for that target_id specifically.
        If target_id is None, checks if ANY featured answer was disliked for this query.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            if target_id:
                cursor.execute("""
                    SELECT * FROM active_preferences
                    WHERE normalized_query = ? AND target_type = ? AND target_id = ?
                """, (normalized_query, TargetType.FEATURED_ANSWER.value, target_id))
            else:
                cursor.execute("""
                    SELECT * FROM active_preferences
                    WHERE normalized_query = ? AND target_type = ?
                    LIMIT 1
                """, (normalized_query, TargetType.FEATURED_ANSWER.value))

            row = cursor.fetchone()
            if not row:
                if str(self.db_path) != ":memory:":
                    conn.close()
                return None

            meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
            event = FeedbackEvent(
                event_id=row["last_event_id"],
                query=row["original_query"],
                normalized_query=row["normalized_query"],
                target_type=TargetType(row["target_type"]),
                target_id=row["target_id"],
                target_slug=row["target_slug"],
                rank_position=row["rank_position"],
                feedback=FeedbackType(row["feedback"]),
                reason=row["reason"],
                created_at=row["updated_at"],
                search_context_id=row["search_context_id"],
                maae_base_score=row["maae_base_score"],
                model_versions=meta.get("model_versions", {}),
                metadata=meta,
            )
            if str(self.db_path) != ":memory:":
                conn.close()
            return event

    def list_all_active_preferences(self) -> List[FeedbackEvent]:
        """Returns all active preferences across all queries (for debugging / admin)."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM active_preferences ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            events = []
            for row in rows:
                meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                events.append(FeedbackEvent(
                    event_id=row["last_event_id"],
                    query=row["original_query"],
                    normalized_query=row["normalized_query"],
                    target_type=TargetType(row["target_type"]),
                    target_id=row["target_id"],
                    target_slug=row["target_slug"],
                    rank_position=row["rank_position"],
                    feedback=FeedbackType(row["feedback"]),
                    reason=row["reason"],
                    created_at=row["updated_at"],
                    search_context_id=row["search_context_id"],
                    maae_base_score=row["maae_base_score"],
                    model_versions=meta.get("model_versions", {}),
                    metadata=meta,
                ))
            if str(self.db_path) != ":memory:":
                conn.close()
            return events

    # ==================== PHASE N3-B: NEURAL SHADOW OBSERVATIONS ====================

    @canonical_write
    def record_neural_observations(self, observations: List[NeuralShadowObservation]) -> None:
        """
        Persists a batch of neural shadow observations.
        Fail-open guarantee: any database error is logged and swallowed so search never fails.
        """
        if not observations:
            return

        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()
                now_iso = datetime.now(timezone.utc).isoformat()
                records = []
                for obs in observations:
                    meta_json = json.dumps(obs.metadata)
                    records.append((
                        obs.observation_id,
                        obs.search_context_id,
                        obs.normalized_query,
                        obs.query,
                        obs.target_type,
                        obs.target_id,
                        obs.target_slug,
                        obs.evidence_id,
                        obs.evidence_summary,
                        obs.answers_probability,
                        obs.does_not_answer_probability,
                        obs.predicted_label,
                        obs.threshold_used,
                        obs.authority,
                        obs.model_id,
                        obs.checkpoint_hash,
                        obs.latency_ms,
                        obs.created_at or now_iso,
                        meta_json
                    ))

                cursor.executemany("""
                    INSERT OR REPLACE INTO neural_shadow_observations (
                        observation_id, search_context_id, normalized_query, original_query,
                        target_type, target_id, target_slug, evidence_id, evidence_summary,
                        answers_probability, does_not_answer_probability, predicted_label,
                        threshold_used, authority, model_id, checkpoint_hash, latency_ms,
                        created_at, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, records)

                conn.commit()
                if str(self.db_path) != ":memory:":
                    conn.close()
        except Exception as exc:
            logging.getLogger(__name__).warning("Failed to record neural shadow observations: %s", exc)

    def get_neural_observations(self, search_context_id: str) -> List[NeuralShadowObservation]:
        """Retrieves all neural observations for a given search_context_id."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM neural_shadow_observations
                WHERE search_context_id = ?
                ORDER BY created_at ASC
            """, (search_context_id,))
            rows = cursor.fetchall()
            results = []
            for row in rows:
                meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                results.append(NeuralShadowObservation(
                    observation_id=row["observation_id"],
                    search_context_id=row["search_context_id"],
                    model_id=row["model_id"],
                    checkpoint_hash=row["checkpoint_hash"],
                    query=row["original_query"],
                    normalized_query=row["normalized_query"],
                    target_type=row["target_type"],
                    target_id=row["target_id"],
                    target_slug=row["target_slug"],
                    evidence_id=row["evidence_id"],
                    evidence_summary=row["evidence_summary"] or "",
                    answers_probability=row["answers_probability"],
                    does_not_answer_probability=row["does_not_answer_probability"],
                    predicted_label=row["predicted_label"],
                    threshold_used=row["threshold_used"],
                    authority=row["authority"],
                    latency_ms=row["latency_ms"] or 0.0,
                    created_at=row["created_at"],
                    metadata=meta,
                ))
            if str(self.db_path) != ":memory:":
                conn.close()
            return results

    def get_neural_observations_for_query_target(
        self, normalized_query: str, target_id: str
    ) -> List[NeuralShadowObservation]:
        """Retrieves observations for a specific query and target."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM neural_shadow_observations
                WHERE normalized_query = ? AND target_id = ?
                ORDER BY created_at DESC
            """, (normalized_query, target_id))
            rows = cursor.fetchall()
            results = []
            for row in rows:
                meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                results.append(NeuralShadowObservation(
                    observation_id=row["observation_id"],
                    search_context_id=row["search_context_id"],
                    model_id=row["model_id"],
                    checkpoint_hash=row["checkpoint_hash"],
                    query=row["original_query"],
                    normalized_query=row["normalized_query"],
                    target_type=row["target_type"],
                    target_id=row["target_id"],
                    target_slug=row["target_slug"],
                    evidence_id=row["evidence_id"],
                    evidence_summary=row["evidence_summary"] or "",
                    answers_probability=row["answers_probability"],
                    does_not_answer_probability=row["does_not_answer_probability"],
                    predicted_label=row["predicted_label"],
                    threshold_used=row["threshold_used"],
                    authority=row["authority"],
                    latency_ms=row["latency_ms"] or 0.0,
                    created_at=row["created_at"],
                    metadata=meta,
                ))
            if str(self.db_path) != ":memory:":
                conn.close()
            return results

    def get_feedback_with_neural_observations(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Reconstructs joined records showing:
        - MAAE decision & human feedback (LIKE / DISLIKE)
        - PESE-Rel-0 neural observation
        - Diagnostic alignment classification
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Query active preferences or audit events
            if query:
                from .preference_signal import normalize_sync_query
                norm_q = normalize_sync_query(query)
                cursor.execute("""
                    SELECT a.*, o.evidence_id, o.evidence_summary, o.answers_probability,
                           o.does_not_answer_probability, o.predicted_label, o.threshold_used,
                           o.model_id, o.checkpoint_hash, o.authority, o.metadata_json AS observation_metadata
                    FROM active_preferences a
                    LEFT JOIN neural_shadow_observations o
                      ON a.search_context_id = o.search_context_id AND a.target_id = o.target_id
                         AND a.target_type = o.target_type AND a.normalized_query = o.normalized_query
                    WHERE a.normalized_query = ?
                    ORDER BY a.updated_at DESC
                """, (norm_q,))
            else:
                cursor.execute("""
                    SELECT a.*, o.evidence_id, o.evidence_summary, o.answers_probability,
                           o.does_not_answer_probability, o.predicted_label, o.threshold_used,
                           o.model_id, o.checkpoint_hash, o.authority, o.metadata_json AS observation_metadata
                    FROM active_preferences a
                    LEFT JOIN neural_shadow_observations o
                      ON a.search_context_id = o.search_context_id AND a.target_id = o.target_id
                         AND a.target_type = o.target_type AND a.normalized_query = o.normalized_query
                    ORDER BY a.updated_at DESC
                """)

            rows = cursor.fetchall()
            joined = []
            seen_keys = set()
            for r in rows:
                key = (r["normalized_query"], r["target_type"], r["target_id"], r["search_context_id"])
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                matches = [row for row in rows if
                           (row["normalized_query"], row["target_type"], row["target_id"], row["search_context_id"]) == key
                           and row["answers_probability"] is not None]
                feedback_meta = json.loads(r["metadata_json"] or "{}")
                receipt = feedback_meta.get("provenance")
                verified = feedback_meta.get("context_verified") is True and bool(receipt)
                if verified:
                    # Match a particular revision/passage/model receipt, never
                    # the highest score or first observation of that document.
                    precise = []
                    for row in matches:
                        observed = json.loads(row["observation_metadata"] or "{}")
                        if (row["evidence_id"] == receipt.get("evidence_id") and
                                all(observed.get(k) == receipt.get(k) for k in
                                    ("document_revision", "evidence_hash", "ranking_version", "generation", "model_versions"))):
                            precise.append(row)
                    matches = precise
                # Multiple passages/models are separate observations, not a vote.
                # Never choose an arbitrary first row as evidence for feedback.
                ambiguous = len(matches) > 1
                selected = matches[0] if len(matches) == 1 else None
                ans_prob = selected["answers_probability"] if selected is not None else None
                if selected is not None:
                    r = selected
                fb_type = FeedbackType(r["feedback"]) if r["feedback"] else None
                alignment = classify_diagnostic_alignment(ans_prob, fb_type, r["threshold_used"] or 0.85)

                joined.append({
                    "search_context_id": r["search_context_id"],
                    "query": r["original_query"],
                    "normalized_query": r["normalized_query"],
                    "target_type": r["target_type"],
                    "target_id": r["target_id"],
                    "target_slug": r["target_slug"],
                    "rank_position": r["rank_position"],
                    "maae_base_score": r["maae_base_score"],
                    "human_feedback": r["feedback"],
                    "reason": r["reason"],
                    "updated_at": r["updated_at"],
                    "neural_model": r["model_id"] or "PESE-Rel-0",
                    "checkpoint_hash": r["checkpoint_hash"] or "",
                    "evidence_id": r["evidence_id"] if selected is not None else None,
                    "evidence_summary": r["evidence_summary"] if selected is not None else None,
                    "answers_probability": ans_prob,
                    "provenance_status": "AMBIGUOUS" if ambiguous else "VERIFIED" if verified and selected is not None else "INCOMPLETE" if verified else "LEGACY_DIAGNOSTIC_ONLY",
                    "predicted_label": r["predicted_label"] if selected is not None else None,
                    "neural_authority": r["authority"] or "NONE",
                    "diagnostic_alignment": alignment or "NO_OBSERVATION" if ans_prob is None else alignment,
                })

            if str(self.db_path) != ":memory:":
                conn.close()
            return joined

    def get_neural_shadow_statistics(self) -> Dict[str, Any]:
        """
        Lightweight developer statistics on recorded neural shadow observations
        and human feedback alignment rates.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*), AVG(answers_probability) FROM neural_shadow_observations")
            obs_row = cursor.fetchone()
            total_obs = obs_row[0] if obs_row else 0
            mean_p_answers = round(obs_row[1] or 0.0, 4)

            cursor.execute("SELECT COUNT(*) FROM neural_shadow_observations WHERE answers_probability >= 0.85")
            high_answers = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM neural_shadow_observations WHERE answers_probability <= 0.15")
            high_does_not = cursor.fetchone()[0]

            if str(self.db_path) != ":memory:":
                conn.close()

            # Join with active feedback to calculate alignment
            feedback_joins = self.get_feedback_with_neural_observations()
            linked_count = sum(1 for item in feedback_joins if item["answers_probability"] is not None)
            agreements = sum(item["diagnostic_alignment"] in {"NEURAL HIGH / HUMAN LIKE", "NEURAL LOW / HUMAN DISLIKE"} for item in feedback_joins)
            disagreements = sum(item["diagnostic_alignment"] in {"NEURAL HIGH / HUMAN DISLIKE", "NEURAL LOW / HUMAN LIKE"} for item in feedback_joins)

            return {
                "total_observations": total_obs,
                "mean_p_answers": mean_p_answers,
                "high_confidence_answers_count": high_answers,
                "high_confidence_does_not_answer_count": high_does_not,
                "linked_feedback_count": linked_count,
                "neural_human_agreements": agreements,
                "neural_human_disagreements": disagreements,
                "model_authority": "NONE",
            }

    @canonical_write
    def clear_all(self):
        """Clears all stored preferences, audit events, and neural observations."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM active_preferences")
            cursor.execute("DELETE FROM feedback_audit_events")
            cursor.execute("DELETE FROM neural_shadow_observations")
            conn.commit()
            if str(self.db_path) != ":memory:":
                conn.close()


# Global default store instance for the engine
feedback_store = SearchSyncFeedbackStore()
