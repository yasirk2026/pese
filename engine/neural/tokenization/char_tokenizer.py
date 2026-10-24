"""
PESE Neural Genesis: Character Tokenizer
Deterministic baseline character-level tokenizer for initial sanity tests and micro-overfit.
"""

import json
from typing import List, Dict, Optional
from .base import BaseTokenizer


class CharTokenizer(BaseTokenizer):
    """Character-level tokenizer for baseline neural sanity and micro-overfit tests."""

    def __init__(self, vocab: Optional[Dict[str, int]] = None):
        super().__init__()
        if vocab is not None:
            self.char2idx = vocab
            self.idx2char = {idx: ch for ch, idx in self.char2idx.items()}
        else:
            # Default fallback printable vocabulary
            special = [self.pad_token, self.unk_token, self.bos_token, self.eos_token]
            chars = sorted(list(set(" abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,!?:;-_'\"/\\#$@%^&*()+=[]{}<>~\n\t")))
            all_tokens = special + chars
            self.char2idx = {ch: i for i, ch in enumerate(all_tokens)}
            self.idx2char = {i: ch for i, ch in enumerate(all_tokens)}

    @property
    def vocab_size(self) -> int:
        return len(self.char2idx)

    def train(self, texts: List[str]) -> None:
        """Alias for train_from_texts."""
        self.train_from_texts(texts)

    def train_from_texts(self, texts: List[str]) -> None:
        """Derive character vocabulary from training corpus."""
        special = [self.pad_token, self.unk_token, self.bos_token, self.eos_token]
        unique_chars = sorted(list(set("".join(texts))))
        all_tokens = special + [c for c in unique_chars if c not in special]
        self.char2idx = {ch: i for i, ch in enumerate(all_tokens)}
        self.idx2char = {i: ch for i, ch in enumerate(all_tokens)}

    def encode(self, text: str, add_special_tokens: bool = True) -> List[int]:
        ids = []
        if add_special_tokens:
            ids.append(self.bos_token_id)

        for ch in text:
            ids.append(self.char2idx.get(ch, self.unk_token_id))

        if add_special_tokens:
            ids.append(self.eos_token_id)

        return ids

    def decode(self, token_ids: List[int], skip_special_tokens: bool = True) -> str:
        special_ids = {self.pad_token_id, self.unk_token_id, self.bos_token_id, self.eos_token_id}
        chars = []
        for tid in token_ids:
            if skip_special_tokens and tid in special_ids:
                continue
            chars.append(self.idx2char.get(tid, ""))
        return "".join(chars)

    def save(self, filepath: str) -> None:
        data = {
            "type": "CharTokenizer",
            "vocab": self.char2idx,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "CharTokenizer":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(vocab=data["vocab"])
