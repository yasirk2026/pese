"""
PESE Neural Genesis: Synthetic Public Datasets & Data Loaders
Strictly decoupled from private user documents and search query logs.
Provides deterministic micro-overfit fixtures and synthetic technical corpora.
"""

from typing import List, Dict, Optional, Tuple
import torch
from torch.utils.data import Dataset, DataLoader

from ..tokenization.base import BaseTokenizer


# ---------------------------------------------------------------------------
# Micro-Overfit Dataset (Deterministic Fixture)
# ---------------------------------------------------------------------------
MICRO_OVERFIT_TEXTS = [
    "Personal Evil Search Engine uses BM25F lexical scoring and dense vectors.",
    "Neural Genesis explores Transformer architectures in PyTorch without external APIs.",
    "Causal attention ensures tokens only attend to past and present positions.",
    "Extractive question answering locates exact token spans inside documents.",
    "Pre-LayerNorm architectures provide superior gradient stability during training.",
    "When no evidence is found in the corpus, the engine must abstain from answering.",
    "Reciprocal Rank Fusion merges ranked retrieval lists with zero score calibration.",
    "Byte Pair Encoding merges frequent byte pairs to build subword vocabularies."
]

# ---------------------------------------------------------------------------
# Synthetic Public Technical Corpus (Clean, General CS Knowledge)
# ---------------------------------------------------------------------------
SYNTHETIC_PUBLIC_CORPUS = [
    # Information Retrieval
    "Information retrieval systems index documents to fulfill user information needs.",
    "BM25F scores multi-field documents by weighting title headings and body terms differently.",
    "Inverse document frequency penalizes terms that appear across almost all documents.",
    "Term frequency measures the repetition of a query term within a single field or document.",
    "Passage retrieval breaks lengthy documents into contiguous semantic chunks for scoring.",
    "Lexical search relies on exact token matches and inverted index postings.",
    "Dense retrieval maps queries and passages into a shared geometric vector space.",
    "Cosine similarity computes the normalized dot product between two vector embeddings.",
    "Hybrid search combines lexical keyword relevance with dense semantic representation.",
    "Reciprocal Rank Fusion aggregates rankings without needing calibrated score magnitudes.",
    "Search engine evaluation relies on Mean Reciprocal Rank and Normalized Discounted Cumulative Gain.",
    "Minimum Evidence Gating prevents speculative answers when passage support is insufficient.",
    "Spam defenses detect keyword stuffing and unnatural link manipulation patterns.",
    "Query suggestions expand partial user prefixes using corpus statistics and frequent terms.",
    "Related searches identify adjacent conceptual queries based on co-occurrence graph walks.",

    # Transformer & Deep Learning
    "Transformer decoders use causal masking to model autoregressive sequence probabilities.",
    "Multi-head attention projects queries, keys, and values into multiple subspace heads.",
    "The scaled dot-product attention divides dot products by the square root of key dimension.",
    "Softmax transforms unnormalized logits into a valid probability distribution summing to one.",
    "Feed-forward networks apply two linear projections with a non-linear activation in between.",
    "GELU activation offers smooth non-linearity approximated through standard error functions.",
    "Layer normalization normalizes activations across feature dimensions per sequence token.",
    "Pre-LayerNorm architectures place normalization before attention and feed-forward sublayers.",
    "Residual connections allow gradient signals to flow directly through deep network layers.",
    "Cross-entropy loss measures the divergence between predicted token logits and true targets.",
    "AdamW optimizer applies weight decay directly to model parameters decoupling it from gradients.",
    "Gradient clipping scales gradient vectors whose Euclidean norm exceeds a fixed threshold.",
    "Subword tokenization compresses text sequences while keeping out-of-vocabulary rates minimal.",
    "Byte Pair Encoding iteratively merges the most frequent pairs of adjacent tokens.",
    "Positional embeddings supply token sequence order information to permutation-invariant attention.",
    
    # Systems & Computing
    "Binary search trees maintain sorted order allowing logarithmic time search and insertion.",
    "Hash tables compute bucket indices using deterministic hash functions for constant-time lookup.",
    "Operating systems schedule threads using preemptive priorities and context switches.",
    "Virtual memory maps logical process addresses to physical RAM pages through page tables.",
    "Garbage collectors trace reachable object graphs to reclaim unused heap memory blocks.",
    "Asynchronous IO handles multiple concurrent sockets without dedicating a OS thread to each.",
    "Relational databases enforce ACID guarantees using write-ahead logs and locks.",
    "Inverted indexes map token identifiers to postings lists containing document IDs and offsets."
]


class CausalLMDataset(Dataset):
    """
    PyTorch Dataset for causal language modeling.
    Pre-tokenizes text sequences into (input_ids, targets) pairs where
    targets are input_ids shifted by one position.
    """

    def __init__(
        self,
        texts: List[str],
        tokenizer: BaseTokenizer,
        max_seq_len: int = 128
    ):
        self.tokenizer = tokenizer
        self.max_seq_len = max_seq_len
        self.samples: List[Tuple[torch.Tensor, torch.Tensor]] = []

        pad_id = tokenizer.pad_token_id

        for text in texts:
            tokens = tokenizer.encode(text)
            if len(tokens) < 2:
                continue

            # Truncate to max_seq_len + 1 (for input and shifted target)
            tokens = tokens[: max_seq_len + 1]

            # Input: tokens[:-1], Target: tokens[1:]
            input_tokens = tokens[:-1]
            target_tokens = tokens[1:]

            # Pad to max_seq_len
            pad_len = max_seq_len - len(input_tokens)
            if pad_len > 0:
                input_tokens = input_tokens + [pad_id] * pad_len
                # For loss computation, pad positions in targets get -100 so CrossEntropy ignores them
                target_tokens = target_tokens + [-100] * pad_len

            self.samples.append((
                torch.tensor(input_tokens, dtype=torch.long),
                torch.tensor(target_tokens, dtype=torch.long)
            ))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        input_ids, targets = self.samples[idx]
        return {
            "input_ids": input_ids,
            "targets": targets
        }


def create_dataloader(
    dataset: Dataset,
    batch_size: int = 4,
    shuffle: bool = True
) -> DataLoader:
    """Helper to construct deterministic PyTorch DataLoader."""
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        drop_last=False
    )
