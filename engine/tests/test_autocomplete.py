"""
Unit tests for PESE Autocomplete Engine.
Verifies prefix matching, typo recovery, explainable scoring,
highlight spans, and deduplication.
"""

import pytest
from engine.indexing.store import DocumentStore
from engine.query_analysis.spelling import CorpusSpellingCorrector
from engine.discovery.autocomplete import AutocompleteEngine
from engine.discovery.history import LocalHistoryStore
from engine.discovery.sessions import SessionManager
from engine.discovery.families import QueryFamilyRegistry


@pytest.fixture
def autocomplete_fixture(tmp_path, public_discovery_store):
    store = public_discovery_store
    corrector = CorpusSpellingCorrector()
    corrector.build_vocabulary(
        index_terms={},
        raw_terms={
            "bicycle": 25,
            "japanese": 30,
            "hydration": 20,
            "nextjs": 15,
            "pese": 40,
        }
    )
    events_file = tmp_path / "test_events.jsonl"
    hist_store = LocalHistoryStore(events_path=events_file, settings_path=tmp_path / "settings.json")
    sess_mgr = SessionManager(hist_store)
    registry = QueryFamilyRegistry()
    engine = AutocompleteEngine(
        store=store,
        spelling_corrector=corrector,
        history_store=hist_store,
        session_manager=sess_mgr,
        family_registry=registry,
    )
    return engine


def test_cold_start_prefix_match(autocomplete_fixture):
    res = autocomplete_fixture.get_suggestions("jap", limit=5)
    assert len(res.suggestions) > 0
    top = res.suggestions[0]
    assert "japan" in top.text.lower()
    assert top.match_type in ("exact_prefix", "word_prefix")
    assert top.score > 0.0


def test_typo_recovery_autocomplete(autocomplete_fixture):
    # 'byc' should recover to 'bicycle'
    res = autocomplete_fixture.get_suggestions("byc", limit=5)
    assert res.has_typo_correction is True
    assert res.corrected_prefix == "bicycle"
    assert len(res.suggestions) > 0
    assert any("bicycle" in s.text.lower() for s in res.suggestions)


def test_empty_input_handling(autocomplete_fixture):
    res = autocomplete_fixture.get_suggestions("", limit=5)
    assert len(res.suggestions) == 0
    assert res.took_ms >= 0


def test_highlight_ranges(autocomplete_fixture):
    res = autocomplete_fixture.get_suggestions("jap", limit=3)
    assert len(res.suggestions) > 0
    sug = res.suggestions[0]
    assert len(sug.highlight_ranges) > 0
    start, end = sug.highlight_ranges[0]
    matched_substring = sug.text[start:end].lower()
    assert matched_substring == "jap"


def test_deduplication(autocomplete_fixture):
    res = autocomplete_fixture.get_suggestions("jap", limit=10)
    texts = [s.text.lower() for s in res.suggestions]
    # Check no duplicate texts
    assert len(texts) == len(set(texts))
