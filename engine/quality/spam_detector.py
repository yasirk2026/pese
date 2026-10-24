"""
PESE Quality: Spam Detector
Detects keyword stuffing, thin content, and unnatural repetition.
Produces an explainable spam penalty between 0.0 (clean) and 0.85 (heavily penalized).
Demonstrates: more keywords != automatically better ranking.
"""

from typing import Dict, List, Tuple, Any
from ..indexing.document import Document
from ..nlp.tokenizer import tokenize
from ..nlp.stopwords import is_stopword


class SpamDetector:
    """Evaluates document quality and spam indicators."""

    def evaluate_document(self, doc: Document) -> Dict[str, Any]:
        """
        Analyze document content and calculate spam penalty with explanation.
        Returns:
            {
                "spam_penalty": float,  # 0.0 to 0.85
                "is_spam": bool,
                "reasons": List[str],
                "max_term_ratio": float,
                "most_frequent_term": str,
                "type_token_ratio": float,
                "word_count": int
            }
        """
        raw_tokens = tokenize(doc.content)
        faq_tokens = []
        for faq in (doc.faqs or []):
            faq_tokens.extend(tokenize(f"{faq.get('question', '')} {faq.get('answer', '')}"))

        combined_tokens = raw_tokens + faq_tokens
        total_tokens = len(combined_tokens)
        reasons: List[str] = []
        penalty = 0.0
        # Field stuffing is manipulation even when the body itself is clean.
        for label, text in (("title", doc.title), ("headings", " ".join(doc.get_all_headings())),
                            ("metadata", doc.meta_description + " " + " ".join(doc.keywords))):
            field_tokens = tokenize(text)
            if len(field_tokens) >= 8 and len(set(field_tokens)) / len(field_tokens) < 0.4:
                penalty += 0.75
                reasons.append(f"Repeated terms in {label}")
        faq_pairs = [(f.get("question", "").strip().lower(), f.get("answer", "").strip().lower()) for f in doc.faqs]
        if len(faq_pairs) >= 4 and len(set(faq_pairs)) / len(faq_pairs) < 0.5:
            penalty += 0.85
            reasons.append("Repeated FAQ entries")

        if total_tokens == 0:
            return {
                "spam_penalty": 0.85,
                "is_spam": True,
                "reasons": ["Completely empty document body"],
                "max_term_ratio": 0.0,
                "most_frequent_term": "",
                "type_token_ratio": 0.0,
                "word_count": 0,
            }

        # Brevity alone is not manipulation. Exact facts may be a single sentence.

        # 2. Keyword Stuffing Detection
        # Count non-stopword frequencies across combined content
        content_term_counts: Dict[str, int] = {}
        content_tokens_count = 0

        for t in combined_tokens:
            if not is_stopword(t) and len(t) >= 2:
                content_term_counts[t] = content_term_counts.get(t, 0) + 1
                content_tokens_count += 1

        max_term = ""
        max_count = 0
        max_ratio = 0.0

        if content_term_counts and content_tokens_count > 0:
            max_term, max_count = max(content_term_counts.items(), key=lambda x: x[1])
            max_ratio = max_count / content_tokens_count

            # If the term is part of doc title, allow normal technical mention density (up to 24%)
            # to prevent legitimate primary entity field repetition from being flagged as keyword stuffing
            is_title_term = max_term in tokenize(doc.title.lower())
            stuffing_threshold = 0.24 if is_title_term else 0.15

            # If a single non-stopword exceeds threshold
            if max_ratio > stuffing_threshold and total_tokens >= 40:
                # Severe stuffing incurs steep penalization up to 92%
                stuffing_severity = min(0.92, (max_ratio - 0.10) * 2.6)
                penalty += stuffing_severity
                reasons.append(
                    f"Keyword stuffing detected: term '{max_term}' accounts for "
                    f"{round(max_ratio * 100, 1)}% of content words ({max_count}/{content_tokens_count})"
                )

        # 3. Type-Token Ratio (TTR) - Vocabulary Diversity
        unique_tokens = len(set(combined_tokens))
        ttr = unique_tokens / total_tokens if total_tokens > 0 else 1.0

        if total_tokens >= 50 and ttr < 0.45:
            repetition_penalty = min(0.40, (0.45 - ttr) * 1.5)
            penalty += repetition_penalty
            reasons.append(
                f"Low vocabulary diversity (TTR={round(ttr, 3)}): heavy repetition detected"
            )

        # 4. Keyword count in meta description or tags stuffing
        if len(doc.keywords) > 15:
            penalty += 0.20
            reasons.append(f"Excessive keyword tags ({len(doc.keywords)} keywords listed)")

        # Cap maximum penalty at 0.95 (leaves slight residual trace for search inspection)
        final_penalty = min(0.95, round(penalty, 4))

        return {
            "spam_penalty": final_penalty,
            "is_spam": final_penalty >= 0.30,
            "reasons": reasons if reasons else ["Clean document: no abnormal spam patterns detected"],
            "max_term_ratio": round(max_ratio, 4),
            "most_frequent_term": max_term,
            "type_token_ratio": round(ttr, 4),
            "word_count": total_tokens,
        }
