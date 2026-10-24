"""
PESE Neural Genesis: Byte Pair Encoding (BPE) Tokenizer
Deterministic subword tokenizer (PESE-BPE-0) trained from scratch.
"""

import json
import re
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict, Counter
from .base import BaseTokenizer


class BPETokenizer(BaseTokenizer):
    """
    Trainable Byte Pair Encoding tokenizer for PESE Neural Genesis.
    Learns statistical subword merges to balance vocabulary coverage with sequence compression.
    """

    def __init__(
        self,
        vocab: Optional[Dict[str, int]] = None,
        merges: Optional[List[Tuple[str, str]]] = None,
    ):
        super().__init__()
        self.merges: List[Tuple[str, str]] = merges or []
        self.bpe_ranks: Dict[Tuple[str, str], int] = {
            m: idx for idx, m in enumerate(self.merges)
        }

        if vocab is not None:
            self.vocab = vocab
            self.inverse_vocab = {idx: tok for tok, idx in self.vocab.items()}
        else:
            special = [self.pad_token, self.unk_token, self.bos_token, self.eos_token]
            self.vocab = {tok: idx for idx, tok in enumerate(special)}
            self.inverse_vocab = {idx: tok for idx, tok in enumerate(special)}

    @property
    def vocab_size(self) -> int:
        return len(self.vocab)

    def train(self, texts: List[str], target_vocab_size: int = 512, min_frequency: int = 2) -> None:
        """
        Train BPE merge rules on an unsegmented text corpus until target_vocab_size is reached.
        """
        # 1. Initialize base vocabulary with special tokens and all unique characters
        special = [self.pad_token, self.unk_token, self.bos_token, self.eos_token]
        char_set: Set[str] = set()
        for t in texts:
            char_set.update(list(t))

        vocab_list = special + sorted(list(char_set))
        self.vocab = {tok: idx for idx, tok in enumerate(vocab_list)}
        self.inverse_vocab = {idx: tok for idx, tok in enumerate(vocab_list)}
        self.merges = []

        # 2. Tokenize corpus into words, represented as space-separated characters with end-of-word marker </w>
        word_freqs: Dict[Tuple[str, ...], int] = Counter()
        for text in texts:
            # Simple whitespace tokenization with punctuation isolation
            words = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
            for w in words:
                symbols = tuple(list(w) + ["</w>"])
                word_freqs[symbols] += 1

        # Also add </w> to initial vocabulary if not present
        if "</w>" not in self.vocab:
            new_id = len(self.vocab)
            self.vocab["</w>"] = new_id
            self.inverse_vocab[new_id] = "</w>"

        # 3. Iteratively find most frequent adjacent pairs and merge
        num_merges = max(0, target_vocab_size - len(self.vocab))

        for step in range(num_merges):
            pair_counts: Dict[Tuple[str, str], int] = defaultdict(int)
            for word_tuple, freq in word_freqs.items():
                for i in range(len(word_tuple) - 1):
                    pair_counts[(word_tuple[i], word_tuple[i + 1])] += freq

            if not pair_counts:
                break

            best_pair, best_freq = max(pair_counts.items(), key=lambda x: x[1])
            if best_freq < min_frequency:
                break

            # Register new merge rule
            self.merges.append(best_pair)
            merged_token = "".join(best_pair)
            new_id = len(self.vocab)
            self.vocab[merged_token] = new_id
            self.inverse_vocab[new_id] = merged_token

            # Update word frequencies with merged pair
            new_word_freqs: Dict[Tuple[str, ...], int] = {}
            p1, p2 = best_pair

            for word_tuple, freq in word_freqs.items():
                new_tuple = []
                i = 0
                while i < len(word_tuple):
                    if i < len(word_tuple) - 1 and word_tuple[i] == p1 and word_tuple[i + 1] == p2:
                        new_tuple.append(merged_token)
                        i += 2
                    else:
                        new_tuple.append(word_tuple[i])
                        i += 1
                new_word_freqs[tuple(new_tuple)] = freq

            word_freqs = new_word_freqs

        self.bpe_ranks = {m: idx for idx, m in enumerate(self.merges)}

    def _bpe(self, word: str) -> List[str]:
        """Apply learned BPE merge rules to a single word."""
        symbols = list(word) + ["</w>"]
        if len(symbols) <= 1:
            return symbols

        while True:
            # Find all possible pairs
            pairs = [(symbols[i], symbols[i + 1]) for i in range(len(symbols) - 1)]
            # Find the pair with minimum rank in bpe_ranks
            min_rank_pair = None
            min_rank = float("inf")

            for p in pairs:
                rank = self.bpe_ranks.get(p)
                if rank is not None and rank < min_rank:
                    min_rank = rank
                    min_rank_pair = p

            if min_rank_pair is None:
                break

            p1, p2 = min_rank_pair
            new_symbols = []
            i = 0
            while i < len(symbols):
                if i < len(symbols) - 1 and symbols[i] == p1 and symbols[i + 1] == p2:
                    new_symbols.append(p1 + p2)
                    i += 2
                else:
                    new_symbols.append(symbols[i])
                    i += 1

            symbols = new_symbols
            if len(symbols) == 1:
                break

        return symbols

    def encode(self, text: str, add_special_tokens: bool = True) -> List[int]:
        """Encode arbitrary text into token IDs."""
        tokens = []
        if add_special_tokens:
            tokens.append(self.bos_token_id)

        # Break text into words/tokens
        words = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
        for w in words:
            bpe_tokens = self._bpe(w)
            for t in bpe_tokens:
                tokens.append(self.vocab.get(t, self.unk_token_id))

        if add_special_tokens:
            tokens.append(self.eos_token_id)

        return tokens

    def decode(self, token_ids: List[int], skip_special_tokens: bool = True) -> str:
        """Decode token IDs back into text."""
        special_ids = {self.pad_token_id, self.unk_token_id, self.bos_token_id, self.eos_token_id}
        parts = []
        for tid in token_ids:
            if skip_special_tokens and tid in special_ids:
                continue
            tok = self.inverse_vocab.get(tid, "")
            parts.append(tok)

        text = "".join(parts).replace("</w>", " ")
        # Clean double spaces
        return re.sub(r"\s+", " ", text).strip()

    def save(self, filepath: str) -> None:
        data = {
            "type": "BPETokenizer",
            "vocab": self.vocab,
            "merges": self.merges,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "BPETokenizer":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        merges = [tuple(m) for m in data["merges"]]
        return cls(vocab=data["vocab"], merges=merges)
