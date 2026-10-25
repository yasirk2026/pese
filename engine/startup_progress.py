"""Content-free desktop readiness progress. Disabled for ordinary library callers."""
import json
import os
from contextlib import contextmanager
from contextvars import ContextVar

_phase = ContextVar("pese_embedding_phase", default="vectors")


def emit_progress(stage, completed=0, total=0):
    if os.environ.get("PESE_STARTUP_PROGRESS") == "1":
        print("PESE_STARTUP " + json.dumps({"stage": stage, "completed": int(completed), "total": int(total)}), flush=True)


@contextmanager
def embedding_phase(stage):
    token = _phase.set(stage)
    try:
        yield
    finally:
        _phase.reset(token)


def embedding_progress(completed, total):
    emit_progress(_phase.get(), completed, total)
