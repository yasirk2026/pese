"""
PESE Neural Genesis: PESE-Rel-0 Trainer & Experiment Engine
Phase N2: Optimization, Micro-Overfit Verification & Checkpointing

Trains PESERelationClassifier on CPU using AdamW with cosine decay and warmup.
Enforces strict split isolation, determinism, and gradient stability.
"""

import os
import time
import random
import math
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from ..configs.model_config import RelationConfig, RelationTrainingConfig
from ..models.relation_classifier import PESERelationClassifier
from ..tokenization.relation_tokenizer import RelationTokenizer
from ..data.relation_contracts import RelationExample, RelationLabel
from ..data.relation_dataset import RelationDataset
from ..data.manifest import load_frozen_dataset

CHECKPOINT_DIR = Path(__file__).resolve().parent.parent / "checkpoints" / "relation"


def set_seed(seed: int = 42):
    """Ensures reproducible training across Python, NumPy, and PyTorch."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def compute_metrics_from_logits(
    all_logits: torch.Tensor,
    all_labels: torch.Tensor
) -> Dict[str, Any]:
    """Computes binary classification metrics for the ANSWERS (1) class."""
    preds = torch.argmax(all_logits, dim=-1).cpu().numpy()
    labels = all_labels.cpu().numpy()

    tp = int(np.sum((preds == 1) & (labels == 1)))
    fp = int(np.sum((preds == 1) & (labels == 0)))
    tn = int(np.sum((preds == 0) & (labels == 0)))
    fn = int(np.sum((preds == 0) & (labels == 1)))

    total = len(labels)
    acc = (tp + tn) / total if total > 0 else 0.0
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

    return {
        "accuracy": round(float(acc), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1": round(float(f1), 4),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "total": total
    }


class RelationTrainer:
    """
    Dedicated training and experiment engine for PESE-Rel-0.
    """

    def __init__(
        self,
        config: Optional[RelationConfig] = None,
        train_config: Optional[RelationTrainingConfig] = None,
        tokenizer: Optional[RelationTokenizer] = None,
        splits: Optional[Dict[str, List[RelationExample]]] = None
    ):
        self.config = config or RelationConfig()
        self.train_config = train_config or RelationTrainingConfig()
        self.device = torch.device(self.train_config.device)

        set_seed(self.train_config.random_seed)

        self.splits = splits or load_frozen_dataset()

        # Initialize or train tokenizer strictly on train split
        if tokenizer is None:
            self.tokenizer = RelationTokenizer()
            self.tokenizer.train_on_split(self.splits["train"], target_vocab_size=self.config.vocab_size)
        else:
            self.tokenizer = tokenizer

        # Align vocab size in config with tokenizer
        self.config.vocab_size = self.tokenizer.vocab_size

        self.model = PESERelationClassifier(self.config).to(self.device)

        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    def run_micro_overfit(
        self,
        num_examples: int = 12,
        steps: int = 60,
        lr: float = 1e-3
    ) -> Dict[str, Any]:
        """
        Micro-overfit sanity check: trains on 8-16 examples to verify gradient flow.
        """
        print(f"\n--- [MICRO-OVERFIT] Training on {num_examples} examples for {steps} steps ---")
        set_seed(self.train_config.random_seed)

        # Select balanced sample from train
        pos = [ex for ex in self.splits["train"] if ex.label == RelationLabel.ANSWERS][:num_examples // 2]
        neg = [ex for ex in self.splits["train"] if ex.label == RelationLabel.DOES_NOT_ANSWER][:num_examples // 2]
        micro_examples = pos + neg

        micro_dataset = RelationDataset(micro_examples, self.tokenizer, self.config.max_seq_len)
        micro_loader = DataLoader(micro_dataset, batch_size=num_examples, shuffle=False)

        micro_model = PESERelationClassifier(self.config).to(self.device)
        optimizer = torch.optim.AdamW(micro_model.parameters(), lr=lr, weight_decay=0.0)

        initial_loss = None
        final_loss = None

        for step in range(steps):
            micro_model.train()
            for input_ids, token_type_ids, attention_mask, labels, _ in micro_loader:
                input_ids = input_ids.to(self.device)
                token_type_ids = token_type_ids.to(self.device)
                attention_mask = attention_mask.to(self.device)
                labels = labels.to(self.device)

                optimizer.zero_grad()
                loss, logits = micro_model(input_ids, token_type_ids, attention_mask, labels=labels)
                loss.backward()
                optimizer.step()

                if initial_loss is None:
                    initial_loss = float(loss.item())
                final_loss = float(loss.item())

        # Evaluate final accuracy on micro batch
        micro_model.eval()
        with torch.no_grad():
            for input_ids, token_type_ids, attention_mask, labels, _ in micro_loader:
                _, logits = micro_model(
                    input_ids.to(self.device),
                    token_type_ids.to(self.device),
                    attention_mask.to(self.device),
                    labels=labels.to(self.device)
                )
                metrics = compute_metrics_from_logits(logits, labels)

        loss_drop_pct = round(((initial_loss - final_loss) / initial_loss) * 100.0, 2)
        print(f"Micro-overfit: Initial loss={initial_loss:.4f}, Final loss={final_loss:.4f} ({loss_drop_pct}% drop)")
        print(f"Micro-overfit accuracy: {metrics['accuracy'] * 100:.1f}%, F1: {metrics['f1']:.4f}")

        return {
            "initial_loss": initial_loss,
            "final_loss": final_loss,
            "loss_drop_pct": loss_drop_pct,
            "accuracy": metrics["accuracy"],
            "f1": metrics["f1"],
            "converged": bool(loss_drop_pct >= 70.0 and metrics["accuracy"] >= 0.90)
        }

    def train(self) -> Dict[str, Any]:
        """
        Executes full training across epochs on the TRAIN split.
        Selects best checkpoint strictly based on VALIDATION F1 score.
        """
        print("\n==================== STARTING PESE-REL-0 FULL TRAINING ====================")
        set_seed(self.train_config.random_seed)

        train_dataset = RelationDataset(self.splits["train"], self.tokenizer, self.config.max_seq_len)
        val_dataset = RelationDataset(self.splits["validation"], self.tokenizer, self.config.max_seq_len)

        train_loader = DataLoader(
            train_dataset,
            batch_size=self.train_config.batch_size,
            shuffle=True
        )
        val_loader = DataLoader(
            val_dataset,
            batch_size=self.train_config.batch_size,
            shuffle=False
        )

        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.train_config.learning_rate,
            weight_decay=self.train_config.weight_decay,
            betas=(0.9, 0.98),
            eps=1e-8
        )

        total_steps = len(train_loader) * self.train_config.epochs
        warmup_steps = self.train_config.warmup_steps

        def lr_lambda(current_step: int) -> float:
            if current_step < warmup_steps:
                return float(current_step) / float(max(1, warmup_steps))
            progress = float(current_step - warmup_steps) / float(max(1, total_steps - warmup_steps))
            # Cosine decay down to 10%
            return max(0.1, 0.5 * (1.0 + math.cos(math.pi * progress)))

        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

        history = []
        best_val_f1 = -1.0
        best_epoch = -1
        best_metrics = {}
        epochs_no_improve = 0
        global_step = 0

        start_time = time.time()
        total_examples_trained = 0

        for epoch in range(1, self.train_config.epochs + 1):
            self.model.train()
            train_loss_total = 0.0
            train_preds = []
            train_targets = []

            for input_ids, token_type_ids, attention_mask, labels, _ in train_loader:
                input_ids = input_ids.to(self.device)
                token_type_ids = token_type_ids.to(self.device)
                attention_mask = attention_mask.to(self.device)
                labels = labels.to(self.device)

                optimizer.zero_grad()
                loss, logits = self.model(input_ids, token_type_ids, attention_mask, labels=labels)

                if torch.isnan(loss) or torch.isinf(loss):
                    raise RuntimeError(f"NaN/Inf loss detected at step {global_step}!")

                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), self.train_config.gradient_clip)
                optimizer.step()
                scheduler.step()

                train_loss_total += loss.item() * len(labels)
                train_preds.append(logits.detach())
                train_targets.append(labels.detach())

                total_examples_trained += len(labels)
                global_step += 1

            train_loss = train_loss_total / len(train_dataset)
            train_metrics = compute_metrics_from_logits(
                torch.cat(train_preds, dim=0),
                torch.cat(train_targets, dim=0)
            )

            # Evaluate on Validation Split
            val_loss, val_metrics = self.evaluate_loader(val_loader)

            epoch_record = {
                "epoch": epoch,
                "global_step": global_step,
                "lr": scheduler.get_last_lr()[0],
                "train_loss": round(train_loss, 4),
                "train_accuracy": train_metrics["accuracy"],
                "train_f1": train_metrics["f1"],
                "val_loss": round(val_loss, 4),
                "val_accuracy": val_metrics["accuracy"],
                "val_precision": val_metrics["precision"],
                "val_recall": val_metrics["recall"],
                "val_f1": val_metrics["f1"],
            }
            history.append(epoch_record)

            print(
                f"[Epoch {epoch:02d}/{self.train_config.epochs:02d}] "
                f"Train Loss: {train_loss:.4f} | Train Acc: {train_metrics['accuracy']*100:.1f}% | "
                f"Val Loss: {val_loss:.4f} | Val Acc: {val_metrics['accuracy']*100:.1f}% | "
                f"Val F1: {val_metrics['f1']:.4f} (Prec: {val_metrics['precision']:.3f}, Rec: {val_metrics['recall']:.3f})"
            )

            # Checkpoint selection strictly on validation F1
            if val_metrics["f1"] > best_val_f1:
                best_val_f1 = val_metrics["f1"]
                best_epoch = epoch
                best_metrics = val_metrics
                epochs_no_improve = 0
                self.save_checkpoint(
                    CHECKPOINT_DIR / "peserel0_best.pt",
                    epoch=epoch,
                    global_step=global_step,
                    metrics=val_metrics,
                    optimizer=optimizer,
                    is_best=True
                )
            else:
                epochs_no_improve += 1

            # Early stopping check
            if epochs_no_improve >= self.train_config.early_stopping_patience:
                print(f"Early stopping triggered after {epochs_no_improve} epochs without validation improvement.")
                break

        total_duration = time.time() - start_time
        examples_per_sec = total_examples_trained / total_duration if total_duration > 0 else 0.0

        # Save last checkpoint
        self.save_checkpoint(
            CHECKPOINT_DIR / "peserel0_last.pt",
            epoch=epoch,
            global_step=global_step,
            metrics=val_metrics,
            optimizer=optimizer,
            is_best=False
        )

        # Save tokenizer
        tokenizer_path = CHECKPOINT_DIR / "peserel0_tokenizer.json"
        self.tokenizer.save(str(tokenizer_path))

        report = {
            "training_duration_sec": round(total_duration, 2),
            "epochs_completed": len(history),
            "total_steps": global_step,
            "examples_per_sec": round(examples_per_sec, 2),
            "best_epoch": best_epoch,
            "best_val_metrics": best_metrics,
            "training_curves": history,
            "parameter_count": self.config.count_parameters(),
            "best_checkpoint_path": str(CHECKPOINT_DIR / "peserel0_best.pt"),
            "tokenizer_path": str(tokenizer_path),
        }

        # Save training report JSON
        with open(CHECKPOINT_DIR / "training_report.json", "w", encoding="utf-8") as f:
            import json
            json.dump(report, f, indent=2)

        return report

    def evaluate_loader(self, loader: DataLoader) -> Tuple[float, Dict[str, Any]]:
        """Evaluates model loss and metrics over a given DataLoader."""
        self.model.eval()
        total_loss = 0.0
        all_logits = []
        all_labels = []

        with torch.no_grad():
            for input_ids, token_type_ids, attention_mask, labels, _ in loader:
                input_ids = input_ids.to(self.device)
                token_type_ids = token_type_ids.to(self.device)
                attention_mask = attention_mask.to(self.device)
                labels = labels.to(self.device)

                loss, logits = self.model(input_ids, token_type_ids, attention_mask, labels=labels)
                total_loss += loss.item() * len(labels)

                all_logits.append(logits)
                all_labels.append(labels)

        avg_loss = total_loss / len(loader.dataset) if len(loader.dataset) > 0 else 0.0
        metrics = compute_metrics_from_logits(
            torch.cat(all_logits, dim=0),
            torch.cat(all_labels, dim=0)
        )
        return avg_loss, metrics

    def save_checkpoint(
        self,
        filepath: Path,
        epoch: int,
        global_step: int,
        metrics: Dict[str, Any],
        optimizer: torch.optim.Optimizer,
        is_best: bool = False
    ):
        """Saves a standalone reproducible checkpoint."""
        checkpoint_data = {
            "model_name": self.config.model_name,
            "architecture": self.config.architecture,
            "epoch": epoch,
            "global_step": global_step,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "config": self.config.model_dump(),
            "train_config": self.train_config.model_dump(),
            "tokenizer_metadata": self.tokenizer.metadata,
            "validation_metrics": metrics,
            "saved_at_utc": datetime.now(timezone.utc).isoformat(),
            "is_best": is_best
        }
        torch.save(checkpoint_data, filepath)

    @classmethod
    def load_model_from_checkpoint(
        cls,
        checkpoint_path: Path,
        device: str = "cpu"
    ) -> Tuple[PESERelationClassifier, RelationConfig, Dict[str, Any]]:
        """Loads and instantiates a model from a saved checkpoint."""
        checkpoint = torch.load(checkpoint_path, map_location=device)
        config = RelationConfig(**checkpoint["config"])
        model = PESERelationClassifier(config).to(device)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        return model, config, checkpoint
