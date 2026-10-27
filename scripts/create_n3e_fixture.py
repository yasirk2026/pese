"""Create a fresh, explicitly marked public synthetic Brain for native acceptance."""
import argparse
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("path");p.add_argument("--count",type=int,default=48);args=p.parse_args();target=Path(args.path).resolve()
    if args.count not in (2,48,200,400):p.error("Use an explicit synthetic fixture size: 2, 48, 200 or 400")
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
    for i,row in enumerate(list(rows.values())[:args.count]):
        store.save_document(Document(id=row["id"],slug=f"fixture-{i}",title=row["text"].split('.')[0],content=row["text"],
                            created_at="2020-01-01T00:00:00Z",updated_at="2020-01-01T00:00:00Z"))
    for i in range(len(list(rows.values())[:args.count]),args.count):
        topic=("physics","biology","geometry","chemistry","astronomy","geography","electricity","ecology")[i%8]
        study="\n\n".join(f"## {topic.capitalize()} study {i}, section {section}\nThis original synthetic educational material describes classroom {topic}. A student records observations, compares a control sample with a measured sample, and writes the units beside each result. The measurement number is {i+section}. A fair comparison keeps the conditions fixed. Repeating observations can reveal measurement errors. The learner lists the method, explains what was measured, and distinguishes an observation from an assumption. This passage is fictional public test material and contains no real personal information." for section in range(1,6))
        store.save_document(Document(id=f"synthetic-study-{i}",slug=f"synthetic-study-{i}",title=f"Public science study {i}",
            content=study,
            created_at="2020-01-01T00:00:00Z",updated_at="2020-01-01T00:00:00Z"))
    (target/".pese-disposable-fixture").write_text("Original public synthetic N3-E acceptance data")
    (target/".pese-beta-query.txt").write_text(cases[0]["question"])
    (target/".pese-beta-queries.json").write_text(json.dumps([case["question"] for case in cases]))
    print(target)
