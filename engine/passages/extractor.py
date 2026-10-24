"""
PESE Passages: Extractor
Segments documents into structural passages (paragraphs/blocks) with heading context,
block types, and native FAQ items.
"""

import re
from typing import List, Tuple, Optional, Dict, Any
from ..indexing.document import Document
from ..indexing.passage import Passage
from ..nlp.normalizer import clean_whitespace
from ..nlp.tokenizer import tokenize
from ..nlp.stemmer import stem_word
from ..nlp.stopwords import filter_stopwords
from .highlighter import clean_markdown_for_snippet


HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$')


def split_into_raw_blocks(content: str) -> List[Tuple[str, str, int, int, str, int]]:
    """
    Split markdown content into raw text blocks while tracking preceding headings and offsets.
    Returns list of (block_text, heading_context, start_offset, end_offset, block_type, heading_level).
    """
    lines = content.splitlines(keepends=True)
    blocks: List[Tuple[str, str, int, int, str, int]] = []

    current_heading = ""
    current_heading_level = 0
    current_block_lines: List[str] = []
    current_block_start = 0
    current_offset = 0

    def detect_block_type(text: str) -> str:
        s = text.strip()
        if s.startswith("```"):
            return "code"
        if s.startswith(">"):
            return "quote"
        if re.match(r'^[-*+]\s+|\d+\.\s+', s):
            return "list_item"
        return "paragraph"

    for line in lines:
        line_len = len(line)
        stripped = line.strip()

        # Check for heading
        heading_match = HEADING_PATTERN.match(stripped)
        if heading_match:
            # If we had a running block, flush it
            if current_block_lines:
                block_text = "".join(current_block_lines).strip()
                if len(block_text) > 15:
                    b_type = detect_block_type(block_text)
                    blocks.append((block_text, current_heading, current_block_start, current_offset, b_type, current_heading_level))
                current_block_lines = []

            current_heading_level = len(heading_match.group(1))
            current_heading = heading_match.group(2).strip()
            current_offset += line_len
            current_block_start = current_offset
            continue

        # Blank line triggers block separation
        if not stripped:
            if current_block_lines:
                block_text = "".join(current_block_lines).strip()
                if len(block_text) > 15:
                    b_type = detect_block_type(block_text)
                    blocks.append((block_text, current_heading, current_block_start, current_offset, b_type, current_heading_level))
                current_block_lines = []
            current_offset += line_len
            current_block_start = current_offset
            continue

        # Non-empty content line
        if not current_block_lines:
            current_block_start = current_offset
        current_block_lines.append(line)
        current_offset += line_len

    # Flush final block
    if current_block_lines:
        block_text = "".join(current_block_lines).strip()
        if len(block_text) > 15:
            b_type = detect_block_type(block_text)
            blocks.append((block_text, current_heading, current_block_start, current_offset, b_type, current_heading_level))

    return blocks


def extract_blocks_from_ast(ast: dict) -> List[Tuple[str, str, int, str, List[str], Dict[str, Any]]]:
    """
    Traverse TipTap/ProseMirror AST nodes.
    Returns list of (text, heading_context, heading_level, block_type, marks, metadata).
    """
    blocks = []
    current_heading = ""
    current_heading_level = 0

    def extract_text_and_marks(node: dict) -> Tuple[str, List[str]]:
        text_parts = []
        marks = set()
        def recurse(n: dict):
            if n.get("type") == "text":
                text_parts.append(n.get("text", ""))
                for m in n.get("marks", []):
                    marks.add(m.get("type", ""))
            for child in n.get("content", []):
                recurse(child)
        recurse(node)
        return "".join(text_parts).strip(), list(marks)

    content_nodes = ast.get("content", [])
    for node in content_nodes:
        node_type = node.get("type")
        if node_type == "heading":
            attrs = node.get("attrs", {})
            lvl = attrs.get("level", 1)
            h_text, _ = extract_text_and_marks(node)
            if h_text:
                current_heading = h_text
                current_heading_level = lvl
        elif node_type == "paragraph":
            p_text, marks = extract_text_and_marks(node)
            if len(p_text) > 10:
                blocks.append((p_text, current_heading, current_heading_level, "paragraph", marks, {}))
        elif node_type == "blockquote":
            q_text, marks = extract_text_and_marks(node)
            if len(q_text) > 10:
                blocks.append((q_text, current_heading, current_heading_level, "quote", marks, {}))
        elif node_type == "codeBlock":
            c_text, marks = extract_text_and_marks(node)
            lang = node.get("attrs", {}).get("language", "")
            if len(c_text) > 5:
                blocks.append((c_text, current_heading, current_heading_level, "code", marks, {"language": lang}))
        elif node_type in ("bulletList", "orderedList"):
            for li in node.get("content", []):
                li_text, marks = extract_text_and_marks(li)
                if len(li_text) > 5:
                    blocks.append((li_text, current_heading, current_heading_level, "list_item", marks, {"list_type": node_type}))

    return blocks


