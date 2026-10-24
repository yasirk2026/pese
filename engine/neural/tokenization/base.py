"""
PESE Neural Genesis: Base Tokenizer Interface
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any


class BaseTokenizer(ABC):
    """Abstract base class for PESE neural tokenizers."""

    def __init__(self):
        self.pad_token = "<pad>"
        self.unk_token = "<unk>"
        self.bos_token = "<bos>"
        self.eos_token = "<eos>"

        self.pad_token_id = 0
        self.unk_token_id = 1
        self.bos_token_id = 2
        self.eos_token_id = 3

    @property
    @abstractmethod
    def vocab_size(self) -> int:
        pass

    @abstractmethod
    def encode(self, text: str, add_special_tokens: bool = True) -> List[int]:
        pass

    @abstractmethod
    def decode(self, token_ids: List[int], skip_special_tokens: bool = True) -> str:
        pass

    def compute_compression_ratio(self, text: str) -> float:
        """Ratio of raw character length to number of tokens produced."""
        if not text:
            return 1.0
        tokens = self.encode(text, add_special_tokens=False)
        if not tokens:
            return 1.0
        return round(len(text) / len(tokens), 2)

    @abstractmethod
    def save(self, filepath: str) -> None:
        pass

    @classmethod
    @abstractmethod
    def load(cls, filepath: str) -> "BaseTokenizer":
        pass
