"""
PESE Transformer Core: Position-Wise Feed-Forward Network
Two-layer projection with non-linear activation and residual dropout.
"""

import torch
import torch.nn as nn
from ..configs.model_config import TransformerConfig


class FeedForward(nn.Module):
    """
    Position-wise Feed-Forward Network (FFN).
    Expands hidden dimension: D -> d_ff -> D with GELU activation.
    """

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.fc1 = nn.Linear(config.d_model, config.d_ff, bias=config.bias)
        self.act = nn.GELU()
        self.fc2 = nn.Linear(config.d_ff, config.d_model, bias=config.bias)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # (B, T, D) -> (B, T, d_ff) -> (B, T, D)
        h = self.act(self.fc1(x))
        out = self.fc2(h)
        return self.dropout(out)
