"""
PESE Search Sync: Neural Shadow Bridge Adapter
Phase N3-B: PESE-Rel-0 Resident Observation Adapter

Connects the trained PESE-Rel-0 relation cross-encoder to real MAAE evidence
candidates in pure SHADOW MODE with strictly ZERO authority.
"""

import os
import time
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from threading import RLock

import torch

from .contracts import (
    NeuralShadowObservation,
    SearchResultNeuralSummary,
    FeedbackType,
    classify_diagnostic_alignment,
)
from ..neural.models.registry import registry, ModelStatus
from ..neural.configs.model_config import RelationConfig
from ..neural.models.relation_classifier import PESERelationClassifier
from ..neural.tokenization.relation_tokenizer import RelationTokenizer

logger = logging.getLogger(__name__)

# Default file locations
RELATION_CKPT_DIR = Path(__file__).resolve().parent.parent / "neural" / "checkpoints" / "relation"
DEFAULT_CHECKPOINT_PATH = RELATION_CKPT_DIR / "peserel0_best.pt"
DEFAULT_TOKENIZER_PATH = RELATION_CKPT_DIR / "peserel0_tokenizer.json"
FROZEN_CHECKPOINT_HASH = "1dd87075cfbf23c09fed5e90be948c6c7af005e9e909ab47e5df6c374b56ff70"
FROZEN_TOKENIZER_HASH = "e2023f42797473452a4a702ddb0894b6540277b85f5bdcc7436ecd1587ea03ec"

DEFAULT_DIAGNOSTIC_THRESHOLD = 0.85
DEFAULT_MAX_CANDIDATE_BUDGET = 6


