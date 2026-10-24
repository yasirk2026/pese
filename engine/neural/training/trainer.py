"""
PESE Neural Genesis: Training Loop Subsystem
Engineers reproducible training runs with deterministic seeding, AdamW,
gradient clipping, NaN guards, and telemetry tracking.
"""

import time
import math
import random
from typing import Dict, List, Optional, Any
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from ..configs.model_config import TrainingConfig
from ..models.transformer import PESETransformer
from .checkpoint import save_checkpoint


def set_seed(seed: int) -> None:
    """Set deterministic random seeds across python, numpy, and torch."""
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class NeuralTrainer:
    """
    Standard trainer for PESE Neural Genesis Transformer models.
    """

    def __init__(
        self,
        model: PESETransformer,
        train_dataset: Dataset,
        config: TrainingConfig,
        val_dataset: Optional[Dataset] = None,
        checkpoint_dir: Optional[Path] = None
    ):
        self.model = model
        self.config = config
        self.train_dataset = train_dataset
        self.val_dataset = val_dataset
        self.checkpoint_dir = checkpoint_dir

        self.device = torch.device(config.device)
        self.model.to(self.device)

        # Set deterministic seed
        set_seed(config.random_seed)

        # Dataloaders
        self.train_loader = DataLoader(
            train_dataset,
            batch_size=config.batch_size,
            shuffle=True,
            drop_last=False
        )
        self.val_loader = DataLoader(
            val_dataset,
            batch_size=config.batch_size,
            shuffle=False,
            drop_last=False
        ) if val_dataset is not None else None

        # Optimizer: AdamW
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
            betas=(0.9, 0.95),
            eps=1e-8
        )

        # Telemetry
        self.history: List[Dict[str, Any]] = []

    def _get_lr(self, step: int, total_steps: int) -> float:
        """Linear warmup followed by cosine decay."""
        if step < self.config.warmup_steps:
            return self.config.learning_rate * float(step) / float(max(1, self.config.warmup_steps))
        progress = float(step - self.config.warmup_steps) / float(max(1, total_steps - self.config.warmup_steps))
        cosine_factor = 0.5 * (1.0 + math.cos(math.pi * progress))
        return self.config.min_learning_rate + cosine_factor * (self.config.learning_rate - self.config.min_learning_rate)

    @torch.no_grad()
    def evaluate(self) -> float:
        """Compute average validation loss."""
        if self.val_loader is None or len(self.val_loader) == 0:
            return 0.0

        self.model.eval()
        total_loss = 0.0
        count = 0

        for batch in self.val_loader:
            input_ids = batch["input_ids"].to(self.device)
            targets = batch["targets"].to(self.device)
            _, loss = self.model(input_ids, targets=targets)
            if loss is not None and not torch.isnan(loss):
                total_loss += loss.item() * input_ids.size(0)
                count += input_ids.size(0)

        self.model.train()
        return total_loss / max(1, count)

    def train(self) -> Dict[str, Any]:
        """
        Execute full training experiment according to TrainingConfig.
        """
        self.model.train()
        start_time = time.time()
        step = 0
        total_steps = self.config.max_steps or (self.config.epochs * len(self.train_loader))

        initial_loss: Optional[float] = None
        last_loss: float = 0.0
        saved_checkpoints: List[str] = []

        for epoch in range(self.config.epochs):
            for batch in self.train_loader:
                step += 1
                if self.config.max_steps and step > self.config.max_steps:
                    break

                # Adjust learning rate
                lr = self._get_lr(step, total_steps)
                for param_group in self.optimizer.param_groups:
                    param_group["lr"] = lr

                input_ids = batch["input_ids"].to(self.device)
                targets = batch["targets"].to(self.device)

                # Forward pass
                self.optimizer.zero_grad()
                logits, loss = self.model(input_ids, targets=targets)

                if loss is None:
                    continue

                # NaN guard
                if torch.isnan(loss) or torch.isinf(loss):
                    raise ValueError(f"Training instability detected: NaN/Inf loss at step {step}")

                loss_val = loss.item()
                if initial_loss is None:
                    initial_loss = loss_val
                last_loss = loss_val

                # Backward pass
                loss.backward()

                # Gradient clipping
                grad_norm = nn.utils.clip_grad_norm_(
                    self.model.parameters(),
                    self.config.gradient_clip
                )

                # Optimizer step
                self.optimizer.step()

                # Telemetry recording
                log_entry = {
                    "step": step,
                    "epoch": epoch + 1,
                    "loss": round(loss_val, 4),
                    "learning_rate": float(f"{lr:.6e}"),
                    "grad_norm": round(float(grad_norm), 4),
                }

                # Periodic evaluation
                if self.val_loader is not None and (step % self.config.eval_interval_steps == 0 or step == total_steps):
                    val_loss = self.evaluate()
                    log_entry["val_loss"] = round(val_loss, 4)

                self.history.append(log_entry)

                # Periodic checkpointing
                if step % self.config.checkpoint_interval_steps == 0 or step == total_steps:
                    chk_path = save_checkpoint(
                        model=self.model,
                        optimizer=self.optimizer,
                        config=self.model.config.model_dump(),
                        step=step,
                        loss=loss_val,
                        metrics={"epoch": epoch + 1, "grad_norm": float(grad_norm)},
                        checkpoint_dir=self.checkpoint_dir
                    )
                    saved_checkpoints.append(str(chk_path))

            if self.config.max_steps and step >= self.config.max_steps:
                break

        duration_sec = time.time() - start_time
        init_l = initial_loss if initial_loss is not None else 0.0
        pct_reduction = ((init_l - last_loss) / init_l * 100.0) if init_l > 0 else 0.0

        return {
            "experiment_name": self.config.experiment_name,
            "initial_loss": round(init_l, 4),
            "final_loss": round(last_loss, 4),
            "loss_reduction_pct": round(pct_reduction, 2),
            "steps_completed": step,
            "duration_seconds": round(duration_sec, 2),
            "saved_checkpoints": saved_checkpoints,
            "history": self.history
        }
