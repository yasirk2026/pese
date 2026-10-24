"""
PESE Neural Genesis: Model Registry & Catalog
Maintains model metadata, lifecycle states, and gating restrictions.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from ..configs.model_config import TransformerConfig, QAConfig, RelationConfig


class ModelStatus(str, Enum):
    EXPERIMENT = "experiment"
    CANDIDATE = "candidate"
    APPROVED = "approved"
    ARCHIVED = "archived"


class ModelCard(BaseModel):
    """Metadata card for a registered neural model."""
    model_id: str
    architecture: str
    status: ModelStatus = ModelStatus.EXPERIMENT
    description: str
    config: Dict[str, Any]
    total_parameters: int
    allowed_for_ranking: bool = False
    allowed_for_answers: bool = False
    registered_at: str
    checkpoint_path: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class ModelRegistry:
    """Catalog of registered neural architectures in PESE."""

    def __init__(self):
        self._models: Dict[str, ModelCard] = {}
        self._register_defaults()

    def _register_defaults(self):
        ng0_cfg = TransformerConfig(
            model_name="PESE-NG-0",
            vocab_size=1024,
            d_model=128,
            n_layers=4,
            n_heads=4,
            d_ff=512,
            max_seq_len=256,
            dropout=0.1
        )
        self.register(
            ModelCard(
                model_id="PESE-NG-0",
                architecture="Decoder-Only Causal Transformer (Pre-LayerNorm)",
                status=ModelStatus.EXPERIMENT,
                description="PESE Neural Genesis initial foundational causal Transformer (~1.2M parameters). Strictly experimental laboratory model.",
                config=ng0_cfg.model_dump(),
                total_parameters=ng0_cfg.count_parameters(),
                allowed_for_ranking=False,
                allowed_for_answers=False,
                registered_at="2026-10-22T00:00:00Z",
                notes=[
                    "Pre-LayerNorm architecture with GELU non-linearities and causal masking.",
                    "Isolated to Neural Genesis laboratory; zero connection to production BM25F/BGE hybrid retrieval.",
                    "Trained solely on synthetic public corpus; zero access to private user search history or documents."
                ]
            )
        )
        qa0_cfg = QAConfig(
            model_name="PESE-QA-0",
            vocab_size=1024,
            d_model=128,
            n_layers=4,
            n_heads=4,
            d_ff=512,
            max_seq_len=256,
            dropout=0.1
        )
        self.register(
            ModelCard(
                model_id="PESE-QA-0",
                architecture="Bidirectional Transformer Reader (Pre-LayerNorm)",
                status=ModelStatus.EXPERIMENT,
                description="PESE-QA-0 foundational extractive reading comprehension reader (~1.1M parameters). Extracts exact answer spans with abstention support.",
                config=qa0_cfg.model_dump(),
                total_parameters=qa0_cfg.count_parameters(),
                allowed_for_ranking=False,
                allowed_for_answers=False,
                registered_at="2026-10-22T00:00:00Z",
                notes=[
                    "Bidirectional attention over [CLS] Question [SEP] Passage [SEP] without causal masking.",
                    "Dual span prediction heads (start/end logits) and pooled answerability classification head.",
                    "Supports abstention ('NO EVIDENCE = NO ANSWER') when passage context is insufficient.",
                    "Isolated to shadow mode; zero destructive impact on production BM25F/BGE hybrid retrieval."
                ]
            )
        )
        rel0_cfg = RelationConfig(
            model_name="PESE-Rel-0",
            vocab_size=512,
            d_model=128,
            n_layers=4,
            n_heads=4,
            d_ff=512,
            max_seq_len=128,
            dropout=0.1
        )
        self.register(
            ModelCard(
                model_id="PESE-Rel-0",
                architecture="Cross-Encoder Bidirectional Transformer (Pre-LayerNorm)",
                status=ModelStatus.EXPERIMENT,
                description="PESE-Rel-0 foundational relation-support cross-encoder classifier (~892k parameters). Judged whether candidate evidence genuinely ANSWERS a question.",
                config=rel0_cfg.model_dump(),
                total_parameters=rel0_cfg.count_parameters(),
                allowed_for_ranking=False,
                allowed_for_answers=False,
                registered_at="2026-10-24T00:00:00Z",
                checkpoint_path="engine/neural/checkpoints/relation/peserel0_best.pt",
                notes=[
                    "Cross-encoder Transformer with segment embeddings over [CLS] Question [SEP] Evidence [SEP].",
                    "Trained exclusively on frozen PESE-REL-DATA-0 train split with disjoint scenario/entity splits.",
                    "Isolated to experimental laboratory research; strictly forbidden from production ranking or Featured Answers.",
                    "Validated 85.0% accuracy on frozen test set, significantly outperforming keyword, Jaccard, and BGE baselines."
                ]
            )
        )

    def register(self, card: ModelCard):
        self._models[card.model_id] = card

    def get(self, model_id: str) -> Optional[ModelCard]:
        return self._models.get(model_id)

    def list_models(self) -> List[ModelCard]:
        return list(self._models.values())


# Global singleton instance for the engine
registry = ModelRegistry()
