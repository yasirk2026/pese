"""
PESE Discovery: Evaluation Benchmark Dataset (Phase 2A)
Defines test suites for Autocomplete, Typo Suggestions, Related Searches,
'You Might Also Ask' (PAA) Answerability, and Session Context.
"""

from typing import List, Dict, Any

# ==================== 1. AUTOCOMPLETE SUITE ====================
AUTOCOMPLETE_TEST_CASES: List[Dict[str, Any]] = [
    {
        "prefix": "jap",
        "description": "Corpus prefix for Japanese cluster",
        "expected_top_contains": "japanese",
        "expected_suggestions": ["Japanese Beginner Roadmap", "Japanese Vocabulary Week 1"],
        "is_typo": False,
    },
    {
        "prefix": "bicy",
        "description": "Corpus prefix for Bicycle cluster",
        "expected_top_contains": "bicycle",
        "expected_suggestions": ["My Bicycle Story", "when did I buy my bicycle"],
        "is_typo": False,
    },
    {
        "prefix": "hydr",
        "description": "Corpus prefix for Hydration cluster",
        "expected_top_contains": "hydration",
        "expected_suggestions": ["Hydration Bugs I Faced", "hydration mismatch error React"],
        "is_typo": False,
    },
    {
        "prefix": "next",
        "description": "Corpus prefix for Next.js cluster",
        "expected_top_contains": "next",
        "expected_suggestions": ["Next.js server components client components", "Next.js Rendering Notes"],
        "is_typo": False,
    },
    {
        "prefix": "pese",
        "description": "Corpus prefix for PESE cluster",
        "expected_top_contains": "pese",
        "expected_suggestions": ["what is pese", "What is PESE Developed With?"],
        "is_typo": False,
    },
    {
        "prefix": "what sh",
        "description": "Multi-word question prefix",
        "expected_top_contains": "what should i learn next in japanese",
        "expected_suggestions": ["What should I learn next in Japanese?"],
        "is_typo": False,
    },
    # Typo prefix recovery tests
    {
        "prefix": "byc",
        "description": "Typo prefix 'byc' -> recovered 'bicycle'",
        "expected_top_contains": "bicycle",
        "expected_suggestions": ["My Bicycle Story", "when did I buy my bicycle"],
        "is_typo": True,
    },
    {
        "prefix": "bycy",
        "description": "Typo prefix 'bycy' -> recovered 'bicycle'",
        "expected_top_contains": "bicycle",
        "expected_suggestions": ["My Bicycle Story", "when did I buy my bicycle"],
        "is_typo": True,
    },
    {
        "prefix": "hyder",
        "description": "Typo prefix 'hyder' -> recovered 'hydration'",
        "expected_top_contains": "hydration",
        "expected_suggestions": ["Hydration Bugs I Faced"],
        "is_typo": True,
    },
]

# ==================== 2. RELATED SEARCHES SUITE ====================
RELATED_SEARCHES_TEST_CASES: List[Dict[str, Any]] = [
    {
        "query": "japanese roadmap",
        "description": "Related searches for Japanese learning roadmap",
        "relevant_terms": ["hiragana", "vocabulary", "kanji", "learn"],
        "must_not_contain": ["bicycle", "hydration", "flimflam"],
        "expected_min_count": 2,
    },
    {
        "query": "hydration error",
        "description": "Related searches for React hydration errors",
        "relevant_terms": ["react", "nextjs", "components", "mismatch"],
        "must_not_contain": ["bicycle", "kanji", "flimflam"],
        "expected_min_count": 2,
    },
    {
        "query": "what is PESE",
        "description": "Related searches for PESE query",
        "relevant_terms": ["pese", "developed", "python", "search"],
        "must_not_contain": ["bicycle", "hiragana"],
        "expected_min_count": 2,
    },
    {
        "query": "when did I buy my bicycle",
        "description": "Related searches for Bicycle purchase and maintenance",
        "relevant_terms": ["bicycle", "maintenance", "bought", "first"],
        "must_not_contain": ["kanji", "react"],
        "expected_min_count": 2,
    },
    # Empty-state safety: garbage / unsupported query MUST return 0 related searches
    {
        "query": "what is flimflamglurp",
        "description": "Unsupported nonsense query: must NOT invent related searches",
        "relevant_terms": [],
        "must_not_contain": [],
        "expected_count": 0,
    },
]

# ==================== 3. 'YOU MIGHT ALSO ASK' (PAA) SUITE ====================
PAA_TEST_CASES: List[Dict[str, Any]] = [
    {
        "query": "what is PESE",
        "description": "PAA for PESE query",
        "expected_answerable_questions": [
            "Who developed PESE?",
            "What is PESE developed with?",
        ],
        "expected_answers_contain": ["Yasir K.", "Python"],
        "must_pass_answerability": True,
    },
    {
        "query": "japanese beginner roadmap",
        "description": "PAA for Japanese beginner roadmap",
        "expected_answerable_questions": [
            "What should I learn next in Japanese?",
        ],
        "expected_answers_contain": ["Kanji", "radicals"],
        "must_pass_answerability": True,
    },
    {
        "query": "hydration mismatch error React",
        "description": "PAA for Hydration error",
        "expected_answerable_questions": [
            "Why do hydration errors happen?",
        ],
        "expected_answers_contain": ["differs from", "DOM"],
        "must_pass_answerability": True,
    },
    # Answerability Gate Safety: Unsupported / Non-existent facts MUST NOT appear
    {
        "query": "what is flimflamglurp",
        "description": "Nonsense query: must NOT surface any PAA question",
        "expected_count": 0,
        "must_pass_answerability": True,
    },
    {
        "query": "xyznonexistent alien language",
        "description": "Unsupported topic: must NOT surface any PAA question",
        "expected_count": 0,
        "must_pass_answerability": True,
    },
]
