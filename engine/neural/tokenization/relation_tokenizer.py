"""
PESE Neural Genesis: Relation Reasoning Tokenizer (PESE-REL-BPE-0)
Phase N2: Dedicated Subword Tokenizer for Relation Classification

Trained strictly on the TRAIN SPLIT of PESE-REL-DATA-0.
Produces [CLS] Question [SEP] Evidence [SEP] sequences with segment IDs.
Zero access to validation or test splits during vocabulary construction.
"""

import json
import re
import hashlib
from typing import List, Dict, Tuple, Optional, Set, Any
from collections import defaultdict, Counter

from .base import BaseTokenizer


class RelationTokenizer(BaseTokenizer):
    """
    Trainable Byte Pair Encoding tokenizer with explicit sequence formatting
    for cross-encoder classification:
      [CLS] question [SEP] evidence [SEP]
    """

    def __init__(
        self,
        vocab: Optional[Dict[str, int]] = None,
        merges: Optional[List[Tuple[str, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        self.pad_token = "<pad>"
        self.unk_token = "<unk>"
        self.cls_token = "[CLS]"
        self.sep_token = "[SEP]"

        self.merges: List[Tuple[str, str]] = merges or []
        self.bpe_ranks: Dict[Tuple[str, str], int] = {
            m: idx for idx, m in enumerate(self.merges)
        }
        self.metadata: Dict[str, Any] = metadata or {}

        if vocab is not None:
            self.vocab = vocab
            self.inverse_vocab = {idx: tok for tok, idx in self.vocab.items()}
        else:
            special = [self.pad_token, self.unk_token, self.cls_token, self.sep_token]
            self.vocab = {tok: idx for idx, tok in enumerate(special)}
            self.inverse_vocab = {idx: tok for idx, tok in enumerate(special)}

        self.pad_token_id = self.vocab.get(self.pad_token, 0)
        self.unk_token_id = self.vocab.get(self.unk_token, 1)
        self.cls_token_id = self.vocab.get(self.cls_token, 2)
        self.sep_token_id = self.vocab.get(self.sep_token, 3)

    @property
    def vocab_size(self) -> int:
        return len(self.vocab)

    def train_on_split(
        self,
        train_examples: List[Any],
        target_vocab_size: int = 512,
        min_frequency: int = 2,
        split_hash: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Trains BPE merge rules ONLY on the train split texts.
        """
        train_texts = [ex.question + " " + ex.evidence for ex in train_examples]
        special = [self.pad_token, self.unk_token, self.cls_token, self.sep_token]

        # Collect unique characters across train split
        char_set: Set[str] = set()
        for t in train_texts:
            char_set.update(list(t))

        vocab_list = special + sorted(list(char_set))
        self.vocab = {tok: idx for idx, tok in enumerate(vocab_list)}
        self.inverse_vocab = {idx: tok for idx, tok in enumerate(vocab_list)}
        self.merges = []

        word_freqs: Dict[Tuple[str, ...], int] = Counter()
        for text in train_texts:
            words = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
            for w in words:
                symbols = tuple(list(w) + ["</w>"])
                word_freqs[symbols] += 1

        if "</w>" not in self.vocab:
            new_id = len(self.vocab)
            self.vocab["</w>"] = new_id
            self.inverse_vocab[new_id] = "</w>"

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

            self.merges.append(best_pair)
            merged_token = "".join(best_pair)
            new_id = len(self.vocab)
            self.vocab[merged_token] = new_id
            self.inverse_vocab[new_id] = merged_token

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

        # Update IDs
        self.pad_token_id = self.vocab[self.pad_token]
        self.unk_token_id = self.vocab[self.unk_token]
        self.cls_token_id = self.vocab[self.cls_token]
        self.sep_token_id = self.vocab[self.sep_token]

        # Compute vocabulary hash for provenance
        sorted_vocab = sorted(self.vocab.items(), key=lambda x: x[1])
        vocab_str = "|".join(f"{k}:{v}" for k, v in sorted_vocab)
        vocab_hash = hashlib.sha256(vocab_str.encode("utf-8")).hexdigest()

        self.metadata = {
            "tokenizer_name": "PESE-REL-BPE-0",
            "vocab_size": len(self.vocab),
            "target_vocab_size": target_vocab_size,
            "min_frequency": min_frequency,
            "training_split_hash": split_hash or "unspecified",
            "vocab_sha256": vocab_hash,
            "special_tokens": {
                "[CLS]": self.cls_token_id,
                "[SEP]": self.sep_token_id,
                "<pad>": self.pad_token_id,
                "<unk>": self.unk_token_id,
            }
        }
        return self.metadata

    def _bpe(self, word: str) -> List[str]:
        symbols = list(word) + ["</w>"]
        if len(symbols) <= 1:
            return symbols

        while True:
            pairs = [(symbols[i], symbols[i + 1]) for i in range(len(symbols) - 1)]
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

    def encode(self, text: str, add_special_tokens: bool = False) -> List[int]:
        tokens = []
        if add_special_tokens:
            tokens.append(self.cls_token_id)

        words = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
        for w in words:
            bpe_tokens = self._bpe(w)
            for t in bpe_tokens:
                tokens.append(self.vocab.get(t, self.unk_token_id))

        if add_special_tokens:
            tokens.append(self.sep_token_id)

        return tokens

    def decode(self, token_ids: List[int], skip_special_tokens: bool = True) -> str:
        special_ids = {self.pad_token_id, self.unk_token_id, self.cls_token_id, self.sep_token_id}
        parts = []
        for tid in token_ids:
            if skip_special_tokens and tid in special_ids:
                continue
            tok = self.inverse_vocab.get(tid, "")
            parts.append(tok)

        text = "".join(parts).replace("</w>", " ")
        return re.sub(r"\s+", " ", text).strip()

    def build_cross_encoder_inputs(
        self,
        question: str,
        evidence: str,
        max_seq_len: int = 128
    ) -> Dict[str, List[int]]:
        """
        Builds model feature tensors for cross-encoder inference:
        Sequence: [CLS] question [SEP] evidence [SEP] [PAD]...
        Segments:   0      0...0     0      1...1     1     0...0
        Mask:       1      1...1     1      1...1     1     0...0
        """
        q_tokens = self.encode(question, add_special_tokens=False)
        e_tokens = self.encode(evidence, add_special_tokens=False)

        # Budget: 3 special tokens: [CLS], [SEP], [SEP]
        max_content = max_seq_len - 3
        if len(q_tokens) + len(e_tokens) > max_content:
            # Keep question complete if possible, truncate evidence
            max_q = min(len(q_tokens), 40)
            q_tokens = q_tokens[:max_q]
            max_e = max_content - len(q_tokens)
            e_tokens = e_tokens[:max_e]

        # Sequence construction
        input_ids = [self.cls_token_id] + q_tokens + [self.sep_token_id] + e_tokens + [self.sep_token_id]
        token_type_ids = [0] * (len(q_tokens) + 2) + [1] * (len(e_tokens) + 1)
        attention_mask = [1] * len(input_ids)

        # Padding
        pad_len = max_seq_len - len(input_ids)
        if pad_len > 0:
            input_ids.extend([self.pad_token_id] * pad_len)
            token_type_ids.extend([0] * pad_len)
            attention_mask.extend([0] * pad_len)

        return {
            "input_ids": input_ids,
            "token_type_ids": token_type_ids,
            "attention_mask": attention_mask
        }

    def audit_splits(self, splits: Dict[str, List[Any]], max_seq_len: int = 128) -> Dict[str, Any]:
        """
        Audits vocabulary coverage, unknown token counts, and truncation across splits.
        """
        report = {}
        for split_name, examples in splits.items():
            total_tokens = 0
            unk_tokens = 0
            truncated_count = 0
            total_seqs = len(examples)

            for ex in examples:
                q_toks = self.encode(ex.question, add_special_tokens=False)
                e_toks = self.encode(ex.evidence, add_special_tokens=False)
                seq_len = len(q_toks) + len(e_toks) + 3

                if seq_len > max_seq_len:
                    truncated_count += 1

                for t in q_toks + e_toks:
                    total_tokens += 1
                    if t == self.unk_token_id:
                        unk_tokens += 1

            unk_rate = unk_tokens / total_tokens if total_tokens > 0 else 0.0
            trunc_rate = truncated_count / total_seqs if total_seqs > 0 else 0.0

            report[split_name] = {
                "example_count": total_seqs,
                "total_tokens": total_tokens,
                "unk_tokens": unk_tokens,
                "unk_rate": round(unk_rate, 6),
                "coverage_pct": round((1.0 - unk_rate) * 100.0, 3),
                "truncated_sequences": truncated_count,
                "truncation_rate": round(trunc_rate, 4)
            }
        return report

    def save(self, filepath: str) -> None:
        data = {
            "type": "RelationTokenizer",
            "vocab": self.vocab,
            "merges": self.merges,
            "metadata": self.metadata,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "RelationTokenizer":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        merges = [tuple(m) for m in data["merges"]]
        return cls(
            vocab=data["vocab"],
            merges=merges,
            metadata=data.get("metadata", {})
        )
