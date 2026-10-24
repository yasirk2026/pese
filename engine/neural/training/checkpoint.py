"""
PESE Neural Genesis: Checkpoint Management
Saves and restores model weights, optimizer states, hyperparameters, and training histories.
Ensures checkpoints are stored in gitignored locations.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import torch
from torch.torch_version import TorchVersion

from ..configs.model_config import TransformerConfig, QAConfig
from ..models.transformer import PESETransformer
from ..models.qa_reader import PESEQAReader


DEFAULT_CHECKPOINT_DIR = Path(__file__).resolve().parent.parent / "checkpoints"
DEFAULT_QA_CHECKPOINT_DIR = DEFAULT_CHECKPOINT_DIR / "qa"


def save_checkpoint(
    model: torch.nn.Module,
    optimizer: Optional[torch.optim.Optimizer],
    config: Dict[str, Any],
    step: int,
    loss: float,
    metrics: Optional[Dict[str, Any]] = None,
    checkpoint_dir: Optional[Path] = None,
    filename: Optional[str] = None
) -> Path:
    """
    Saves complete training state to disk.
    """
    chk_dir = Path(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
    chk_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        filename = f"{config.get('model_name', 'model')}_step{step}.pt"

    filepath = chk_dir / filename

    checkpoint_data = {
        "model_name": config.get("model_name", "PESE-NG-0"),
        "model_config": config,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict() if optimizer is not None else None,
        "step": step,
        "loss": float(loss),
        "metrics": metrics or {},
        "saved_at": datetime.utcnow().isoformat() + "Z",
        "pytorch_version": torch.__version__,
    }

    torch.save(checkpoint_data, str(filepath))
    return filepath


def load_checkpoint(
    filepath: Path,
    device: str = "cpu"
) -> Tuple[torch.nn.Module, Dict[str, Any]]:
    """
    Loads model and metadata from a saved checkpoint file.
    Automatically detects whether it is a PESETransformer (LM) or PESEQAReader (QA).
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Checkpoint file not found: {filepath}")

    # Older local checkpoints stored torch.__version__ as a TorchVersion
    # string subclass. Permit that one metadata type, not arbitrary pickle code.
    with torch.serialization.safe_globals([TorchVersion]):
        checkpoint_data = torch.load(str(filepath), map_location=device, weights_only=True)

    raw_cfg = checkpoint_data.get("model_config", {})
    model_name = checkpoint_data.get("model_name", "") or raw_cfg.get("model_name", "")

    if "QA" in model_name:
        cfg = QAConfig(**raw_cfg)
        model = PESEQAReader(cfg)
    else:
        cfg = TransformerConfig(**raw_cfg)
        model = PESETransformer(cfg)

    model.load_state_dict(checkpoint_data["model_state_dict"])
    model.to(device)
    model.eval()

    return model, checkpoint_data


def list_checkpoints(checkpoint_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Lists available saved checkpoints and their metadata.
    """
    chk_dir = Path(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
    if not chk_dir.exists():
        return []

    results = []
    for f in chk_dir.rglob("*.pt"):
        try:
            with torch.serialization.safe_globals([TorchVersion]):
                data = torch.load(str(f), map_location="cpu", weights_only=True)
            results.append({
                "filename": f.name,
                "filepath": str(f),
                "model_name": data.get("model_name", "unknown"),
                "step": data.get("step", 0),
                "loss": data.get("loss", 0.0),
                "saved_at": data.get("saved_at", ""),
                "size_bytes": f.stat().st_size,
            })
        except Exception as e:
            results.append({
                "filename": f.name,
                "filepath": str(f),
                "error": str(e)
            })

    # Sort descending by step
    results.sort(key=lambda x: x.get("step", 0), reverse=True)
    return results
