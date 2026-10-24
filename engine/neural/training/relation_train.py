"""
PESE Neural Genesis: PESE-Rel-0 Training CLI Entrypoint
Phase N2: Reproducible Model Training Command

Usage:
  python -m engine.neural.training.relation_train [--epochs 25] [--batch-size 16] [--lr 3e-4] [--seed 42]
"""

import argparse
from typing import Dict, Any

from ..configs.model_config import RelationConfig, RelationTrainingConfig
from .relation_trainer import RelationTrainer


def main() -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description="Train PESE-Rel-0 Relation Cross-Encoder")
    parser.add_argument("--epochs", type=int, default=25, help="Maximum training epochs")
    parser.add_argument("--batch-size", type=int, default=16, help="Training batch size")
    parser.add_argument("--lr", type=float, default=3e-4, help="Peak learning rate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--skip-micro", action="store_true", help="Skip initial micro-overfit test")

    args = parser.parse_args()

    model_cfg = RelationConfig()
    train_cfg = RelationTrainingConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        random_seed=args.seed
    )

    trainer = RelationTrainer(config=model_cfg, train_config=train_cfg)

    if not args.skip_micro:
        micro_report = trainer.run_micro_overfit()
        if not micro_report["converged"]:
            raise RuntimeError(f"Micro-overfit verification failed! Loss drop: {micro_report['loss_drop_pct']}%")

    report = trainer.train()
    print("\nTraining complete! Summary:")
    print(f"Total Epochs: {report['epochs_completed']}")
    print(f"Duration: {report['training_duration_sec']}s")
    print(f"Throughput: {report['examples_per_sec']} examples/sec")
    print(f"Best Validation F1: {report['best_val_metrics']['f1']} (Epoch {report['best_epoch']})")
    print(f"Saved Checkpoint: {report['best_checkpoint_path']}")
    return report


if __name__ == "__main__":
    main()
