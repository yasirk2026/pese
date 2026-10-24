"""
PESE-QA-0: Training Pipeline Subsystem
Specialized trainer for extractive question answering with dual span loss,
answerability classification, gradient clipping, and exact span accuracy metrics.
"""

import time
import math
import random
from typing import Dict, List, Optional, Any
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from ..configs.model_config import QATrainingConfig
from ..models.qa_reader import PESEQAReader
from .checkpoint import save_checkpoint


DEFAULT_QA_CHECKPOINT_DIR = Path(__file__).resolve().parent.parent / "checkpoints" / "qa"


class QATrainer:
    """
    Supervised trainer for PESE-QA-0 reading comprehension reader.
    """

    def __init__(
        self,
        model: PESEQAReader,
        train_dataset: Dataset,
        config: QATrainingConfig,
        val_dataset: Optional[Dataset] = None,
        checkpoint_dir: Optional[Path] = None
    ):
        self.model = model
        self.config = config
        self.train_dataset = train_dataset
        self.val_dataset = val_dataset
        self.checkpoint_dir = Path(checkpoint_dir or DEFAULT_QA_CHECKPOINT_DIR)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self.device = torch.device(config.device)
        self.model.to(self.device)

        # Seeding
        random.seed(config.random_seed)
        torch.manual_seed(config.random_seed)

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

        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
            betas=(0.9, 0.98),
            eps=1e-8
        )

        self.history: List[Dict[str, Any]] = []

    def _get_lr(self, step: int, total_steps: int) -> float:
        """Linear warmup followed by cosine decay."""
        if step < self.config.warmup_steps:
            return self.config.learning_rate * float(step) / float(max(1, self.config.warmup_steps))
        progress = float(step - self.config.warmup_steps) / float(max(1, total_steps - self.config.warmup_steps))
        cosine_factor = 0.5 * (1.0 + math.cos(math.pi * progress))
        return self.config.min_learning_rate + cosine_factor * (self.config.learning_rate - self.config.min_learning_rate)

    @torch.no_grad()
    def evaluate(self) -> Dict[str, float]:
        """Compute validation metrics across validation loader."""
        if self.val_loader is None or len(self.val_loader) == 0:
            return {"val_loss": 0.0, "val_start_acc": 0.0, "val_end_acc": 0.0, "val_ans_acc": 0.0}

        self.model.eval()
        total_loss = 0.0
        total_samples = 0
        correct_start = 0
        correct_end = 0
        correct_ans = 0

        for batch in self.val_loader:
            input_ids = batch["input_ids"].to(self.device)
            token_type_ids = batch["token_type_ids"].to(self.device)
            attention_mask = batch["attention_mask"].to(self.device)
            start_pos = batch["start_positions"].to(self.device)
            end_pos = batch["end_positions"].to(self.device)
            is_ans = batch["is_answerable"].to(self.device)

            s_logits, e_logits, a_logits, loss = self.model(
                input_ids,
                token_type_ids=token_type_ids,
                attention_mask=attention_mask,
                start_positions=start_pos,
                end_positions=end_pos,
                is_answerable=is_ans
            )

            if loss is not None and not torch.isnan(loss):
                B = input_ids.size(0)
                total_loss += loss.item() * B
                total_samples += B

                pred_start = torch.argmax(s_logits, dim=-1)
                pred_end = torch.argmax(e_logits, dim=-1)
                pred_ans = torch.argmax(a_logits, dim=-1)

                correct_start += (pred_start == start_pos).sum().item()
                correct_end += (pred_end == end_pos).sum().item()
                correct_ans += (pred_ans == is_ans).sum().item()

        self.model.train()
        n = max(1, total_samples)
        return {
            "val_loss": round(total_loss / n, 4),
            "val_start_acc": round(correct_start / n * 100.0, 2),
            "val_end_acc": round(correct_end / n * 100.0, 2),
            "val_ans_acc": round(correct_ans / n * 100.0, 2),
        }

    def train(self) -> Dict[str, Any]:
        """Execute QA training curriculum."""
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

                # Adjust LR
                lr = self._get_lr(step, total_steps)
                for pg in self.optimizer.param_groups:
                    pg["lr"] = lr

                input_ids = batch["input_ids"].to(self.device)
                token_type_ids = batch["token_type_ids"].to(self.device)
                attention_mask = batch["attention_mask"].to(self.device)
                start_pos = batch["start_positions"].to(self.device)
                end_pos = batch["end_positions"].to(self.device)
                is_ans = batch["is_answerable"].to(self.device)

                self.optimizer.zero_grad()
                s_logits, e_logits, a_logits, loss = self.model(
                    input_ids,
                    token_type_ids=token_type_ids,
                    attention_mask=attention_mask,
                    start_positions=start_pos,
                    end_positions=end_pos,
                    is_answerable=is_ans
                )

                if loss is None:
                    continue

                if torch.isnan(loss) or torch.isinf(loss):
                    raise ValueError(f"Training instability: NaN loss at QA step {step}")

                loss_val = loss.item()
                if initial_loss is None:
                    initial_loss = loss_val
                last_loss = loss_val

                loss.backward()
                grad_norm = nn.utils.clip_grad_norm_(
                    self.model.parameters(),
                    self.config.gradient_clip
                )
                self.optimizer.step()

                # Step accuracies
                pred_start = torch.argmax(s_logits, dim=-1)
                pred_end = torch.argmax(e_logits, dim=-1)
                pred_ans = torch.argmax(a_logits, dim=-1)

                start_acc = (pred_start == start_pos).float().mean().item() * 100.0
                end_acc = (pred_end == end_pos).float().mean().item() * 100.0
                ans_acc = (pred_ans == is_ans).float().mean().item() * 100.0

                log_entry = {
                    "step": step,
                    "epoch": epoch + 1,
                    "loss": round(loss_val, 4),
                    "learning_rate": float(f"{lr:.6e}"),
                    "grad_norm": round(float(grad_norm), 4),
                    "start_acc": round(start_acc, 2),
                    "end_acc": round(end_acc, 2),
                    "ans_acc": round(ans_acc, 2),
                }

                if self.val_loader is not None and (step % self.config.eval_interval_steps == 0 or step == total_steps):
                    val_metrics = self.evaluate()
                    log_entry.update(val_metrics)

                self.history.append(log_entry)

                if step % self.config.checkpoint_interval_steps == 0 or step == total_steps:
                    chk_path = save_checkpoint(
                        model=self.model,
                        optimizer=self.optimizer,
                        config=self.model.config.model_dump(),
                        step=step,
                        loss=loss_val,
                        metrics={"epoch": epoch + 1, "start_acc": start_acc, "end_acc": end_acc},
                        checkpoint_dir=self.checkpoint_dir,
                        filename=f"peseqa0_step{step}.pt"
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
