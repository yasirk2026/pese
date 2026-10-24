"""
PESE-QA-0: QA Dataset, Sliding Window Tokenizer Alignment & Provenance Tracking
Converts QAExample instances into model input features with exact token-to-character spans.
"""

from typing import List, Dict, Tuple, Optional, Any
import torch
from torch.utils.data import Dataset, DataLoader
from pydantic import BaseModel

from .contracts import QAExample, find_answer_span
from ..tokenization.base import BaseTokenizer


class QAInputFeature(BaseModel):
    """Token-level input representation for PESE-QA-0 with provenance tracking."""
    example_id: str
    input_ids: List[int]
    token_type_ids: List[int]
    attention_mask: List[int]
    start_position: int
    end_position: int
    is_answerable: int
    token_to_char_offsets: List[Optional[Tuple[int, int]]]
    context_token_start: int
    context_token_end: int


import re

def tokenize_with_char_offsets(
    text: str,
    tokenizer: BaseTokenizer
) -> Tuple[List[int], List[Tuple[int, int]]]:
    """
    Tokenizes text into subwords while tracking the exact (char_start, char_end)
    offsets for each token in the original text.
    """
    tokens: List[int] = []
    offsets: List[Tuple[int, int]] = []

    # Use regex to find all words and punctuation with exact character spans
    matches = list(re.finditer(r"\w+|[^\w\s]", text, re.UNICODE))
    for m in matches:
        w = m.group()
        start_char = m.start()
        end_char = m.end()

        subwords = tokenizer.encode(w, add_special_tokens=False)
        if not subwords:
            subwords = [tokenizer.unk_token_id]

        if len(subwords) == 1:
            tokens.append(subwords[0])
            offsets.append((start_char, end_char))
        else:
            cur = start_char
            inv_vocab = getattr(tokenizer, "inverse_vocab", {})
            for i, sid in enumerate(subwords):
                if i == len(subwords) - 1:
                    sub_s = cur
                    sub_e = end_char
                else:
                    raw_tok = inv_vocab.get(sid, "").replace("</w>", "")
                    t_len = max(1, len(raw_tok)) if raw_tok else 1
                    sub_s = cur
                    sub_e = min(end_char, cur + t_len)
                    cur = sub_e
                tokens.append(sid)
                offsets.append((sub_s, sub_e))

    return tokens, offsets


