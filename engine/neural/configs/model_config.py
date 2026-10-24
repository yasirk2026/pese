"""
PESE Neural Genesis: Model & Experiment Configurations
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class TransformerConfig(BaseModel):
    """Configuration for PESE Transformer Core architectures."""
    model_name: str = "PESE-NG-0"
    vocab_size: int = 1024
    d_model: int = 128
    n_layers: int = 4
    n_heads: int = 4
    d_ff: int = 512
    max_seq_len: int = 256
    dropout: float = 0.1
    bias: bool = True
    initializer_range: float = 0.02

    @property
    def head_dim(self) -> int:
        assert self.d_model % self.n_heads == 0, f"d_model ({self.d_model}) must be divisible by n_heads ({self.n_heads})"
        return self.d_model // self.n_heads

    def count_parameters(self) -> int:
        """Calculate theoretical parameter count analytically."""
        # Token embeddings: vocab_size * d_model
        # Positional embeddings: max_seq_len * d_model
        embed_params = (self.vocab_size + self.max_seq_len) * self.d_model

        # Per layer:
        # 1. Multi-head attention: Q, K, V, Out projections -> 4 * (d_model * d_model + (d_model if bias else 0))
        # 2. Two LayerNorms: 2 * (2 * d_model) = 4 * d_model
        # 3. FFN: d_model * d_ff + d_ff + d_ff * d_model + d_model = 2 * d_model * d_ff + (d_ff + d_model if bias else 0)
        attn_params = 4 * (self.d_model * self.d_model + (self.d_model if self.bias else 0))
        ln_params = 4 * self.d_model
        ffn_params = 2 * self.d_model * self.d_ff + ((self.d_ff + self.d_model) if self.bias else 0)
        layer_params = self.n_layers * (attn_params + ln_params + ffn_params)

        # Final LayerNorm: 2 * d_model
        # LM Head (if untied): d_model * vocab_size
        head_params = (2 * self.d_model) + (self.d_model * self.vocab_size)

        return embed_params + layer_params + head_params


class TrainingConfig(BaseModel):
    """Configuration for reproducible neural training experiments."""
    experiment_name: str = "ng0-baseline-experiment"
    random_seed: int = 42
    batch_size: int = 8
    learning_rate: float = 5e-4
    min_learning_rate: float = 5e-5
    weight_decay: float = 0.01
    gradient_clip: float = 1.0
    epochs: int = 20
    max_steps: Optional[int] = 500
    warmup_steps: int = 50
    eval_interval_steps: int = 25
    checkpoint_interval_steps: int = 100
    device: str = "cpu"
    dataset_name: str = "public-synthetic-corpus-v1"


class QAConfig(BaseModel):
    """Configuration for PESE-QA-0 Bidirectional Transformer Reader."""
    model_name: str = "PESE-QA-0"
    vocab_size: int = 1024
    d_model: int = 128
    n_layers: int = 4
    n_heads: int = 4
    d_ff: int = 512
    max_seq_len: int = 256
    dropout: float = 0.1
    bias: bool = True
    initializer_range: float = 0.02
    type_vocab_size: int = 2  # 0 for question, 1 for context
    max_answer_len: int = 30
    null_score_diff_threshold: float = 0.0

    @property
    def head_dim(self) -> int:
        assert self.d_model % self.n_heads == 0, f"d_model ({self.d_model}) must be divisible by n_heads ({self.n_heads})"
        return self.d_model // self.n_heads

    def count_parameters(self) -> int:
        """Calculate theoretical parameter count analytically."""
        # Embeddings: token + positional + segment
        embed_params = (self.vocab_size + self.max_seq_len + self.type_vocab_size) * self.d_model

        # Per layer (Bidirectional Attention + 2 LayerNorms + FFN)
        attn_params = 4 * (self.d_model * self.d_model + (self.d_model if self.bias else 0))
        ln_params = 4 * self.d_model
        ffn_params = 2 * self.d_model * self.d_ff + ((self.d_ff + self.d_model) if self.bias else 0)
        layer_params = self.n_layers * (attn_params + ln_params + ffn_params)

        # Final LayerNorm: 2 * d_model
        # Start/End QA head: d_model * 2 + 2
        # Answerability head: (d_model * d_model + d_model) + (d_model * 2 + 2)
        head_params = (2 * self.d_model) + (self.d_model * 2 + 2) + (self.d_model * self.d_model + self.d_model + self.d_model * 2 + 2)

        return embed_params + layer_params + head_params


class QATrainingConfig(BaseModel):
    """Configuration for PESE-QA training runs."""
    experiment_name: str = "qa0-experiment"
    random_seed: int = 42
    batch_size: int = 8
    learning_rate: float = 1e-3
    min_learning_rate: float = 1e-4
    weight_decay: float = 0.01
    gradient_clip: float = 1.0
    epochs: int = 15
    max_steps: Optional[int] = 300
    warmup_steps: int = 30
    eval_interval_steps: int = 25
    checkpoint_interval_steps: int = 50
    device: str = "cpu"
    dataset_name: str = "pese-public-qa-corpus-v1"


class RelationConfig(BaseModel):
    """Configuration for PESE-Rel-0 Cross-Encoder Bidirectional Transformer."""
    model_name: str = "PESE-Rel-0"
    architecture: str = "Cross-Encoder Bidirectional Transformer (Pre-LayerNorm)"
    vocab_size: int = 512
    d_model: int = 128
    n_layers: int = 4
    n_heads: int = 4
    d_ff: int = 512
    max_seq_len: int = 128
    dropout: float = 0.1
    bias: bool = True
    initializer_range: float = 0.02
    type_vocab_size: int = 2  # 0 for question, 1 for evidence
    num_classes: int = 2      # 0 for DOES_NOT_ANSWER, 1 for ANSWERS

    @property
    def head_dim(self) -> int:
        assert self.d_model % self.n_heads == 0, f"d_model ({self.d_model}) must be divisible by n_heads ({self.n_heads})"
        return self.d_model // self.n_heads

    def count_parameters(self) -> int:
        """Calculate theoretical parameter count analytically."""
        embed_params = (self.vocab_size + self.max_seq_len + self.type_vocab_size) * self.d_model
        attn_params = 4 * (self.d_model * self.d_model + (self.d_model if self.bias else 0))
        ln_params = 4 * self.d_model
        ffn_params = 2 * self.d_model * self.d_ff + ((self.d_ff + self.d_model) if self.bias else 0)
        layer_params = self.n_layers * (attn_params + ln_params + ffn_params)
        final_ln = 2 * self.d_model
        head_params = (self.d_model * self.d_model + (self.d_model if self.bias else 0)) + (self.d_model * self.num_classes + (self.num_classes if self.bias else 0))
        return embed_params + layer_params + final_ln + head_params


class RelationTrainingConfig(BaseModel):
    """Configuration for reproducible PESE-Rel-0 neural training runs."""
    experiment_name: str = "pese-rel-0-training"
    random_seed: int = 42
    batch_size: int = 16
    learning_rate: float = 3e-4
    min_learning_rate: float = 3e-5
    weight_decay: float = 0.01
    gradient_clip: float = 1.0
    epochs: int = 25
    warmup_steps: int = 20
    eval_interval_steps: int = 10
    early_stopping_patience: int = 8
    device: str = "cpu"
    dataset_name: str = "PESE-REL-DATA-0"

