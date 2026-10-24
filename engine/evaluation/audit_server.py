"""Factory for a disposable local-only HTTP audit service."""
import os
from pathlib import Path


def create_app():
    from engine.api import main
    from engine.indexing.store import DocumentStore
    from engine.semantic.index import VectorIndex
    root=Path(os.environ["PESE_AUDIT_ROOT"]).resolve()
    workspace=Path(__file__).resolve().parents[2]
    if not root.is_relative_to((workspace/".tmp").resolve()):
        raise ValueError("Audit service must use an isolated workspace temporary directory")
    main.store=DocumentStore(storage_path=root/"documents.json")
    main.vector_index=VectorIndex(index_dir=root/"vectors")
    (root/"boot-id.txt").write_text(main.BOOT_ID)
    return main.app
