"""
PESE Transformer Core: PESE-NG-0 Neural Architecture
Full causal language model with learned embeddings, pre-LayerNorm residual blocks,
and autoregressive token generation.
"""

import math
from typing import Optional, Tuple, Dict, Any
import torch
import torch.nn as nn
import torch.nn.functional as F

from ..configs.model_config import TransformerConfig
from .transformer_block import TransformerBlock


class PESETransformer(nn.Module):
    """
    PESE Neural Genesis Core Model (PESE-NG-0).
    Causal Transformer Decoder for autoregressive language modeling.
    """

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.config = config

        # Token & Learned Positional Embeddings
        self.tok_embeddings = nn.Embedding(config.vocab_size, config.d_model)
        self.pos_embeddings = nn.Embedding(config.max_seq_len, config.d_model)
        self.drop = nn.Dropout(config.dropout)

        # Transformer Decoder Layers
        self.blocks = nn.ModuleList([
            TransformerBlock(config) for _ in range(config.n_layers)
        ])

        # Final Layer Normalization
        self.ln_f = nn.LayerNorm(config.d_model, eps=1e-5)

        # Language Model Head (projects hidden state back to vocabulary logits)
        self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)

        # Weight tying (optional in some models, but we keep head explicit or tied)
        # Note: We keep lm_head untied for explicit parameter counting unless desired
        
        # Initialize weights
        self.apply(self._init_weights)

    def _init_weights(self, module: nn.Module):
        """Standard Gaussian initialization for Transformer stability."""
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
        idx: torch.Tensor,
        targets: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Forward pass for PESETransformer.

        Args:
            idx: Tensor of token indices, shape (B, T)
            targets: Optional ground-truth token indices for loss computation, shape (B, T)

        Returns:
            Tuple of (logits: (B, T, V), loss: Optional[torch.Tensor])
        """
        device = idx.device
        B, T = idx.size()
        if T > self.config.max_seq_len:
            raise ValueError(
                f"Sequence length {T} exceeds maximum sequence length {self.config.max_seq_len}"
            )

        # Generate position indices [0, 1, ..., T-1]
        pos = torch.arange(0, T, dtype=torch.long, device=device).unsqueeze(0)  # (1, T)

        # Embeddings: Token + Positional
        tok_emb = self.tok_embeddings(idx)  # (B, T, D)
        pos_emb = self.pos_embeddings(pos)  # (1, T, D)
        x = self.drop(tok_emb + pos_emb)

        # Pass through Transformer blocks
        for block in self.blocks:
            x = block(x)

        # Final LayerNorm
        x = self.ln_f(x)

        # Project to vocabulary logits
        logits = self.lm_head(x)  # (B, T, V)

        loss = None
        if targets is not None:
            # Cross-entropy loss over flattened tokens
            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                targets.view(-1),
                ignore_index=-100
            )

        return logits, loss

    @torch.no_grad()
    def generate(
        self,
        idx: torch.Tensor,
        max_new_tokens: int,
        temperature: float = 1.0,
        top_k: Optional[int] = None
    ) -> torch.Tensor:
        """
        Autoregressive generation loop.
        Appends max_new_tokens to prompt sequence `idx` (shape (B, T)).
        """
        for _ in range(max_new_tokens):
            # Crop context if it exceeds max_seq_len
            idx_cond = idx if idx.size(1) <= self.config.max_seq_len else idx[:, -self.config.max_seq_len:]
            
            # Forward pass to get logits for the last token
            logits, _ = self.forward(idx_cond)
            logits = logits[:, -1, :]  # (B, V)

            if temperature <= 0.0 or temperature == 1e-6:
                # Greedy argmax decoding
                idx_next = torch.argmax(logits, dim=-1, keepdim=True)
            else:
                logits = logits / temperature
                if top_k is not None and top_k > 0:
                    v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                    logits[logits < v[:, [-1]]] = -float("Inf")
                probs = F.softmax(logits, dim=-1)
                idx_next = torch.multinomial(probs, num_samples=1)

            # Append sampled token to running sequence
            idx = torch.cat((idx, idx_next), dim=1)

        return idx

    def count_parameters(self) -> int:
        """Count total trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def get_summary(self) -> Dict[str, Any]:
        """Return structural model summary."""
        total_params = self.count_parameters()
        return {
            "model_name": self.config.model_name,
            "vocab_size": self.config.vocab_size,
            "d_model": self.config.d_model,
            "n_layers": self.config.n_layers,
            "n_heads": self.config.n_heads,
            "d_ff": self.config.d_ff,
            "max_seq_len": self.config.max_seq_len,
            "dropout": self.config.dropout,
            "total_parameters": total_params,
            "parameter_breakdown": {
                "token_embeddings": self.tok_embeddings.weight.numel(),
                "positional_embeddings": self.pos_embeddings.weight.numel(),
                "transformer_blocks": sum(p.numel() for block in self.blocks for p in block.parameters()),
                "final_layernorm": sum(p.numel() for p in self.ln_f.parameters()),
                "lm_head": self.lm_head.weight.numel()
            }
        }
