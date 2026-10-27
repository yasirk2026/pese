"""Reproducible N3 verification without opening the user's Brain.

Use an existing PESE CPU Python runtime. --workspace must be a NEW directory
outside the application checkout. --model-path is an existing packaged BGE
snapshot directory (model_optimized.onnx plus tokenizer files), never a URL.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace",required=True)
    parser.add_argument("--model-path",required=True)
    args=parser.parse_args()
    work=Path(args.workspace).resolve()
    if work == ROOT or ROOT in work.parents:
        parser.error("Synthetic Brains must be outside the application directory")
    model=Path(args.model_path).resolve()
    if not (model/"model_optimized.onnx").is_file():
        parser.error("Existing local BGE assets required; downloads are forbidden")
    work.mkdir(parents=True,exist_ok=False)
    for name in ("Brain","LocalAppData","temp"):
        (work/name).mkdir()
    os.environ.update(PESE_BRAIN_PATH=str(work/"Brain"),PESE_DATA_DIR=str(work/"Brain"),
                      LOCALAPPDATA=str(work/"LocalAppData"),TEMP=str(work/"temp"),TMP=str(work/"temp"),
                      PESE_PROFILE="private",PESE_ENV="development",PESE_FASTEMBED_MODEL_PATH=str(model),
                      HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",HF_HUB_DISABLE_TELEMETRY="1",
                      NEXT_TELEMETRY_DISABLED="1")
    tempfile.tempdir=None
    sys.path.insert(0,str(ROOT))
    os.chdir(ROOT)
    from engine.brain import initialize_brain
    initialize_brain(work/"Brain",name="N3 synthetic verification")
    import pytest
    class Receipt:
        def pytest_sessionfinish(self,session,exitstatus):
            stats=session.config.pluginmanager.get_plugin("terminalreporter").stats
            receipt={"version":1,"exit_code":int(exitstatus),"passed":len(stats.get("passed",[])),
                     "failed":len(stats.get("failed",[])),"errors":len(stats.get("error",[])),
                     "skipped":len(stats.get("skipped",[])),"offline":True,"synthetic_brain":True}
            (work/"verification.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    return pytest.main(["engine/tests","host/tests","-q", "--basetemp="+str(work/"pytest"),
                        "--junitxml="+str(work/"results.xml")],plugins=[Receipt()])


if __name__ == "__main__":
    raise SystemExit(main())
