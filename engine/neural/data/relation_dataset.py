"""
PESE Neural Genesis: Relation Reasoning Dataset Loader
Phase N2: PyTorch Dataset & Batching for PESE-Rel-0
"""

from typing import List, Dict, Any, Tuple
import torch
from torch.utils.data import Dataset

from .relation_contracts import RelationExample, RelationLabel
from ..tokenization.relation_tokenizer import RelationTokenizer


class RelationDataset(Dataset):
    """
    PyTorch Dataset mapping RelationExample instances to tokenized tensor representations.
    """

    def __init__(
        self,
        examples: List[RelationExample],
        tokenizer: RelationTokenizer,
        max_seq_len: int = 128
    ):
        self.examples = examples
        self.tokenizer = tokenizer
        self.max_seq_len = max_seq_len

        # Pre-tokenize all examples into tensors for fast CPU iteration
        self.input_ids = []
        self.token_type_ids = []
        self.attention_masks = []
        self.labels = []
        self.example_ids = []

        for ex in examples:
            feat = tokenizer.build_cross_encoder_inputs(
                question=ex.question,
                evidence=ex.evidence,
                max_seq_len=max_seq_len
            )
            lbl = 1 if ex.label == RelationLabel.ANSWERS else 0

            self.input_ids.append(torch.tensor(feat["input_ids"], dtype=torch.long))
            self.token_type_ids.append(torch.tensor(feat["token_type_ids"], dtype=torch.long))
            self.attention_masks.append(torch.tensor(feat["attention_mask"], dtype=torch.long))
            self.labels.append(lbl)
            self.example_ids.append(ex.id)

        self.input_ids = torch.stack(self.input_ids)
        self.token_type_ids = torch.stack(self.token_type_ids)
        self.attention_masks = torch.stack(self.attention_masks)
        self.labels = torch.tensor(self.labels, dtype=torch.long)

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, str]:
        return (
            self.input_ids[idx],
            self.token_type_ids[idx],
            self.attention_masks[idx],
            self.labels[idx],
            self.example_ids[idx]
        )
