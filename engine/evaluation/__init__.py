"""
PESE Evaluation package: benchmark dataset, evaluation metrics, and runner.
"""

from .dataset import EVALUATION_DATASET
from .metrics import (
    reciprocal_rank,
    precision_at_k,
    recall_at_k,
    hit_at_k,
    passage_match_hit,
)
from .runner import run_evaluation, print_evaluation_summary

__all__ = [
    "EVALUATION_DATASET",
    "reciprocal_rank",
    "precision_at_k",
    "recall_at_k",
    "hit_at_k",
    "passage_match_hit",
    "run_evaluation",
    "print_evaluation_summary",
]
