"""Recover a marked synthetic native fixture; never opens an owner Brain."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture");parser.add_argument("output")
    args=parser.parse_args();brain=Path(args.fixture).resolve();output=Path(args.output).resolve()
    if not (brain/".pese-disposable-fixture").is_file():parser.error("Marked synthetic fixture required")
    if output==ROOT or ROOT in output.parents or output==brain or brain in output.parents:
        parser.error("New output must be outside application and Brain")
    output.mkdir(parents=True,exist_ok=False)
    os.environ.update(PESE_BRAIN_PATH=str(brain),PESE_DATA_DIR=str(brain),LOCALAPPDATA=str(output/"profile"))
    sys.path.insert(0,str(ROOT))
    from engine.sync.snapshot import create_snapshot
    from engine.sync.restore import restore_snapshot
    before=hashlib.sha256((brain/"firestore_documents.json").read_bytes()).hexdigest()
    bundle=create_snapshot(brain,output/"backups")
    with zipfile.ZipFile(bundle.zip_path) as archive:
        assert not any("intelligence" in n or "weights.pt" in n or "learning.db" in n for n in archive.namelist())
    recovered=output/"inactive-recovery"
    restore_snapshot(bundle.zip_path,recovered,expected_brain_id=bundle.brain_id,
                     expected_snapshot_id=bundle.snapshot_id,expected_zip_sha256=bundle.zip_sha256)
    after=hashlib.sha256((recovered/"firestore_documents.json").read_bytes()).hexdigest()
    assert before==after and not (recovered/".pese-intelligence-v1").exists()
    receipt={"passed":True,"synthetic_only":True,"snapshot_id":bundle.snapshot_id,
        "zip_sha256":bundle.zip_sha256,"documents_sha256":before,"restored_documents_identical":True,
        "experimental_sidecar_excluded":True,"owner_brain_opened":False,"remote_drive_used":False}
    (output/"verification.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt))

if __name__=="__main__":main()
