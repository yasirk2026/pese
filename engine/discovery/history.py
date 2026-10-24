"""
PESE Discovery: Search History Store Abstraction
Provides a privacy-respecting persistent history layer.
Decoupled through an abstract base class to support Local JSON/JSONL
and future Firebase/Firestore private cloud backends.
"""

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from .models import QuerySessionEvent
from ..config import RUNTIME_ROOT, DEMO

DATA_DIR = RUNTIME_ROOT
DEFAULT_EVENTS_PATH = DATA_DIR / "behavioural_events.jsonl"
DEFAULT_SETTINGS_PATH = DATA_DIR / "privacy_settings.json"


class SearchHistoryStore(ABC):
    """Abstract interface for PESE search history and session observation persistence."""

    @abstractmethod
    def record_event(self, event: QuerySessionEvent) -> None:
        """Persist a single query session interaction event."""
        pass

    @abstractmethod
    def get_recent_searches(self, limit: int = 10, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve recent query submissions in reverse chronological order."""
        pass

    @abstractmethod
    def get_query_frequencies(self) -> Dict[str, int]:
        """Return normalized query frequencies across history."""
        pass

    @abstractmethod
    def get_query_clicks(self) -> Dict[str, Dict[str, int]]:
        """Return mapping of query -> target_slug -> click_count."""
        pass

    @abstractmethod
    def get_reformulation_chains(self) -> List[Tuple[str, str, int]]:
        """Return observed query reformulation pairs (query_a -> query_b, count)."""
        pass

    @abstractmethod
    def clear_history(self) -> None:
        """Erase all recorded behavioural search history."""
        pass

    @abstractmethod
    def is_history_enabled(self) -> bool:
        """Check whether behavioural history collection is active."""
        pass

    @abstractmethod
    def set_history_enabled(self, enabled: bool) -> None:
        """Toggle behavioural history collection on or off."""
        pass


class LocalHistoryStore(SearchHistoryStore):
    """
    Local JSONL implementation of SearchHistoryStore.
    Reads and appends events locally on disk without external network dependencies.
    """

    def __init__(
        self,
        events_path: Optional[Path] = None,
        settings_path: Optional[Path] = None,
    ):
        self.events_path = events_path or DEFAULT_EVENTS_PATH
        self.settings_path = settings_path or DEFAULT_SETTINGS_PATH
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_settings_file()

    def _ensure_settings_file(self) -> None:
        if not self.settings_path.exists():
            default_settings = {
                "history_enabled": not DEMO,
                "storage_mode": "local",
                "version": "1.0",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            try:
                with open(self.settings_path, "w", encoding="utf-8") as f:
                    json.dump(default_settings, f, indent=2)
            except Exception:
                pass

    def is_history_enabled(self) -> bool:
        if not self.settings_path.exists():
            return True
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return bool(data.get("history_enabled", True))
        except Exception:
            return True

    def set_history_enabled(self, enabled: bool) -> None:
        settings = {
            "history_enabled": enabled,
            "storage_mode": "local",
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except Exception:
            pass

    def record_event(self, event: QuerySessionEvent) -> None:
        if not self.is_history_enabled():
            return

        if not event.timestamp:
            event.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        line = json.dumps(event.model_dump()) + "\n"
        try:
            with open(self.events_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def _read_all_events(self) -> List[Dict[str, Any]]:
        if not self.events_path.exists():
            return []
        events = []
        try:
            with open(self.events_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except Exception:
                            continue
        except Exception:
            return []
        return events

    def get_recent_searches(self, limit: int = 10, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        events = self._read_all_events()
        # Find query_submitted events
        submitted = []
        seen_queries = set()
        for ev in reversed(events):
            if ev.get("event_type") == "query_submitted":
                q = (ev.get("query") or "").strip()
                if q and q.lower() not in seen_queries:
                    if session_id and ev.get("session_id") != session_id:
                        continue
                    seen_queries.add(q.lower())
                    submitted.append({
                        "query": q,
                        "session_id": ev.get("session_id"),
                        "timestamp": ev.get("timestamp"),
                    })
                    if len(submitted) >= limit:
                        break
        return submitted

    def get_query_frequencies(self) -> Dict[str, int]:
        freqs: Dict[str, int] = {}
        for ev in self._read_all_events():
            if ev.get("event_type") == "query_submitted":
                q = (ev.get("query") or "").strip().lower()
                if q:
                    freqs[q] = freqs.get(q, 0) + 1
        return freqs

    def get_query_clicks(self) -> Dict[str, Dict[str, int]]:
        clicks: Dict[str, Dict[str, int]] = {}
        for ev in self._read_all_events():
            if ev.get("event_type") == "result_clicked":
                q = (ev.get("query") or "").strip().lower()
                target = ev.get("target_slug")
                if q and target:
                    if q not in clicks:
                        clicks[q] = {}
                    clicks[q][target] = clicks[q].get(target, 0) + 1
        return clicks

    def get_reformulation_chains(self) -> List[Tuple[str, str, int]]:
        events = self._read_all_events()
        # Group submissions by session
        session_queries: Dict[str, List[str]] = {}
        for ev in events:
            if ev.get("event_type") == "query_submitted":
                sid = ev.get("session_id") or "anonymous"
                q = (ev.get("query") or "").strip().lower()
                if q:
                    session_queries.setdefault(sid, []).append(q)

        pair_counts: Dict[Tuple[str, str], int] = {}
        for sid, q_list in session_queries.items():
            for i in range(len(q_list) - 1):
                prev_q = q_list[i]
                next_q = q_list[i + 1]
                if prev_q != next_q:
                    pair_counts[(prev_q, next_q)] = pair_counts.get((prev_q, next_q), 0) + 1

        return [(pair[0], pair[1], count) for pair, count in pair_counts.items()]

    def clear_history(self) -> None:
        try:
            if self.events_path.exists():
                with open(self.events_path, "w", encoding="utf-8") as f:
                    f.truncate(0)
        except Exception:
            pass
