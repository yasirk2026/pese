"""
PESE Neural Genesis: Relation Classifier Architecture (PESE-Rel-0)
Phase N2: Bidirectional Cross-Encoder Transformer for Relational Support

Model contract:
Given [CLS] Question [SEP] Evidence [SEP], predict logits over:
  0: DOES_NOT_ANSWER
  1: ANSWERS
"""

import math
from typing import Optional, Tuple, Dict, Any, Union
import torch
import torch.nn as nn
import torch.nn.functional as F

from ..configs.model_config import RelationConfig
from .ffn import FeedForward


class RelationAttention(nn.Module):
    """
    Bidirectional Multi-Head Self-Attention for Relation Reasoning.
    Allows all tokens in Question and Evidence to attend to each other without causal masking.
    """

    def __init__(self, config: RelationConfig):
        super().__init__()
        self.d_model = config.d_model
        self.n_heads = config.n_heads
        self.head_dim = config.head_dim
        self.dropout = config.dropout

        self.q_proj = nn.Linear(self.d_model, self.d_model, bias=config.bias)
        self.k_proj = nn.Linear(self.d_model, self.d_model, bias=config.bias)
        self.v_proj = nn.Linear(self.d_model, self.d_model, bias=config.bias)
        self.out_proj = nn.Linear(self.d_model, self.d_model, bias=config.bias)

        self.attn_dropout = nn.Dropout(config.dropout)
        self.resid_dropout = nn.Dropout(config.dropout)

    def forward(
        self,
        x: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        x: (B, T, D)
        attention_mask: (B, T) with 1 for valid tokens, 0 for padding tokens
        """
        B, T, D = x.size()

        q = self.q_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)

        scale = 1.0 / math.sqrt(self.head_dim)
        scores = torch.matmul(q, k.transpose(-2, -1)) * scale  # (B, h, T, T)

        if attention_mask is not None:
            mask = attention_mask.unsqueeze(1).unsqueeze(2)  # (B, 1, 1, T)
            scores = scores.masked_fill(mask == 0, -10000.0)

        weights = torch.softmax(scores, dim=-1)
        weights = self.attn_dropout(weights)

        context = torch.matmul(weights, v)  # (B, h, T, head_dim)
        context = context.transpose(1, 2).contiguous().view(B, T, D)

        out = self.out_proj(context)
        return self.resid_dropout(out)


class RelationEncoderBlock(nn.Module):
    """
    Pre-LayerNorm Bidirectional Transformer Block.
    """

    def __init__(self, config: RelationConfig):
        super().__init__()
        self.ln1 = nn.LayerNorm(config.d_model, eps=1e-5)
        self.attn = RelationAttention(config)
        self.ln2 = nn.LayerNorm(config.d_model, eps=1e-5)
        self.ffn = FeedForward(config)

    def forward(
        self,
        x: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        x = x + self.attn(self.ln1(x), attention_mask=attention_mask)
        x = x + self.ffn(self.ln2(x))
        return x


class PESERelationClassifier(nn.Module):
    """
    PESE-Rel-0 Cross-Encoder Classifier.
    Predicts whether evidence supports / answers a question.
    """

    def __init__(self, config: RelationConfig):
        super().__init__()
        self.config = config

        self.tok_embeddings = nn.Embedding(config.vocab_size, config.d_model)
        self.pos_embeddings = nn.Embedding(config.max_seq_len, config.d_model)
        self.use_segments = config.type_vocab_size > 0
        if self.use_segments:
            self.seg_embeddings = nn.Embedding(config.type_vocab_size, config.d_model)

        self.drop = nn.Dropout(config.dropout)

        self.blocks = nn.ModuleList([
            RelationEncoderBlock(config) for _ in range(config.n_layers)
        ])

        self.ln_f = nn.LayerNorm(config.d_model, eps=1e-5)

        # Pooled classification head on [CLS] position
        self.classifier = nn.Sequential(
            nn.Linear(config.d_model, config.d_model, bias=config.bias),
            nn.Tanh(),
            nn.Dropout(config.dropout),
            nn.Linear(config.d_model, config.num_classes, bias=config.bias)
        )

        self.apply(self._init_weights)

    def _init_weights(self, module: nn.Module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=self.config.initializer_range)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=self.config.initializer_range)
        elif isinstance(module, nn.LayerNorm):
            torch.nn.init.ones_(module.weight)
            torch.nn.init.zeros_(module.bias)

    def forward(
        self,
        input_ids: torch.Tensor,
        token_type_ids: Optional[torch.Tensor] = None,
        attention_mask: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Args:
            input_ids: (B, T)
            token_type_ids: (B, T) 0 for question, 1 for evidence
            attention_mask: (B, T) 1 for real tokens, 0 for padding
            labels: (B,) 0 for DOES_NOT_ANSWER, 1 for ANSWERS
        Returns:
            logits (B, 2) or (loss, logits) if labels provided
        """
        B, T = input_ids.size()
        device = input_ids.device

        positions = torch.arange(0, T, dtype=torch.long, device=device).unsqueeze(0)

        x = self.tok_embeddings(input_ids) + self.pos_embeddings(positions)
        if self.use_segments:
            if token_type_ids is None:
                token_type_ids = torch.zeros_like(input_ids)
            x = x + self.seg_embeddings(token_type_ids)

        x = self.drop(x)

        for block in self.blocks:
            x = block(x, attention_mask=attention_mask)

        x = self.ln_f(x)

        # Extract pooled [CLS] token at position 0
        cls_rep = x[:, 0, :]
        logits = self.classifier(cls_rep)

        if labels is not None:
            loss = F.cross_entropy(logits, labels)
            return loss, logits

        return logits