class PESERelationShadowAdapter:
    """
    Resident inference adapter that evaluates candidate evidence through PESE-Rel-0.
    Operates in pure observer mode: strictly ZERO authority over ranking or answers.
    """

    def __init__(
        self,
        checkpoint_path: Path = DEFAULT_CHECKPOINT_PATH,
        tokenizer_path: Path = DEFAULT_TOKENIZER_PATH,
        diagnostic_threshold: float = DEFAULT_DIAGNOSTIC_THRESHOLD,
        max_candidate_budget: int = DEFAULT_MAX_CANDIDATE_BUDGET,
    ):
        self.checkpoint_path = Path(checkpoint_path)
        self.tokenizer_path = Path(tokenizer_path)
        self.diagnostic_threshold = diagnostic_threshold
        self.max_candidate_budget = max_candidate_budget

        self._lock = RLock()
        self._model: Optional[PESERelationClassifier] = None
        self._tokenizer: Optional[RelationTokenizer] = None
        self._checkpoint_hash: Optional[str] = None
        self._init_error: Optional[str] = None

        # Verify registry invariants at instantiation
        self._verify_registry_invariants()

    def _verify_registry_invariants(self) -> None:
        """Enforces that PESE-Rel-0 holds zero authority in the model registry."""
        card = registry.get("PESE-Rel-0")
        if card is not None:
            if card.allowed_for_ranking or card.allowed_for_answers:
                raise RuntimeError(
                    "SECURITY INVARIANT VIOLATION: PESE-Rel-0 has authority enabled in registry! "
                    "N3-B strictly requires allowed_for_ranking=False and allowed_for_answers=False."
                )
            if card.status != ModelStatus.EXPERIMENT:
                logger.warning("PESE-Rel-0 status is %s (expected EXPERIMENT)", card.status)

    def _load_model_and_tokenizer(self) -> Tuple[PESERelationClassifier, RelationTokenizer, str]:
        """Lazy thread-safe loader for model weights and tokenizer."""
        with self._lock:
            if self._model is not None and self._tokenizer is not None and self._checkpoint_hash is not None:
                return self._model, self._tokenizer, self._checkpoint_hash

            if self._init_error is not None:
                raise RuntimeError(f"Shadow model initialization previously failed: {self._init_error}")

            if not self.checkpoint_path.exists():
                err = f"Checkpoint not found at {self.checkpoint_path}"
                self._init_error = err
                raise FileNotFoundError(err)

            if not self.tokenizer_path.exists():
                err = f"Tokenizer not found at {self.tokenizer_path}"
                self._init_error = err
                raise FileNotFoundError(err)

            # Compute and store frozen checkpoint SHA-256
            ckpt_bytes = self.checkpoint_path.read_bytes()
            self._checkpoint_hash = hashlib.sha256(ckpt_bytes).hexdigest()
            if (self._checkpoint_hash != FROZEN_CHECKPOINT_HASH or
                    hashlib.sha256(self.tokenizer_path.read_bytes()).hexdigest() != FROZEN_TOKENIZER_HASH):
                self._checkpoint_hash = None
                self._init_error = "Frozen model/tokenizer integrity check failed"
                raise ValueError(self._init_error)

            # Load Tokenizer
            self._tokenizer = RelationTokenizer.load(str(self.tokenizer_path))

            # Load Checkpoint weights
            ckpt = torch.load(self.checkpoint_path, map_location="cpu", weights_only=True)
            config = RelationConfig(**ckpt["config"])
            self._model = PESERelationClassifier(config)
            self._model.load_state_dict(ckpt["model_state_dict"])
            self._model.eval()

            # Enforce CPU eval mode
            for p in self._model.parameters():
                p.requires_grad = False

            logger.info(
                "PESE-Rel-0 shadow model resident loaded: %d parameters, hash=%s (Authority: NONE)",
                config.count_parameters(),
                self._checkpoint_hash[:16],
            )
            return self._model, self._tokenizer, self._checkpoint_hash

    @property
    def checkpoint_hash(self) -> str:
        """Observability must never initialize inference, including when disabled."""
        return self._checkpoint_hash or "UNAVAILABLE"

    def is_enabled(self) -> bool:
        """Checks the global disable switch."""
        env_val = os.getenv("PESE_REL_SHADOW_ENABLED", "true").strip().lower()
        return env_val in ("true", "1", "yes", "on")

    def observe_candidates(
        self,
        query: str,
        normalized_query: str,
        search_context_id: str,
        candidate_items: List[Dict[str, Any]],
        active_feedback_map: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, SearchResultNeuralSummary], List[NeuralShadowObservation]]:
        """
        Executes batch shadow inference over budgeted candidate evidence items.
        Returns:
            (summaries_by_target_id, all_observations_list)

        Fail-Open Guarantee:
            If model loading, tokenization, PyTorch forward pass, or any internal
            logic throws an error, this method catches the exception, logs a warning,
            and returns fallback diagnostic objects with status='SHADOW_ERROR' and
            authority='NONE'. Search execution is never interrupted.
        """
        if not self.is_enabled():
            return self._build_disabled_fallback(candidate_items)

        if not candidate_items:
            return {}, []

        # 1. Enforce candidate budget cap
        budgeted_items = candidate_items[: self.max_candidate_budget]

        try:
            t0 = time.perf_counter()
            model, tokenizer, ckpt_hash = self._load_model_and_tokenizer()

            # 2. Build vectorized batch inputs
            features = []
            for item in budgeted_items:
                ev_text = item.get("evidence_text", "").strip()
                feat = tokenizer.build_cross_encoder_inputs(
                    question=query,
                    evidence=ev_text,
                    max_seq_len=128,
                )
                features.append(feat)

            input_ids = torch.tensor([f["input_ids"] for f in features], dtype=torch.long)
            token_type_ids = torch.tensor([f["token_type_ids"] for f in features], dtype=torch.long)
            attention_mask = torch.tensor([f["attention_mask"] for f in features], dtype=torch.long)

            # 3. Vectorized batch forward pass (CPU PyTorch)
            with torch.no_grad():
                logits = model(input_ids, token_type_ids, attention_mask)
                probs = torch.softmax(logits, dim=-1)

            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            per_candidate_ms = round(elapsed_ms / max(1, len(budgeted_items)), 2)

            # 4. Construct structured observations
            observations: List[NeuralShadowObservation] = []
            for idx, item in enumerate(budgeted_items):
                p_answers = float(probs[idx, 1].item())
                p_does_not = float(probs[idx, 0].item())
                label = "ANSWERS" if p_answers >= self.diagnostic_threshold else "DOES_NOT_ANSWER"

                ev_text = item.get("evidence_text", "")
                ev_summary = (ev_text[:180] + "...") if len(ev_text) > 180 else ev_text

                obs = NeuralShadowObservation(
                    search_context_id=search_context_id,
                    model_id="PESE-Rel-0",
                    checkpoint_hash=ckpt_hash,
                    query=query,
                    normalized_query=normalized_query,
                    target_type=item.get("target_type", "SERP_RESULT"),
                    target_id=item["target_id"],
                    target_slug=item.get("target_slug"),
                    evidence_id=item.get("evidence_id", f"{item['target_id']}#p0"),
                    evidence_summary=ev_summary,
                    answers_probability=round(p_answers, 4),
                    does_not_answer_probability=round(p_does_not, 4),
                    predicted_label=label,
                    threshold_used=self.diagnostic_threshold,
                    authority="NONE",
                    latency_ms=per_candidate_ms,
                    metadata={
                        **item.get("provenance", {}),
                        "model_versions": {"relation": "PESE-Rel-0:shadow:" + ckpt_hash},
                        "seq_len": int(attention_mask[idx].sum().item()),
                        "batch_size": len(budgeted_items),
                        "total_inference_ms": elapsed_ms,
                    },
                )
                observations.append(obs)

            # 5. Group by target_id and compile SearchResultNeuralSummary
            summaries: Dict[str, SearchResultNeuralSummary] = {}
            for item in budgeted_items:
                tid = item["target_id"]
                if tid in summaries:
                    continue

                target_obs = [o for o in observations if o.target_id == tid and o.target_type == "SERP_RESULT"]
                if not target_obs:
                    continue

                # Find best candidate evidence (highest P(ANSWERS))
                best_obs = max(target_obs, key=lambda x: x.answers_probability)

                # Check active human feedback for diagnostic alignment
                fb_event = active_feedback_map.get(tid) if active_feedback_map else None
                fb_type = getattr(fb_event, "feedback", None)
                alignment = classify_diagnostic_alignment(best_obs.answers_probability, fb_type, self.diagnostic_threshold)

                summaries[tid] = SearchResultNeuralSummary(
                    answers_probability=best_obs.answers_probability,
                    does_not_answer_probability=best_obs.does_not_answer_probability,
                    predicted_label=best_obs.predicted_label,
                    best_evidence_id=best_obs.evidence_id,
                    evidence_count=len(target_obs),
                    authority="NONE",
                    status="OK",
                    alignment=alignment,
                    observations=target_obs,
                )

            return summaries, observations

        except Exception as exc:
            logger.warning("Neural shadow inference failed open: %s", exc, exc_info=True)
            return self._build_error_fallback(candidate_items, reason=str(exc))

    def _build_disabled_fallback(
        self, candidate_items: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, SearchResultNeuralSummary], List[NeuralShadowObservation]]:
        """Fallback when PESE_REL_SHADOW_ENABLED=false."""
        summaries = {}
        for item in candidate_items:
            tid = item["target_id"]
            if tid not in summaries:
                summaries[tid] = SearchResultNeuralSummary(
                    authority="NONE",
                    status="DISABLED",
                )
        return summaries, []

    def _build_error_fallback(
        self, candidate_items: List[Dict[str, Any]], reason: str
    ) -> Tuple[Dict[str, SearchResultNeuralSummary], List[NeuralShadowObservation]]:
        """Fallback when shadow model encounters an unrecoverable exception."""
        summaries = {}
        for item in candidate_items:
            tid = item["target_id"]
            if tid not in summaries:
                summaries[tid] = SearchResultNeuralSummary(
                    authority="NONE",
                    status=f"SHADOW_ERROR: {reason[:60]}",
                )
        return summaries, []


# Global singleton adapter for the engine process
shadow_adapter = PESERelationShadowAdapter()
