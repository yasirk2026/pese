"""
Unit tests for PESE Typo Detection and Corpus-Aware Spelling Recovery.
Tests Damerau-Levenshtein distances, transpositions, substitutions,
frequency scaling, and conservative protection rules.
"""

import pytest
from engine.query_analysis.spelling import (
    damerau_levenshtein_distance,
    CorpusSpellingCorrector,
    TypoCorrection,
)


def test_damerau_levenshtein_exact():
    dist, edit_type = damerau_levenshtein_distance("bicycle", "bicycle")
    assert dist == 0
    assert edit_type == "exact"


def test_damerau_levenshtein_transposition():
    # purhcase -> purchase (adjacent swap of 'h' and 'c')
    dist, edit_type = damerau_levenshtein_distance("purhcase", "purchase")
    assert dist == 1
    assert edit_type == "transposition"


def test_damerau_levenshtein_substitution():
    # bycycle -> bicycle (y -> i)
    dist, edit_type = damerau_levenshtein_distance("bycycle", "bicycle")
    assert dist == 1
    assert edit_type == "substitution"


def test_damerau_levenshtein_vowel_inversion():
    # bycicle -> bicycle (two vowel substitutions across consonant)
    dist, edit_type = damerau_levenshtein_distance("bycicle", "bicycle")
    assert dist == 2
    assert edit_type == "multi_edit"


def test_corpus_spelling_corrector_transposition():
    corrector = CorpusSpellingCorrector()
    corrector.build_vocabulary(
        index_terms={},
        raw_terms={"purchase": 5, "bicycle": 20, "hydration": 8},
    )

    correction = corrector.correct_token("purhcase")
    assert correction is not None
    assert correction.corrected_token == "purchase"
    assert correction.edit_distance == 1
    assert correction.edit_type == "transposition"
    assert correction.confidence >= 0.80


def test_corpus_spelling_corrector_vowel_substitution():
    corrector = CorpusSpellingCorrector()
    corrector.build_vocabulary(
        index_terms={},
        raw_terms={"bicycle": 25, "mountain": 4},
    )

    correction = corrector.correct_token("bycycle")
    assert correction is not None
    assert correction.corrected_token == "bicycle"
    assert correction.edit_distance == 1


def test_corpus_spelling_corrector_protection_rules():
    corrector = CorpusSpellingCorrector()
    corrector.build_vocabulary(
        index_terms={},
        raw_terms={"bicycle": 10, "nextjs": 5, "bm25": 12},
        protected_words={"next.js", "bm25", "firestore"},
    )

    # 1. Already known token is never altered
    assert corrector.correct_token("bicycle") is None
    assert corrector.correct_token("bm25") is None

    # 2. Protected technical token is never altered
    assert corrector.correct_token("next.js") is None
    assert corrector.correct_token("firestore") is None

    # 3. Very short token (<= 3 chars) is never altered
    assert corrector.correct_token("cat") is None
    assert corrector.correct_token("xyz") is None

    # 4. Token containing digits is never altered
    assert corrector.correct_token("v2") is None
    assert corrector.correct_token("2024") is None


def test_corpus_spelling_corrector_nonsense_rejection():
    corrector = CorpusSpellingCorrector()
    corrector.build_vocabulary(
        index_terms={},
        raw_terms={"bicycle": 10, "hydration": 5},
    )

    # High edit distance nonsense words must NOT be corrected
    assert corrector.correct_token("flimflamglurp") is None
    assert corrector.correct_token("zoobadongas") is None
    assert corrector.correct_token("xyznonexistent") is None
