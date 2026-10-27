"""Create a fresh, explicitly marked public synthetic Brain for native acceptance."""
import argparse
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("path");args=p.parse_args();target=Path(args.path).resolve()
    target.mkdir(parents=True,exist_ok=False)
    os.environ.update(PESE_BRAIN_PATH=str(target),PESE_DATA_DIR=str(target),LOCALAPPDATA=str(target.parent/"fixture-profile"))
    from engine.brain import initialize_brain
    from engine.indexing.document import Document
    from engine.indexing.store import DocumentStore
    from engine.intelligence.beta.data import build_splits
    initialize_brain(target)
    store=DocumentStore(target/"firestore_documents.json")
    cases=build_splits()["validation"][:16]
    rows={row["id"]:row for case in cases for row in case["candidates"]}
    for i,row in enumerate(rows.values()):
        store.save_document(Document(id=row["id"],slug=f"fixture-{i}",title=row["text"].split('.')[0],content=row["text"],
                            created_at="2020-01-01T00:00:00Z",updated_at="2020-01-01T00:00:00Z"))
    (target/".pese-disposable-fixture").write_text("Original public synthetic N3-E acceptance data")
    (target/".pese-beta-query.txt").write_text(cases[0]["question"])
    (target/".pese-beta-queries.json").write_text(json.dumps([case["question"] for case in cases]))
    print(target)
