"""
Unit tests for PESE Phase 2B.5: Structured Knowledge Authoring, Native FAQ Schema,
Snippet Markdown Hygiene, Quality Defenses, and Runtime Timing Instrumentation.
"""

from engine.indexing.document import Document
from engine.passages.extractor import PassageExtractor, extract_blocks_from_ast
from engine.passages.highlighter import clean_markdown_for_snippet, SnippetGenerator
from engine.passages.answer_extractor import FeaturedAnswerExtractor
from engine.quality.spam_detector import SpamDetector
from engine.query_analysis.analyzer import AnalyzedQuery
from engine.query_analysis.intent import QueryIntent
from engine.nlp.tokenizer import QueryRepresentation


def test_ast_block_and_faq_passage_extraction():
    structured_doc = Document(
        id="test-ast-doc",
        slug="test-ast-doc",
        title="AST & FAQ Test Document",
        content_schema_version=2,
        content="# AST & FAQ Test Document\n\nBody paragraph.",
        structured_content={
            "type": "doc",
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "Structured Subheading"}]
                },
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "This is a "},
                        {"type": "text", "marks": [{"type": "bold"}], "text": "bold"},
                        {"type": "text", "text": " paragraph."}
                    ]
                },
                {
                    "type": "codeBlock",
                    "attrs": {"language": "python"},
                    "content": [{"type": "text", "text": "print('hello')"}]
                },
                {
                    "type": "blockquote",
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Quoted wisdom."}]}]
                }
            ]
        },
        faqs=[
            {"id": "faq-1", "question": "What is PESE?", "answer": "Personal Evil Search Engine."}
        ]
    )

    extractor = PassageExtractor()
    passages = extractor.extract_passages(structured_doc)

    assert len(passages) >= 4
    block_types = [p.block_type for p in passages]
    assert "paragraph" in block_types
    assert "code" in block_types
    assert "quote" in block_types
    assert "faq" in block_types

    faq_psg = [p for p in passages if p.block_type == "faq"][0]
    assert faq_psg.faq_id == "faq-1"
    assert faq_psg.faq_question == "What is PESE?"
    assert faq_psg.structural_metadata.get("faq_answer") == "Personal Evil Search Engine."


def test_snippet_markdown_hygiene():
    raw_markdown = """### Configuration Guide
You can configure the **database** by setting `DATABASE_URL` in the [Environment File](/doc/env).
```bash
export DATABASE_URL="postgresql://localhost"
```
> Ensure your credentials remain secret.
"""
    cleaned = clean_markdown_for_snippet(raw_markdown)

    # Must strip all formatting tokens
    assert "###" not in cleaned
    assert "**" not in cleaned
    assert "`" not in cleaned
    assert "```" not in cleaned
    assert "[Environment File]" not in cleaned
    assert "> " not in cleaned

    # Must preserve readable text
    assert "Configuration Guide" in cleaned
    assert "database" in cleaned
    assert "Environment File" in cleaned
    assert "Ensure your credentials remain secret" in cleaned

    # SnippetGenerator integration test
    gen = SnippetGenerator()
    snippet = gen.generate_snippet(raw_markdown, QueryRepresentation("database"))
    assert "###" not in snippet["snippet_text"]
    assert "**" not in snippet["snippet_text"]
    assert '<strong class="pese-hit">database</strong>' in snippet["snippet_html"]


def test_faq_featured_answer_extraction():
    extractor = FeaturedAnswerExtractor()
    doc = Document(
        id="faq-doc",
        slug="faq-doc",
        title="FAQ Doc",
        content="General reference content for server ports and configurations.",
        faqs=[{"id": "f1", "question": "What is the port?", "answer": "The server runs on port 8000 by default."}]
    )
    p_extractor = PassageExtractor()
    passages = p_extractor.extract_passages(doc)
    faq_psg = [p for p in passages if p.block_type == "faq"][0]

    analyzed = AnalyzedQuery(
        original_query="What is the port?",
        normalized_query="what is the port",
        effective_query="what is the port",
        intent=QueryIntent.WHAT,
        intent_reason="Direct what query",
        raw_tokens=["what", "is", "the", "port"],
        content_terms=["port"],
        intent_terms=["what"],
        grammatical_terms=["is", "the"],
        effective_content_terms=["port"],
        effective_stems=["port"],
    )

    ans, justification = extractor.extract_answer(
        passage_text=faq_psg.text,
        analyzed_query=analyzed,
        passage_score=10.0,
        document_score=20.0,
        top_passage=faq_psg,
    )

    assert ans == "The server runs on port 8000 by default."
    assert "Native FAQ match" in justification


def test_concise_faq_document_exempt_from_thin_content():
    detector = SpamDetector()
    concise_faq_doc = Document(
        id="short-faq-doc",
        slug="short-faq-doc",
        title="Operational Runbook",
        content="Quick reference guide for common operational tasks.", # 8 words
        faqs=[
            {"id": "q1", "question": "How do I restart the search engine?", "answer": "Run uvicorn api.main:app on port 8000 with lifespan enabled."},
            {"id": "q2", "question": "Where is the vector index stored?", "answer": "The FAISS and metadata vector files are saved under the data directory."},
        ]
    )

    eval_result = detector.evaluate_document(concise_faq_doc)
    assert not any("Thin content" in r for r in eval_result["reasons"])
    assert eval_result["spam_penalty"] == 0.0
