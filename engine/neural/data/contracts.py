"""
PESE Neural Genesis: Data Contracts & QA Grounding Schemas
Defines schemas for future PESE-QA-0 extractive question-answering,
deterministic span localization, abstention (no evidence = no answer),
and pairwise reranker pairs.
"""

from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field
from ..tokenization.base import BaseTokenizer


class QAExample(BaseModel):
    """
    Extractive QA contract for future PESE-QA-0 models.
    Supports both answerable queries (exact character/token span) and
    unanswerable queries (abstention: is_answerable=False).
    """
    id: str
    question: str
    context: str
    answer_text: Optional[str] = None
    answer_start_char: Optional[int] = None
    answer_end_char: Optional[int] = None
    answer_start_token: Optional[int] = None
    answer_end_token: Optional[int] = None
    is_answerable: bool = True
    abstention_reason: Optional[str] = None
    source_doc_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RerankerPair(BaseModel):
    """
    Pairwise ranking contract for future neural cross-encoders / rerankers.
    Defines a query with a positive (relevant) passage and a negative (distractor) passage.
    """
    query: str
    doc_positive: str
    doc_negative: str
    doc_id_pos: str
    doc_id_neg: str
    margin: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


def find_answer_span(
    context: str,
    answer_text: Optional[str],
    tokenizer: Optional[BaseTokenizer] = None
) -> Dict[str, Any]:
    """
    Deterministically locates the character and token offsets of `answer_text` within `context`.

    Returns a dict with:
        found: bool
        start_char: Optional[int]
        end_char: Optional[int]
        start_token: Optional[int]
        end_token: Optional[int]
    """
    if not answer_text or not context:
        return {
            "found": False,
            "start_char": None,
            "end_char": None,
            "start_token": None,
            "end_token": None,
        }

    # 1. Exact match search
    start_char = context.find(answer_text)
    if start_char == -1:
        # Case-insensitive fallback
        lower_context = context.lower()
        lower_answer = answer_text.lower()
        start_char = lower_context.find(lower_answer)

    if start_char == -1:
        return {
            "found": False,
            "start_char": None,
            "end_char": None,
            "start_token": None,
            "end_token": None,
        }

    end_char = start_char + len(answer_text)

    # 2. Token offset mapping if tokenizer is provided
    start_token = None
    end_token = None

    if tokenizer is not None:
        # Tokenize prefix before the answer to find token start
        prefix = context[:start_char]
        prefix_tokens = tokenizer.encode(prefix)
        start_token = len(prefix_tokens)

        # Tokenize the answer text to find token length
        answer_tokens = tokenizer.encode(answer_text)
        end_token = start_token + len(answer_tokens)

    return {
        "found": True,
        "start_char": start_char,
        "end_char": end_char,
        "start_token": start_token,
        "end_token": end_token,
    }


def export_faqs_to_qa_contracts(
    documents: List[Dict[str, Any]],
    tokenizer: Optional[BaseTokenizer] = None,
    include_negative_abstentions: bool = True
) -> List[QAExample]:
    """
    Converts knowledge documents with native FAQ schemas into structured QAExample contracts.
    Also optionally generates explicit unanswerable negative queries to teach abstention
    ('NO EVIDENCE = NO ANSWER').
    """
    qa_examples: List[QAExample] = []

    for doc in documents:
        doc_id = doc.get("id") or doc.get("slug", "unknown")
        title = doc.get("title", "")
        content = doc.get("content", "")
        faqs = doc.get("faqs", [])

        # Build full context including title and content
        full_context = f"{title}\n\n{content}".strip()

        for idx, faq in enumerate(faqs):
            q_text = faq.get("question", "").strip()
            a_text = faq.get("answer", "").strip()
            if not q_text or not a_text:
                continue

            # Check if answer exists in context or if FAQ answer should be appended
            target_context = full_context
            span = find_answer_span(target_context, a_text, tokenizer)

            if not span["found"]:
                # If the FAQ answer is not explicitly in the body, include FAQ in context
                target_context = f"{full_context}\n\nQ: {q_text}\nA: {a_text}".strip()
                span = find_answer_span(target_context, a_text, tokenizer)

            qa_examples.append(
                QAExample(
                    id=f"{doc_id}-faq-{idx}",
                    question=q_text,
                    context=target_context,
                    answer_text=a_text if span["found"] else None,
                    answer_start_char=span["start_char"],
                    answer_end_char=span["end_char"],
                    answer_start_token=span["start_token"],
                    answer_end_token=span["end_token"],
                    is_answerable=span["found"],
                    source_doc_id=doc_id,
                    metadata={"source": "faq_schema", "faq_index": idx}
                )
            )

        # Generate negative abstention example if requested
        if include_negative_abstentions and full_context:
            qa_examples.append(
                QAExample(
                    id=f"{doc_id}-unanswerable-neg",
                    question=f"What is the secret recipe for quantum cold fusion in {title}?",
                    context=full_context,
                    answer_text=None,
                    answer_start_char=None,
                    answer_end_char=None,
                    answer_start_token=None,
                    answer_end_token=None,
                    is_answerable=False,
                    abstention_reason="NO EVIDENCE = NO ANSWER",
                    source_doc_id=doc_id,
                    metadata={"negative_sample": True}
                )
            )

    return qa_examples
