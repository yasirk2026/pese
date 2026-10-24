"""
PESE Engine: Global Runtime Configuration & Authoritative Brain Path Binding
"""

import os
from pathlib import Path
from .brain.resolver import resolve_brain_path

DATA_ROOT = Path(__file__).resolve().parent / "data"
DEMO = os.getenv("PESE_PROFILE", "private") == "demo"

# Authoritative Brain root resolution via PESE Brain subsystem
if DEMO and not (os.getenv("PESE_DATA_DIR") or os.getenv("PESE_BRAIN_PATH")):
    RUNTIME_ROOT = (DATA_ROOT / "demo_runtime").resolve()
else:
    RUNTIME_ROOT = resolve_brain_path(allow_dev_fallback=True)

BACKEND = os.getenv("PESE_STORAGE_BACKEND", "local")
if BACKEND not in {"local", "firestore"}:
    raise ValueError("PESE_STORAGE_BACKEND must be local or firestore")
