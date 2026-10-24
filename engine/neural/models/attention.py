"""
PESE Transformer Core: Multi-Head Self-Attention
Implemented with explicit mathematical tensor transformations and causal masking.
"""

import math
import torch
import torch.nn as nn
from ..configs.model_config import TransformerConfig


class MultiHeadSelfAttention(nn.Module):
    """
    Multi-Head Causal Self-Attention module.
    
    Tensor Dimensions:
        Input X: (B, T, D)
        Q, K, V: (B, h, T, d_k) where d_k = D // h
        Attention Weights S: (B, h, T, T)
        Output Context: (B, T, D)
    """

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.d_model = config.d_model
        self.n_heads = config.n_heads
        self.head_dim = config.head_dim
        self.dropout = config.dropout

        # Linear projections for Query, Key, Value
        self.q_proj = nn.Linear(self.d_model, self.d_model, bias=config.bias)
        self.k_proj = nn.Linear(self.d_model, self.d_model, bias=config.bias)
        self.v_proj = nn.Linear(self.d_model, self.d_model, bias=config.bias)
        self.out_proj = nn.Linear(self.d_model, self.d_model, bias=config.bias)

        # Regularization
        self.attn_dropout = nn.Dropout(config.dropout)
        self.resid_dropout = nn.Dropout(config.dropout)

        # Causal mask ensuring token at t can only attend to tokens <= t
        self.register_buffer(
            "causal_mask",
            torch.tril(torch.ones(config.max_seq_len, config.max_seq_len)).view(
                1, 1, config.max_seq_len, config.max_seq_len
            ),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, D = x.size()

        # 1. Project inputs into Queries, Keys, Values: (B, T, D)
        q = self.q_proj(x)
        k = self.k_proj(x)
        v = self.v_proj(x)

        # 2. Reshape and transpose for multi-head attention: (B, h, T, d_k)
        q = q.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)

        # 3. Compute scaled dot-product attention scores: (B, h, T, T)
        # Scaled by 1 / sqrt(d_k) to prevent vanishing gradients in softmax
        scale = 1.0 / math.sqrt(self.head_dim)
        scores = torch.matmul(q, k.transpose(-2, -1)) * scale

        # 4. Apply causal mask (set attention to future positions to -inf)
        scores = scores.masked_fill(self.causal_mask[:, :, :T, :T] == 0, float("-inf"))

        # 5. Softmax over key sequence dimension to get attention distribution
        attn_weights = torch.softmax(scores, dim=-1)
        attn_weights = self.attn_dropout(attn_weights)

        # 6. Compute weighted context vector: (B, h, T, d_k)
        context = torch.matmul(attn_weights, v)

        # 7. Concatenate all attention heads back to (B, T, D)
        context = context.transpose(1, 2).contiguous().view(B, T, D)

        # 8. Final linear projection with residual dropout
        out = self.out_proj(context)
        return self.resid_dropout(out)
