"""
PESE Structured Knowledge: Benchmark Dataset (Phase 2B.5)
Defines benchmark test cases for structured knowledge authoring, TipTap AST indexing,
native FAQ schema retrieval, snippet markdown hygiene, quality defenses, and runtime latency.
"""

from typing import List, Dict, Any

STRUCTURED_ACCEPTANCE_DOC = {
    "id": "pese-architecture-deep-dive",
    "slug": "pese-architecture-deep-dive",
    "title": "PESE Architecture Deep Dive",
    "meta_description": "Comprehensive reference guide to Personal Evil Search Engine internal architecture and runtime systems.",
    "content_schema_version": 2,
    "keywords": ["pese", "architecture", "retrieval", "search", "faq"],
    "internal_links": ["my-first-bicycle", "things-i-bought-in-2024"],
    "status": "published",
    "source_type": "authored",
    "content": """# PESE Architecture Deep Dive

The Personal Evil Search Engine operates on an explainable multi-stage hybrid retrieval architecture.

## Retrieval Subsystems

PESE combines classical lexical BM25F with local dense ONNX semantic vector retrieval.

Here are the primary components:
- Fielded Inverted Index for exact term matching
- Passage-level dense embeddings using bge-small-en
- Reciprocal Rank Fusion with constant k=60

> PESE is designed from first principles: deterministic explainability before neural comprehension.

For custom indexing, invoke the pipeline directly:
```python
results = engine.search("pese architecture", limit=5)
```

For more background on historical purchases, consult [Purchases](/doc/things-i-bought-in-2024).
""",
    "structured_content": {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 1},
                "content": [{"type": "text", "text": "PESE Architecture Deep Dive"}]
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "The Personal Evil Search Engine operates on an "},
                    {"type": "text", "marks": [{"type": "bold"}], "text": "explainable"},
                    {"type": "text", "text": " multi-stage hybrid retrieval architecture."}
                ]
            },
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Retrieval Subsystems"}]
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "PESE combines classical lexical BM25F with local dense ONNX semantic vector retrieval."}
                ]
            },
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Fielded Inverted Index for exact term matching"}]}]
                    },
                    {
                        "type": "listItem",
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Passage-level dense embeddings using bge-small-en"}]}]
                    },
                    {
                        "type": "listItem",
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Reciprocal Rank Fusion with constant k=60"}]}]
                    }
                ]
            },
            {
                "type": "blockquote",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "PESE is designed from first principles: deterministic explainability before neural comprehension."}]}
                ]
            },
            {
                "type": "codeBlock",
                "attrs": {"language": "python"},
                "content": [{"type": "text", "text": "results = engine.search(\"pese architecture\", limit=5)"}]
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "For more background on historical purchases, consult "},
                    {"type": "text", "marks": [{"type": "link", "attrs": {"href": "/doc/things-i-bought-in-2024"}}], "text": "Purchases"},
                    {"type": "text", "text": "."}
                ]
            }
        ]
    },
    "faqs": [
        {
            "id": "faq-arch-1",
            "question": "What retrieval models does PESE use?",
            "answer": "PESE combines fielded BM25F lexical scoring with dense semantic vectors fused through Reciprocal Rank Fusion."
        },
        {
            "id": "faq-arch-2",
            "question": "How does PESE prevent semantic hallucination?",
            "answer": "PESE enforces a strict Minimum Evidence Gate and semantic drift protection before ranking candidates."
        },
        {
            "id": "faq-arch-3",
            "question": "How does PESE handle typo recovery?",
            "answer": "PESE uses a corpus-aware Damerau-Levenshtein spelling corrector with vocabulary frequency validation."
        }
    ]
}

STRUCTURED_BENCHMARK_CASES = [
    {
        "id": "sb-01",
        "category": "faq_retrieval",
        "query": "What retrieval models does PESE use?",
        "expected_slug": "pese-architecture-deep-dive",
        "expected_answer_fragment": "PESE combines fielded BM25F lexical scoring with dense semantic vectors",
        "description": "Native FAQ Question query retrieves author-crafted direct answer",
    },
    {
        "id": "sb-02",
        "category": "faq_retrieval",
        "query": "How does PESE prevent semantic hallucination?",
        "expected_slug": "pese-architecture-deep-dive",
        "expected_answer_fragment": "Minimum Evidence Gate and semantic drift protection",
        "description": "Native FAQ Question query extracts exact answer via passage block",
    },
    {
        "id": "sb-03",
        "category": "snippet_hygiene",
        "query": "pese architecture deep dive",
        "expected_slug": "pese-architecture-deep-dive",
        "prohibited_tokens": ["###", "##", "**", "```", "[Purchases]"],
        "description": "Snippet text must not leak raw markdown symbols",
    },
    {
        "id": "sb-04",
        "category": "paa_faq_incorporation",
        "query": "pese architecture",
        "expected_paa_fragment": "What retrieval models does PESE use?",
        "description": "PAA engine incorporates native FAQ questions and passes Answerability Gate",
    },
]