def build_qa_features(
    example: QAExample,
    tokenizer: BaseTokenizer,
    max_seq_len: int = 128,
    doc_stride: int = 32
) -> List[QAInputFeature]:
    """
    Converts a QAExample into one or more QAInputFeature objects.
    Uses sliding window chunking if the passage exceeds the model's max sequence length.
    """
    cls_token_id = tokenizer.bos_token_id
    sep_token_id = tokenizer.eos_token_id
    pad_token_id = tokenizer.pad_token_id

    # 1. Tokenize question
    q_tokens = tokenizer.encode(example.question, add_special_tokens=False)
    # Reserve room for [CLS], [SEP], context, and [SEP]
    max_q_len = max_seq_len // 3
    if len(q_tokens) > max_q_len:
        q_tokens = q_tokens[:max_q_len]

    # 2. Tokenize context with character offsets
    c_tokens, c_offsets = tokenize_with_char_offsets(example.context, tokenizer)

    # 3. Locate target character span in context
    has_answer = example.is_answerable and example.answer_start_char is not None and example.answer_end_char is not None
    target_start_char = example.answer_start_char if has_answer else -1
    target_end_char = example.answer_end_char if has_answer else -1

    # Maximum context tokens per window
    # Format: [CLS] + Q + [SEP] + C_window + [SEP]
    overhead = 3 + len(q_tokens)
    max_c_window_len = max_seq_len - overhead
    if max_c_window_len < 10:
        max_c_window_len = 10

    features: List[QAInputFeature] = []
    window_start = 0

    while True:
        window_end = min(len(c_tokens), window_start + max_c_window_len)
        window_c_tokens = c_tokens[window_start:window_end]
        window_c_offsets = c_offsets[window_start:window_end]

        # Construct input_ids: [CLS] + Q + [SEP] + Window_C + [SEP]
        input_ids = [cls_token_id] + q_tokens + [sep_token_id] + window_c_tokens + [sep_token_id]
        token_type_ids = [0] * (2 + len(q_tokens)) + [1] * (len(window_c_tokens) + 1)
        attention_mask = [1] * len(input_ids)

        context_token_start = 2 + len(q_tokens)
        context_token_end = context_token_start + len(window_c_tokens)

        # Build token_to_char_offsets mapping for all tokens in input_ids
        token_to_char: List[Optional[Tuple[int, int]]] = [None] * context_token_start
        token_to_char.extend(window_c_offsets)
        token_to_char.append(None)  # Trailing [SEP]

        # Determine target start and end positions in this window
        start_pos = 0  # Default to [CLS] (null span / unanswerable)
        end_pos = 0
        is_ans = 0

        if has_answer and len(window_c_offsets) > 0:
            window_first_char = window_c_offsets[0][0]
            window_last_char = window_c_offsets[-1][1]

            # Check if target answer span is fully within this window
            if window_first_char <= target_start_char and target_end_char <= window_last_char:
                # Find token indices
                matched_start = None
                matched_end = None

                for idx, (cs, ce) in enumerate(window_c_offsets):
                    if matched_start is None and ce > target_start_char:
                        matched_start = context_token_start + idx
                    if cs < target_end_char:
                        matched_end = context_token_start + idx

                if matched_start is not None and matched_end is not None and matched_end >= matched_start:
                    start_pos = matched_start
                    end_pos = matched_end
                    is_ans = 1

        # Pad to max_seq_len
        pad_len = max_seq_len - len(input_ids)
        if pad_len > 0:
            input_ids += [pad_token_id] * pad_len
            token_type_ids += [0] * pad_len
            attention_mask += [0] * pad_len
            token_to_char += [None] * pad_len

        features.append(
            QAInputFeature(
                example_id=example.id,
                input_ids=input_ids,
                token_type_ids=token_type_ids,
                attention_mask=attention_mask,
                start_position=start_pos,
                end_position=end_pos,
                is_answerable=is_ans,
                token_to_char_offsets=token_to_char,
                context_token_start=context_token_start,
                context_token_end=context_token_end
            )
        )

        if window_end >= len(c_tokens):
            break
        window_start += doc_stride

    return features


class ExtractiveQADataset(Dataset):
    """PyTorch Dataset yielding tensors for PESE-QA-0."""

    def __init__(self, features: List[QAInputFeature]):
        self.features = features

    def __len__(self) -> int:
        return len(self.features)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        feat = self.features[idx]
        return {
            "input_ids": torch.tensor(feat.input_ids, dtype=torch.long),
            "token_type_ids": torch.tensor(feat.token_type_ids, dtype=torch.long),
            "attention_mask": torch.tensor(feat.attention_mask, dtype=torch.long),
            "start_positions": torch.tensor(feat.start_position, dtype=torch.long),
            "end_positions": torch.tensor(feat.end_position, dtype=torch.long),
            "is_answerable": torch.tensor(feat.is_answerable, dtype=torch.long),
        }


