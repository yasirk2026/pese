"""
PESE Neural Genesis: Data Subsystem
"""

from .contracts import (
    QAExample,
    RerankerPair,
    find_answer_span,
    export_faqs_to_qa_contracts
)
from .dataset import (
    MICRO_OVERFIT_TEXTS,
    SYNTHETIC_PUBLIC_CORPUS,
    CausalLMDataset,
    create_dataloader
)
from .qa_dataset import (
    QAInputFeature,
    build_qa_features,
    ExtractiveQADataset,
    tokenize_with_char_offsets,
    STAGE_A_SANITY_EXAMPLES,
    STAGE_B_MICRO_OVERFIT_EXAMPLES,
    STAGE_C_PUBLIC_QA_CORPUS
)

__all__ = [
    "QAExample",
    "RerankerPair",
    "find_answer_span",
    "export_faqs_to_qa_contracts",
    "MICRO_OVERFIT_TEXTS",
    "SYNTHETIC_PUBLIC_CORPUS",
    "CausalLMDataset",
    "create_dataloader",
    "QAInputFeature",
    "build_qa_features",
    "ExtractiveQADataset",
    "tokenize_with_char_offsets",
    "STAGE_A_SANITY_EXAMPLES",
    "STAGE_B_MICRO_OVERFIT_EXAMPLES",
    "STAGE_C_PUBLIC_QA_CORPUS",
]
