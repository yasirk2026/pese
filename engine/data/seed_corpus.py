"""Compatibility seed entry point. Only synthetic public documents ship by default."""
from .demo_corpus import demo_documents, seed_demo
from ..indexing.store import DocumentStore

SEED_DOCUMENTS = [d.model_dump() for d in demo_documents()]


def seed_corpus(store=None):
    return seed_demo(store or DocumentStore())
