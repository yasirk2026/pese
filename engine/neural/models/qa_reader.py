"""
PESE-QA-0: Neural Reading Comprehension & Exact Answer Extraction
Bidirectional Transformer Reader with span extraction and answerability classification.
"""

import math
from typing import Optional, Tuple, Dict, Any
import torch
import torch.nn as nn
import torch.nn.functional as F

from ..configs.model_config import QAConfig
from .ffn import FeedForward


class BidirectionalAttention(nn.Module):
    """
    Bidirectional Multi-Head Self-Attention for Reading Comprehension.
    Allows all tokens in Question and Passage to attend to each other without causal masking.
    """

    def __init__(self, config: QAConfig):
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
        attention_mask: (B, T) with 1 for valid tokens, 0 for pad tokens
        """
        B, T, D = x.size()

        # Project Q, K, V
        q = self.q_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)

        # Scaled dot-product attention
        scale = 1.0 / math.sqrt(self.head_dim)
        scores = torch.matmul(q, k.transpose(-2, -1)) * scale  # (B, h, T, T)

        # Apply padding mask if provided
        if attention_mask is not None:
            # Expand mask to (B, 1, 1, T)
            mask = attention_mask.unsqueeze(1).unsqueeze(2)
            scores = scores.masked_fill(mask == 0, -10000.0)

        weights = torch.softmax(scores, dim=-1)
        weights = self.attn_dropout(weights)

        context = torch.matmul(weights, v)  # (B, h, T, head_dim)
        context = context.transpose(1, 2).contiguous().view(B, T, D)

        out = self.out_proj(context)
        return self.resid_dropout(out)


class QAEncoderBlock(nn.Module):
    """
    Pre-LayerNorm Bidirectional Transformer Block.
    """

    def __init__(self, config: QAConfig):
        super().__init__()
        self.ln1 = nn.LayerNorm(config.d_model, eps=1e-5)
        self.attn = BidirectionalAttention(config)
        self.ln2 = nn.LayerNorm(config.d_model, eps=1e-5)
        self.ffn = FeedForward(config)  # Reuses existing FeedForward module with GELU

    def forward(
        self,
        x: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        x = x + self.attn(self.ln1(x), attention_mask=attention_mask)
        x = x + self.ffn(self.ln2(x))
        return x


class PESEQAReader(nn.Module):
    """
    PESE-QA-0: Neural Reading Comprehension & Answer Span Extractor.
    Takes [CLS] Question [SEP] Passage [SEP] and predicts:
      1. Start token logits across sequence
      2. End token logits across sequence
      3. Binary answerability classification (Answerable vs Abstain)
    """

    def __init__(self, config: QAConfig):
        super().__init__()
        self.config = config

        # Embeddings
        self.tok_embeddings = nn.Embedding(config.vocab_size, config.d_model)
        self.pos_embeddings = nn.Embedding(config.max_seq_len, config.d_model)
        self.seg_embeddings = nn.Embedding(config.type_vocab_size, config.d_model)
        self.drop = nn.Dropout(config.dropout)

        # Bidirectional Transformer Encoder Layers
        self.blocks = nn.ModuleList([
            QAEncoderBlock(config) for _ in range(config.n_layers)
        ])

        # Final Layer Normalization
        self.ln_f = nn.LayerNorm(config.d_model, eps=1e-5)

        # Span Prediction Head: Linear(D -> 2) for Start and End logits
        self.qa_outputs = nn.Linear(config.d_model, 2, bias=config.bias)

        # Answerability Head: Pooled [CLS] projection -> [unanswerable, answerable]
        self.answerability_head = nn.Sequential(
            nn.Linear(config.d_model, config.d_model, bias=config.bias),
            nn.Tanh(),
            nn.Dropout(config.dropout),
            nn.Linear(config.d_model, 2, bias=config.bias)
        )

        # Weight initialization
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
        start_positions: Optional[torch.Tensor] = None,
        end_positions: Optional[torch.Tensor] = None,
        is_answerable: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Optional[torch.Tensor]]:
        """
        Args:
            input_ids: (B, T) token indices
            token_type_ids: (B, T) 0 for question tokens, 1 for passage tokens
            attention_mask: (B, T) 1 for valid tokens, 0 for padding tokens
            start_positions: (B,) ground truth start token index (0 if unanswerable)
            end_positions: (B,) ground truth end token index (0 if unanswerable)
            is_answerable: (B,) 1 if answerable, 0 if unanswerable

        Returns:
            Tuple of (start_logits, end_logits, ans_logits, total_loss)
        """
        device = input_ids.device
        B, T = input_ids.size()
        if T > self.config.max_seq_len:
            raise ValueError(f"Sequence length {T} exceeds max_seq_len {self.config.max_seq_len}")

        # Position and segment vectors
        pos = torch.arange(0, T, dtype=torch.long, device=device).unsqueeze(0)  # (1, T)
        if token_type_ids is None:
            token_type_ids = torch.zeros_like(input_ids, dtype=torch.long)

        # Construct combined embeddings
        tok_emb = self.tok_embeddings(input_ids)
        pos_emb = self.pos_embeddings(pos)
        seg_emb = self.seg_embeddings(token_type_ids)
        x = self.drop(tok_emb + pos_emb + seg_emb)

        # Pass through bidirectional encoder blocks
        for block in self.blocks:
            x = block(x, attention_mask=attention_mask)

        # Final LayerNorm
        h = self.ln_f(x)  # (B, T, D)

        # Span logits
        logits = self.qa_outputs(h)  # (B, T, 2)
        start_logits = logits[:, :, 0]  # (B, T)
        end_logits = logits[:, :, 1]    # (B, T)

        # Mask padding tokens in logits to very large negative values
        if attention_mask is not None:
            start_logits = start_logits.masked_fill(attention_mask == 0, -10000.0)
            end_logits = end_logits.masked_fill(attention_mask == 0, -10000.0)

        # Pooled representation from position 0 ([CLS])
        pooled = h[:, 0, :]  # (B, D)
        ans_logits = self.answerability_head(pooled)  # (B, 2)

        total_loss = None
        if start_positions is not None and end_positions is not None:
            # Ensure positions do not exceed sequence length
            ignored_index = start_logits.size(1)
            start_positions = start_positions.clamp(0, ignored_index - 1)
            end_positions = end_positions.clamp(0, ignored_index - 1)

            loss_fct = nn.CrossEntropyLoss()
            start_loss = loss_fct(start_logits, start_positions)
            end_loss = loss_fct(end_logits, end_positions)
            span_loss = (start_loss + end_loss) / 2.0

            if is_answerable is not None:
                ans_loss = loss_fct(ans_logits, is_answerable.long())
                total_loss = span_loss + 1.0 * ans_loss
            else:
                total_loss = span_loss

        return start_logits, end_logits, ans_logits, total_loss

    def count_parameters(self) -> int:
        """Count trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def get_summary(self) -> Dict[str, Any]:
        """Return model metadata and parameter breakdown."""
        total_params = self.count_parameters()
        return {
            "model_name": self.config.model_name,
            "architecture": "Bidirectional Transformer Reader (PESE-QA-0)",
            "vocab_size": self.config.vocab_size,
            "d_model": self.config.d_model,
            "n_layers": self.config.n_layers,
            "n_heads": self.config.n_heads,
            "d_ff": self.config.d_ff,
            "max_seq_len": self.config.max_seq_len,
            "total_parameters": total_params,
            "parameter_breakdown": {
                "tok_embeddings": self.tok_embeddings.weight.numel(),
                "pos_embeddings": self.pos_embeddings.weight.numel(),
                "seg_embeddings": self.seg_embeddings.weight.numel(),
                "encoder_blocks": sum(p.numel() for b in self.blocks for p in b.parameters()),
                "final_layernorm": sum(p.numel() for p in self.ln_f.parameters()),
                "qa_outputs_head": sum(p.numel() for p in self.qa_outputs.parameters()),
                "answerability_head": sum(p.numel() for p in self.answerability_head.parameters()),
            }
        }