# ---------------------------------------------------------------------------
# STAGE A: Synthetic Sanity Set (5 examples)
# ---------------------------------------------------------------------------
STAGE_A_SANITY_EXAMPLES = [
    QAExample(
        id="sanity-1",
        question="When was the bicycle purchased?",
        context="After months of research, I finally bought my bicycle on 17 March 2024 from the shop.",
        answer_text="17 March 2024",
        answer_start_char=52,
        answer_end_char=65,
        is_answerable=True
    ),
    QAExample(
        id="sanity-2",
        question="What language is PESE developed with?",
        context="Personal Evil Search Engine is developed with Python and Next.js for high performance.",
        answer_text="Python",
        answer_start_char=46,
        answer_end_char=52,
        is_answerable=True
    ),
    QAExample(
        id="sanity-3",
        question="Who invented the telephone?",
        context="Personal Evil Search Engine uses BM25F lexical ranking and dense vector embeddings.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
    QAExample(
        id="sanity-4",
        question="What is the capital of Japan?",
        context="Tokyo is the bustling capital of Japan and the center of the Greater Tokyo Area.",
        answer_text="Tokyo",
        answer_start_char=0,
        answer_end_char=5,
        is_answerable=True
    ),
    QAExample(
        id="sanity-5",
        question="How many wheels does a bicycle have?",
        context="A standard bicycle is a pedal-driven vehicle with two wheels attached to a frame.",
        answer_text="two wheels",
        answer_start_char=50,
        answer_end_char=60,
        is_answerable=True
    ),
]


# ---------------------------------------------------------------------------
# STAGE B: Micro-Overfit QA Set (25 diverse examples)
# Tests dates, names, definitions, multi-facts in same passage, and unanswerables
# ---------------------------------------------------------------------------
STAGE_B_MICRO_OVERFIT_EXAMPLES = [
    # Multi-Fact Disambiguation in Same Passage (Fact 1)
    QAExample(
        id="overfit-mf-1",
        question="When was the project imagined?",
        context="The search project was imagined in 2023. Real implementation commenced in October 2026.",
        answer_text="2023",
        answer_start_char=35,
        answer_end_char=39,
        is_answerable=True
    ),
    # Multi-Fact Disambiguation in Same Passage (Fact 2)
    QAExample(
        id="overfit-mf-2",
        question="When did real implementation commence?",
        context="The search project was imagined in 2023. Real implementation commenced in October 2026.",
        answer_text="October 2026",
        answer_start_char=74,
        answer_end_char=86,
        is_answerable=True
    ),
    # Distractor Test (Multiple Dates)
    QAExample(
        id="overfit-distractor-dates",
        question="When was the laptop purchased?",
        context="I looked at models in January 2022. I finally bought the laptop on 15 May 2023. It broke in December.",
        answer_text="15 May 2023",
        answer_start_char=67,
        answer_end_char=78,
        is_answerable=True
    ),
    # Numeric Answer
    QAExample(
        id="overfit-num-1",
        question="How much did the bicycle cost?",
        context="The touring bicycle cost $650 when acquired at the local cycling boutique.",
        answer_text="$650",
        answer_start_char=25,
        answer_end_char=29,
        is_answerable=True
    ),
    # Paraphrased Question (prioritized -> mattered most)
    QAExample(
        id="overfit-para-1",
        question="What mattered most when choosing the bicycle?",
        context="When selecting my first bicycle, I prioritized durability over pure aerodynamic speed.",
        answer_text="durability over pure aerodynamic speed",
        answer_start_char=47,
        answer_end_char=85,
        is_answerable=True
    ),
    # Definition
    QAExample(
        id="overfit-def-1",
        question="What is BM25F?",
        context="BM25F is a fielded ranking algorithm that weights terms differently across title and body.",
        answer_text="a fielded ranking algorithm",
        answer_start_char=9,
        answer_end_char=36,
        is_answerable=True
    ),
    # Entity / Who
    QAExample(
        id="overfit-who-1",
        question="Who pioneered the field of algebra?",
        context="In classical mathematics, Al-Khwarizmi pioneered the foundational rules of algebra.",
        answer_text="Al-Khwarizmi",
        answer_start_char=26,
        answer_end_char=38,
        is_answerable=True
    ),
    # Location / Where
    QAExample(
        id="overfit-where-1",
        question="Where was the House of Wisdom located?",
        context="The House of Wisdom was a celebrated academy located in Baghdad during the Golden Age.",
        answer_text="Baghdad",
        answer_start_char=56,
        answer_end_char=63,
        is_answerable=True
    ),
    # Duration / End
    QAExample(
        id="overfit-end-1",
        question="When did the classical era end?",
        context="The historical era flourished for centuries and came to an end in 1258 CE following the siege.",
        answer_text="1258 CE",
        answer_start_char=66,
        answer_end_char=73,
        is_answerable=True
    ),
    # Unanswerable Abstention 1 (Topic matches, but specific question unanswerable)
    QAExample(
        id="overfit-unans-1",
        question="What exact time of day did the siege happen?",
        context="The historical era flourished for centuries and came to an end in 1258 CE following the siege.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
    # Unanswerable Abstention 2 (Complete distractor query)
    QAExample(
        id="overfit-unans-2",
        question="What color shirt was the author wearing?",
        context="The search engine indexes multi-field documents using inverted postings lists.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
    # Unanswerable Abstention 3
    QAExample(
        id="overfit-unans-3",
        question="Who was the president of the moon colony?",
        context="Tokyo is the bustling capital of Japan and the center of the Greater Tokyo Area.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
    # List Answer
    QAExample(
        id="overfit-list-1",
        question="What should be compared with server HTML?",
        context="To fix hydration bugs: 1. Inspect server HTML. 2. Compare the initial browser render. 3. Fix discrepancies.",
        answer_text="the initial browser render",
        answer_start_char=58,
        answer_end_char=84,
        is_answerable=True
    ),
    # Short Answer
    QAExample(
        id="overfit-short-1",
        question="How many characters does hiragana have?",
        context="The standard modern Japanese hiragana syllabary contains exactly 46 basic characters.",
        answer_text="46",
        answer_start_char=65,
        answer_end_char=67,
        is_answerable=True
    ),
    # Technology / Tooling
    QAExample(
        id="overfit-tech-1",
        question="What frontend framework does PESE use?",
        context="The frontend is constructed using Next.js with React server components.",
        answer_text="Next.js",
        answer_start_char=34,
        answer_end_char=41,
        is_answerable=True
    ),
]


# ---------------------------------------------------------------------------
# STAGE C: Public Synthetic QA Corpus (Clean, Open Knowledge)
# ---------------------------------------------------------------------------
STAGE_C_PUBLIC_QA_CORPUS = [
    # IR & Search
    QAExample(
        id="pub-1",
        question="What does BM25F stand for?",
        context="BM25F stands for Best Matching 25 with Fields, an extension of the Okapi BM25 ranking function.",
        answer_text="Best Matching 25 with Fields",
        answer_start_char=17,
        answer_end_char=45,
        is_answerable=True
    ),
    QAExample(
        id="pub-2",
        question="What does an inverted index store?",
        context="An inverted index stores postings lists mapping terms to document IDs and positions.",
        answer_text="postings lists mapping terms to document IDs and positions",
        answer_start_char=26,
        answer_end_char=84,
        is_answerable=True
    ),
    QAExample(
        id="pub-3",
        question="How does Reciprocal Rank Fusion combine rankings?",
        context="Reciprocal Rank Fusion merges rankings by summing reciprocal ranks without requiring score normalization.",
        answer_text="summing reciprocal ranks without requiring score normalization",
        answer_start_char=43,
        answer_end_char=105,
        is_answerable=True
    ),
    QAExample(
        id="pub-4",
        question="What prevents hallucinated answers in search engines?",
        context="Search engines employ Minimum Evidence Gating to reject speculative answers when support is inadequate.",
        answer_text="Minimum Evidence Gating",
        answer_start_char=22,
        answer_end_char=45,
        is_answerable=True
    ),
    QAExample(
        id="pub-5",
        question="What is the speed of light in vacuum?",
        context="The inverted index allows constant time term lookup through deterministic hash tables.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
    # Transformers & Neural Nets
    QAExample(
        id="pub-6",
        question="What activation function does the Transformer FFN use?",
        context="Modern Transformer architectures employ the GELU activation function in position-wise feed-forward layers.",
        answer_text="GELU",
        answer_start_char=45,
        answer_end_char=49,
        is_answerable=True
    ),
    QAExample(
        id="pub-7",
        question="Why are residual connections used in deep networks?",
        context="Residual connections enable direct gradient propagation across deep layers to avoid vanishing gradients.",
        answer_text="enable direct gradient propagation across deep layers",
        answer_start_char=21,
        answer_end_char=74,
        is_answerable=True
    ),
    QAExample(
        id="pub-8",
        question="What optimizer decouples weight decay from gradient updates?",
        context="The AdamW optimizer directly applies weight decay to parameters rather than folding it into the gradient.",
        answer_text="AdamW optimizer",
        answer_start_char=4,
        answer_end_char=19,
        is_answerable=True
    ),
    QAExample(
        id="pub-9",
        question="What is the formula for quantum gravity?",
        context="Layer normalization normalizes activations across feature channels per sequence position.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
    # History & Science
    QAExample(
        id="pub-10",
        question="What ancient academy was founded in Baghdad?",
        context="The House of Wisdom was established in Baghdad as a center for scholarship, translation, and science.",
        answer_text="The House of Wisdom",
        answer_start_char=0,
        answer_end_char=19,
        is_answerable=True
    ),
    QAExample(
        id="pub-11",
        question="When was paper manufacturing introduced from China to the Islamic world?",
        context="Scholars learned paper manufacturing in the 8th century, which drastically lowered the cost of books.",
        answer_text="the 8th century",
        answer_start_char=40,
        answer_end_char=55,
        is_answerable=True
    ),
    QAExample(
        id="pub-12",
        question="What city suffered the siege of 1258?",
        context="The devastating Mongol siege of Baghdad in 1258 resulted in the destruction of classical libraries.",
        answer_text="Baghdad",
        answer_start_char=32,
        answer_end_char=39,
        is_answerable=True
    ),
    QAExample(
        id="pub-13",
        question="What exact minute did the treaty sign?",
        context="The devastating Mongol siege of Baghdad in 1258 resulted in the destruction of classical libraries.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
    QAExample(
        id="pub-14-unans",
        question="Who is the king of Mars?",
        context="BM25F stands for Best Matching 25 with Fields, an extension of the Okapi BM25 ranking function.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
    QAExample(
        id="pub-15-unans",
        question="What is the recipe for chocolate cake?",
        context="The House of Wisdom was established in Baghdad as a center for scholarship, translation, and science.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
    QAExample(
        id="pub-16-unans",
        question="When was the atomic bomb dropped?",
        context="An inverted index stores postings lists mapping terms to document IDs and positions.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
    QAExample(
        id="pub-17-unans",
        question="Who won the 2020 World Cup?",
        context="Modern Transformer architectures employ the GELU activation function in position-wise feed-forward layers.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
    QAExample(
        id="pub-18-unans",
        question="How many kilometers is the Amazon river?",
        context="Scholars learned paper manufacturing in the 8th century, which drastically lowered the cost of books.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
    # Numbers, Prices & Quantities
    QAExample(
        id="pub-19-num",
        question="How much did the bicycle cost?",
        context="The touring bicycle cost $650 when acquired at the local cycling boutique.",
        answer_text="$650",
        answer_start_char=25,
        answer_end_char=29,
        is_answerable=True
    ),
    QAExample(
        id="pub-20-num",
        question="What was the price of the road bike?",
        context="The vintage road bike was priced at $450 in the auction catalog.",
        answer_text="$450",
        answer_start_char=36,
        answer_end_char=40,
        is_answerable=True
    ),
    QAExample(
        id="pub-21-num",
        question="How many characters does hiragana have?",
        context="The standard modern Japanese hiragana syllabary contains exactly 46 basic characters.",
        answer_text="46",
        answer_start_char=65,
        answer_end_char=67,
        is_answerable=True
    ),
    QAExample(
        id="pub-22-num",
        question="How many layers does the transformer have?",
        context="The base transformer encoder consists of 12 identical stacked attention layers.",
        answer_text="12",
        answer_start_char=42,
        answer_end_char=44,
        is_answerable=True
    ),
    # Dates & Times
    QAExample(
        id="pub-23-date",
        question="When was the laptop purchased?",
        context="I ordered my primary development laptop on 15 May 2023 from the official distributor.",
        answer_text="15 May 2023",
        answer_start_char=43,
        answer_end_char=54,
        is_answerable=True
    ),
    QAExample(
        id="pub-24-date",
        question="When was the phone acquired?",
        context="The refurbished mobile phone was bought on 22 August 2022 from an online store.",
        answer_text="22 August 2022",
        answer_start_char=43,
        answer_end_char=57,
        is_answerable=True
    ),
    QAExample(
        id="pub-25-date",
        question="When was the initial release published?",
        context="The first stable alpha build was released in October 2026 across open repositories.",
        answer_text="October 2026",
        answer_start_char=46,
        answer_end_char=58,
        is_answerable=True
    ),
    QAExample(
        id="pub-26-date",
        question="When was the concept first imagined?",
        context="The research architecture was imagined in 2023 as a personal experiment.",
        answer_text="2023",
        answer_start_char=42,
        answer_end_char=46,
        is_answerable=True
    ),
    # Multi-Fact Disambiguation in Same Passage
    QAExample(
        id="pub-27-mf1",
        question="When was the project imagined?",
        context="The search project was imagined in 2023. Real implementation commenced in October 2026.",
        answer_text="2023",
        answer_start_char=35,
        answer_end_char=39,
        is_answerable=True
    ),
    QAExample(
        id="pub-28-mf2",
        question="When did real implementation commence?",
        context="The search project was imagined in 2023. Real implementation commenced in October 2026.",
        answer_text="October 2026",
        answer_start_char=74,
        answer_end_char=86,
        is_answerable=True
    ),
    QAExample(
        id="pub-37-temporal-dream",
        question="When was the idea first dreamed?",
        context="The engineer dreamed of this system in 2023. However, the software was finalized in October 2026.",
        answer_text="2023",
        answer_start_char=39,
        answer_end_char=43,
        is_answerable=True
    ),
    QAExample(
        id="pub-38-temporal-finalize",
        question="When was the software finalized?",
        context="The engineer dreamed of this system in 2023. However, the software was finalized in October 2026.",
        answer_text="October 2026",
        answer_start_char=84,
        answer_end_char=96,
        is_answerable=True
    ),
    QAExample(
        id="pub-39-temporal-envision",
        question="When did they envision building the engine?",
        context="Was it a lifelong vision? Yes, the team envisioned creating the engine in 2023 before full construction began.",
        answer_text="2023",
        answer_start_char=74,
        answer_end_char=78,
        is_answerable=True
    ),
    QAExample(
        id="pub-40-temporal-dreamt",
        question="When did the creator dream of building it?",
        context="He dreamt of the concept in 2023 as a simple prototype. Later in October 2026, development escalated.",
        answer_text="2023",
        answer_start_char=28,
        answer_end_char=32,
        is_answerable=True
    ),
    # Paraphrased questions
    QAExample(
        id="pub-29-para",
        question="What was the main consideration when acquiring the bicycle?",
        context="When selecting my first bicycle, I prioritized durability over pure aerodynamic speed.",
        answer_text="durability over pure aerodynamic speed",
        answer_start_char=47,
        answer_end_char=85,
        is_answerable=True
    ),
    QAExample(
        id="pub-30-para",
        question="What mattered most when choosing the equipment?",
        context="In choosing our laboratory instruments, the engineers prioritized precision over cost savings.",
        answer_text="precision over cost savings",
        answer_start_char=66,
        answer_end_char=93,
        is_answerable=True
    ),
    # Entities / Names
    QAExample(
        id="pub-31-who",
        question="Who pioneered the field of algebra?",
        context="In classical mathematics, Al-Khwarizmi pioneered the foundational rules of algebra.",
        answer_text="Al-Khwarizmi",
        answer_start_char=26,
        answer_end_char=38,
        is_answerable=True
    ),
    QAExample(
        id="pub-32-who",
        question="Who formulated the laws of motion?",
        context="In the seventeenth century, Isaac Newton formulated the three universal laws of motion.",
        answer_text="Isaac Newton",
        answer_start_char=28,
        answer_end_char=40,
        is_answerable=True
    ),
    # Locations
    QAExample(
        id="pub-33-loc",
        question="Where was the House of Wisdom located?",
        context="The House of Wisdom was a celebrated academy located in Baghdad during the Golden Age.",
        answer_text="Baghdad",
        answer_start_char=56,
        answer_end_char=63,
        is_answerable=True
    ),
    QAExample(
        id="pub-34-loc",
        question="Which city is the capital of Japan?",
        context="Tokyo is the bustling capital of Japan and the political heart of the nation.",
        answer_text="Tokyo",
        answer_start_char=0,
        answer_end_char=5,
        is_answerable=True
    ),
    # Historical Eras & Siege
    QAExample(
        id="pub-35-hist",
        question="When did the classical era end?",
        context="The historical era flourished for centuries and came to an end in 1258 CE following the siege.",
        answer_text="1258 CE",
        answer_start_char=66,
        answer_end_char=73,
        is_answerable=True
    ),
    QAExample(
        id="pub-36-hist",
        question="When did the empire fall?",
        context="The empire flourished for four centuries and fell in 1453 CE after the historic siege.",
        answer_text="1453 CE",
        answer_start_char=53,
        answer_end_char=60,
        is_answerable=True
    ),
    # Topic-Overlapping Hard Negatives (Sacred Abstention)
    QAExample(
        id="pub-37-unans",
        question="What exact minute did the siege begin?",
        context="The historical era flourished for centuries and came to an end in 1258 CE following the siege.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
    QAExample(
        id="pub-38-unans",
        question="What color bicycle did Yasir buy?",
        context="The touring bicycle cost $650 when acquired at the local cycling boutique.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
    QAExample(
        id="pub-39-unans",
        question="Who was the prime minister of Mars?",
        context="Tokyo is the bustling capital of Japan and the political heart of the nation.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
    QAExample(
        id="pub-40-unans",
        question="What color shirt was the author wearing?",
        context="BM25F stands for Best Matching 25 with Fields, an extension of the Okapi BM25 ranking function.",
        answer_text=None,
        answer_start_char=None,
        answer_end_char=None,
        is_answerable=False,
        abstention_reason="NO EVIDENCE = NO ANSWER"
    ),
]
