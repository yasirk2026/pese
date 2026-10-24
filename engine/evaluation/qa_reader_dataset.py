"""
PESE-QA-0 Reading Benchmark Dataset
Evaluation suite covering Exact Answer, Paraphrase, Multiple Dates, Multi-Fact Disambiguation,
Numeric Spans, and Unanswerables (Abstention).
Strictly decoupled from training and sealed blind acceptance tests.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class QABenchmarkItem(BaseModel):
    id: str
    category: str
    question: str
    context: str
    ground_truth_answer: Optional[str] = None
    is_answerable: bool = True
    metadata: Dict[str, Any] = {}


BENCHMARK_QA_ITEMS: List[QABenchmarkItem] = [
    # 1. Exact Answer
    QABenchmarkItem(
        id="bm-exact-1",
        category="exact_answer",
        question="What algorithm does PESE use for lexical scoring?",
        context="PESE employs fielded BM25F lexical scoring to rank multi-field documents.",
        ground_truth_answer="BM25F",
        is_answerable=True
    ),
    # 2. Paraphrased Question
    QABenchmarkItem(
        id="bm-para-1",
        category="paraphrase",
        question="What was the main consideration when acquiring the bicycle?",
        context="When selecting my first bicycle, I prioritized durability over pure aerodynamic speed.",
        ground_truth_answer="durability over pure aerodynamic speed",
        is_answerable=True
    ),
    # 3. Multiple Dates in Passage
    QABenchmarkItem(
        id="bm-multi-dates-1",
        question="When was the laptop purchased?",
        category="multiple_dates",
        context="I looked at models in January 2022. I finally bought the laptop on 15 May 2023. The device failed in December.",
        ground_truth_answer="15 May 2023",
        is_answerable=True
    ),
    # 4. Multi-Fact Disambiguation (Fact A)
    QABenchmarkItem(
        id="bm-multifact-a",
        category="multi_fact",
        question="When was the project imagined?",
        context="The search project was imagined in 2023. Real implementation commenced in October 2026.",
        ground_truth_answer="2023",
        is_answerable=True
    ),
    # 5. Multi-Fact Disambiguation (Fact B)
    QABenchmarkItem(
        id="bm-multifact-b",
        category="multi_fact",
        question="When did real implementation commence?",
        context="The search project was imagined in 2023. Real implementation commenced in October 2026.",
        ground_truth_answer="October 2026",
        is_answerable=True
    ),
    # 6. Definition
    QABenchmarkItem(
        id="bm-def-1",
        category="definition",
        question="What does BM25F stand for?",
        context="BM25F stands for Best Matching 25 with Fields, an extension of the Okapi BM25 ranking function.",
        ground_truth_answer="Best Matching 25 with Fields",
        is_answerable=True
    ),
    # 7. Who / Named Entity
    QABenchmarkItem(
        id="bm-who-1",
        category="who",
        question="Who pioneered the field of algebra?",
        context="In classical mathematics, Al-Khwarizmi pioneered the foundational rules of algebra in Baghdad.",
        ground_truth_answer="Al-Khwarizmi",
        is_answerable=True
    ),
    # 8. Where / Location
    QABenchmarkItem(
        id="bm-where-1",
        category="where",
        question="Where was the House of Wisdom located?",
        context="The House of Wisdom was a celebrated academy located in Baghdad during the Golden Age.",
        ground_truth_answer="Baghdad",
        is_answerable=True
    ),
    # 9. Numeric Answer
    QABenchmarkItem(
        id="bm-numeric-1",
        category="numeric",
        question="How much did the touring bicycle cost?",
        context="The touring bicycle cost $650 when acquired at the local cycling boutique.",
        ground_truth_answer="$650",
        is_answerable=True
    ),
    # 10. List Answer
    QABenchmarkItem(
        id="bm-list-1",
        category="list",
        question="What should be compared with server HTML?",
        context="To fix hydration bugs: 1. Inspect server HTML. 2. Compare the initial browser render. 3. Fix discrepancies.",
        ground_truth_answer="the initial browser render",
        is_answerable=True
    ),
    # 11. Unanswerable / Abstention (Topic matches, specific answer absent)
    QABenchmarkItem(
        id="bm-unans-1",
        category="unanswerable",
        question="What exact minute did the siege begin?",
        context="The devastating Mongol siege of Baghdad in 1258 resulted in the destruction of classical libraries.",
        ground_truth_answer=None,
        is_answerable=False
    ),
    # 12. Unanswerable / Distractor query
    QABenchmarkItem(
        id="bm-unans-2",
        category="unanswerable",
        question="Who was the prime minister of Mars?",
        context="Tokyo is the bustling capital of Japan and the center of the Greater Tokyo Area.",
        ground_truth_answer=None,
        is_answerable=False
    ),
    # 13. Unanswerable / High lexical overlap but missing fact
    QABenchmarkItem(
        id="bm-unans-3",
        category="unanswerable",
        question="What color bicycle did Yasir buy?",
        context="Yasir purchased a bicycle on 17 March 2024 for commuting across the city.",
        ground_truth_answer=None,
        is_answerable=False
    ),
    # 14. Distractor-Heavy Passage
    QABenchmarkItem(
        id="bm-distractor-1",
        category="distractor_heavy",
        question="Which city is the capital of Japan?",
        context="Kyoto was once the historic capital. Osaka is an economic hub. Today, Tokyo is the official capital of Japan.",
        ground_truth_answer="Tokyo",
        is_answerable=True
    ),
    # 15. Short Answer
    QABenchmarkItem(
        id="bm-short-1",
        category="short_answer",
        question="How many characters are in modern hiragana?",
        context="The modern Japanese hiragana syllabary contains exactly 46 basic characters.",
        ground_truth_answer="46",
        is_answerable=True
    ),
]