class PassageExtractor:
    """Extracts indexed passages from a Document."""

    def extract_passages(self, doc: Document) -> List[Passage]:
        passages: List[Passage] = []
        ast_blocks = []
        if doc.structured_content and isinstance(doc.structured_content, dict):
            ast_blocks = extract_blocks_from_ast(doc.structured_content)

        if ast_blocks:
            for idx, (text, heading, h_level, b_type, marks, meta) in enumerate(ast_blocks):
                clean_text = clean_whitespace(text)
                tokens = tokenize(clean_text)
                filtered = filter_stopwords(tokens, preserve_intent=True)
                stems = [stem_word(t) for t in filtered]
                passages.append(
                    Passage(
                        passage_id=f"{doc.slug}#p{idx}",
                        doc_id=doc.id,
                        slug=doc.slug,
                        doc_title=doc.title,
                        text=clean_text,
                        heading_context=heading if heading else None,
                        heading_level=h_level if h_level else None,
                        block_type=b_type,
                        marks=marks,
                        structural_metadata=meta,
                        tokens=tokens,
                        stems=stems,
                        token_count=len(tokens),
                        offset_start=0,
                        offset_end=len(clean_text),
                        passage_index=idx,
                    )
                )
        else:
            raw_blocks = split_into_raw_blocks(doc.content)
            # If document has no blocks (e.g. very short content), use the entire body
            if not raw_blocks and doc.content.strip():
                raw_blocks = [(doc.content.strip(), "", 0, len(doc.content), "paragraph", 0)]

            for idx, (text, heading, start, end, b_type, h_level) in enumerate(raw_blocks):
                clean_text = clean_whitespace(clean_markdown_for_snippet(text)) if b_type != "code" else clean_whitespace(text)
                tokens = tokenize(clean_text)
                filtered = filter_stopwords(tokens, preserve_intent=True)
                stems = [stem_word(t) for t in filtered]

                passages.append(
                    Passage(
                        passage_id=f"{doc.slug}#p{idx}",
                        doc_id=doc.id,
                        slug=doc.slug,
                        doc_title=doc.title,
                        text=clean_text,
                        heading_context=heading if heading else None,
                        heading_level=h_level if h_level else None,
                        block_type=b_type,
                        tokens=tokens,
                        stems=stems,
                        token_count=len(tokens),
                        offset_start=start,
                        offset_end=end,
                        passage_index=idx,
                    )
                )

        # 3. Add Native FAQ Schema passages
        if doc.faqs:
            for f_idx, faq in enumerate(doc.faqs):
                q = clean_markdown_for_snippet(faq.get("question", "")).strip()
                a = clean_markdown_for_snippet(faq.get("answer", "")).strip()
                f_id = faq.get("id") or f"faq-{f_idx+1}"
                if q and a:
                    faq_text = f"{q}\n{a}"
                    clean_text = clean_whitespace(faq_text)
                    tokens = tokenize(clean_text)
                    filtered = filter_stopwords(tokens, preserve_intent=True)
                    stems = [stem_word(t) for t in filtered]

                    passages.append(
                        Passage(
                            passage_id=f"{doc.slug}#{f_id}",
                            doc_id=doc.id,
                            slug=doc.slug,
                            doc_title=doc.title,
                            text=clean_text,
                            heading_context="Frequently Asked Questions",
                            heading_level=3,
                            block_type="faq",
                            faq_id=f_id,
                            faq_question=q,
                            structural_metadata={"faq_answer": a},
                            tokens=tokens,
                            stems=stems,
                            token_count=len(tokens),
                            offset_start=0,
                            offset_end=len(clean_text),
                            passage_index=len(passages),
                        )
                    )

        return passages
