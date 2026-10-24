"""
PESE Transformer Core: Pre-LayerNorm Transformer Block
Each block consists of multi-head self-attention and position-wise FFN with pre-layer normalization.
"""

import torch
import torch.nn as nn
from ..configs.model_config import TransformerConfig
from .attention import MultiHeadSelfAttention
from .ffn import FeedForward


class TransformerBlock(nn.Module):
    """
    Pre-LayerNorm Transformer Decoder Block:
        x -> LayerNorm -> Causal Self-Attention -> Dropout -> (+) -> x
        x -> LayerNorm -> Feed-Forward Network  -> Dropout -> (+) -> Output
    """

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.ln1 = nn.LayerNorm(config.d_model, eps=1e-5)
        self.attn = MultiHeadSelfAttention(config)
        self.ln2 = nn.LayerNorm(config.d_model, eps=1e-5)
        self.ffn = FeedForward(config)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Pre-LN attention branch
        x = x + self.attn(self.ln1(x))
        # Pre-LN FFN branch
        x = x + self.ffn(self.ln2(x))
        return x
