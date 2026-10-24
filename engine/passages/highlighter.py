"""
PESE Passages: Highlighter
Generates search result snippets, highlights matching terms, and formats featured passage answers.
"""

import re
from typing import List, Dict, Optional, Any
from ..nlp.tokenizer import QueryRepresentation
from .scorer import extract_matched_date


def clean_markdown_for_snippet(text: str) -> str:
    """
    Strip raw markdown formatting symbols to ensure clean snippet presentation.
    Eliminates headers (###), bold/italics (**, *), links ([text](url)), code backticks,
    and blockquote/list prefixes without losing readable text.
    """
    if not text:
        return ""
    # Strip code blocks
    cleaned = re.sub(r'```[\s\S]*?```', '', text)
    # Strip markdown headings
    cleaned = re.sub(r'(?:^|\n)#+\s*', ' ', cleaned)
    # Convert markdown links [text](url) -> text
    cleaned = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', cleaned)
    # Convert image embeds ![alt](url) -> alt
    cleaned = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', cleaned)
    # Strip bold and italics
    cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)
    cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)
    cleaned = re.sub(r'__([^_]+)__', r'\1', cleaned)
    cleaned = re.sub(r'_([^_]+)_', r'\1', cleaned)
    # Strip inline backticks
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)
    # Strip blockquotes and lists
    cleaned = re.sub(r'(?:^|\n)>\s*', ' ', cleaned)
    cleaned = re.sub(r'(?:^|\n)\s*[-*+]\s+', ' ', cleaned)
    cleaned = re.sub(r'(?:^|\n)\s*\d+\.\s+', ' ', cleaned)
    # Normalize whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def highlight_terms(text: str, query_rep: QueryRepresentation) -> str:
    """
    Wrap query terms, stems, and phrases in <strong> tags.
    Case-insensitive, preserving original casing.
    """
    if not text:
        return ""

    # Collect regex patterns for terms
    terms_to_highlight = set()
    for phrase in query_rep.phrases:
        terms_to_highlight.add(re.escape(phrase))

    for tok in query_rep.filtered_tokens:
        if len(tok) >= 3:
            terms_to_highlight.add(re.escape(tok))

    if not terms_to_highlight:
        return text

    # Sort longest first to avoid partial replacements
    sorted_terms = sorted(terms_to_highlight, key=len, reverse=True)
    pattern = re.compile(r'\b(' + '|'.join(sorted_terms) + r')\b', re.IGNORECASE)

    return pattern.sub(r'<strong class="pese-hit">\1</strong>', text)


class SnippetGenerator:
    """Generates context-rich snippets and featured answers from winning passages."""

    def generate_snippet(
        self,
        passage_text: str,
        query_rep: QueryRepresentation,
        max_chars: int = 240,
        is_featured_candidate: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate snippet text and highlighted HTML.
        If featured candidate and temporal query, formats featured answer prefix.
        """
        if not passage_text:
            return {
                "snippet_text": "",
                "snippet_html": "",
                "featured_answer": None,
                "is_featured": False,
            }

        # Clean raw markdown formatting symbols to ensure clean snippet presentation
        clean_passage = clean_markdown_for_snippet(passage_text)
        if not clean_passage:
            clean_passage = passage_text.strip()

        # Check for temporal featured answer (e.g. '17 March 2024')
        is_when_query = any(w in query_rep.raw_query.lower().split() for w in ["when", "year", "date", "month"])
        matched_date = extract_matched_date(clean_passage) if is_when_query else None

        featured_answer = None
        if is_when_query and matched_date and is_featured_candidate:
            featured_answer = matched_date

        # Window extraction around first match
        text_lower = clean_passage.lower()
        first_match_pos = -1

        for term in query_rep.filtered_tokens:
            pos = text_lower.find(term.lower())
            if pos != -1 and (first_match_pos == -1 or pos < first_match_pos):
                first_match_pos = pos

        if first_match_pos == -1:
            # Fallback to start of text
            snippet_raw = clean_passage[:max_chars].strip()
            if len(clean_passage) > max_chars:
                snippet_raw += "..."
        else:
            # Center window around match
            start = max(0, first_match_pos - 60)
            end = min(len(clean_passage), start + max_chars)

            # Snap to word boundaries
            if start > 0:
                space_before = clean_passage.rfind(" ", 0, start)
                if space_before != -1:
                    start = space_before + 1

            if end < len(clean_passage):
                space_after = clean_passage.find(" ", end)
                if space_after != -1:
                    end = space_after

            snippet_raw = clean_passage[start:end].strip()
            if start > 0:
                snippet_raw = "..." + snippet_raw
            if end < len(clean_passage):
                snippet_raw = snippet_raw + "..."

        snippet_html = highlight_terms(snippet_raw, query_rep)

        return {
            "snippet_text": snippet_raw,
            "snippet_html": snippet_html,
            "featured_answer": featured_answer,
            "is_featured": bool(featured_answer),
        }
