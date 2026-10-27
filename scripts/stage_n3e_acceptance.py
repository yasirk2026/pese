"""Fresh native acceptance stage using known release runtime assets, no Brain."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--reference",required=True);p.add_argument("--stage",required=True)
    args=p.parse_args();reference=Path(args.reference).resolve();stage=Path(args.stage).resolve()
    if stage==ROOT or ROOT in stage.parents or reference==stage:p.error("Use a fresh external stage")
    stage.mkdir(parents=True,exist_ok=False)
    for name in ("runtime","models"):
        shutil.copytree(reference/name,stage/name,ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    from scripts.stage_desktop import tracked_engine_sources
    for source in tracked_engine_sources(ROOT):
        relative=source.relative_to(ROOT)
        if any(part in ("tests",".venv","__pycache__","private") for part in relative.parts):continue
        destination=stage/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
    for name in ("engine/neural/checkpoints","engine/neural/data/pese_rel_data_0"):
        shutil.copytree(reference/name,stage/name)
    for name in ("neural_genesis_report.json","qa_experiment_report.json"):
        destination=stage/"engine/data"/name;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(reference/"engine/data"/name,destination)
    shutil.copytree(ROOT/"engine/neural/assets",stage/"engine/neural/assets",ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    shutil.copytree(ROOT/"web/out",stage/"ui")
    shutil.copy2(ROOT/"requirements.lock.txt",stage/"requirements.lock.txt")
    shutil.copy2(reference/"runtime-manifest.json",stage/"runtime-manifest.json")
    from engine.app_version import application_version
    subprocess.check_call([sys.executable,str(ROOT/"scripts/source_provenance.py"),str(stage),application_version(ROOT),"--acceptance-only"])
    if list(stage.rglob("pese-brain.json")):raise RuntimeError("Stage unexpectedly contains a Brain")
    print(stage)
