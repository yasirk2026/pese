"""Owner-local BETA artifacts. Never accepted by the signed production verifier."""
import hashlib
import json
from pathlib import Path
import shutil
import time
from ..evidence import digest
from ..model_release import ApprovedModel
from ...brain.atomic import atomic_write_json


def bundle(directory,*,brain_binding=None,base_pin=None):
    root=Path(directory)
    manifest=json.loads((root/"beta-model.json").read_text(encoding="utf-8"))
    if (manifest.get("format")!="pese-owner-local-beta" or manifest.get("version")!=1 or
            manifest.get("objective")!="retrieval_relevance" or manifest.get("policy")!="aggressive_learning_beta"):
        raise ValueError("Invalid local BETA contract")
    if manifest.get("origin")=="local_adaptation":
        if not brain_binding or manifest.get("brain_binding")!=brain_binding:raise ValueError("Wrong Brain adaptation")
        if not manifest.get("evaluation_hash") or not manifest.get("training_hash"):raise ValueError("Missing candidate provenance")
    elif manifest.get("origin")=="public_synthetic_base":
        if base_pin is None or manifest["files"]!=base_pin:raise ValueError("Base model differs from application pin")
    else:raise ValueError("Unsupported local model origin")
    if set(manifest["files"])!={"weights.pt","tokenizer.json"}:raise ValueError("Artifact inventory")
    for name,expected in manifest["files"].items():
        file=root/name
        if file.is_symlink() or not 0<file.stat().st_size<=16*1024*1024 or hashlib.sha256(file.read_bytes()).hexdigest()!=expected:
            raise ValueError("Artifact integrity failure")
    return ApprovedModel(root,manifest["model_id"],manifest["files"]["weights.pt"],manifest["files"]["tokenizer.json"],.03,.75)


def write_manifest(directory,*,identity,origin,brain_binding=None,evaluation=None,training=None,lineage=None):
    root=Path(directory)
    manifest={"format":"pese-owner-local-beta","version":1,"policy":"aggressive_learning_beta",
       "objective":"retrieval_relevance","model_id":identity,"origin":origin,"created":time.time(),
       "brain_binding":brain_binding,"files":{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ("weights.pt","tokenizer.json")},
       "evaluation_hash":digest(evaluation) if evaluation else None,"training_hash":digest(training) if training else None,
       "training_lineage":sorted(set(lineage or []))}
    atomic_write_json(root/"beta-model.json",manifest)
    return manifest


class LocalModels:
    def __init__(self,root,brain_binding,base_path,base_pin):
        self.root=Path(root);self.binding=brain_binding;self.base_path=Path(base_path);self.pin=base_pin

    def base(self):return bundle(self.base_path,base_pin=self.pin)

    def current(self):
        pointer=self.root/"active.json"
        if not pointer.exists():return self.base()
        data=json.loads(pointer.read_text(encoding="utf-8"));name=data["current"]
        if name=="base":return self.base()
        if len(name)!=64 or any(c not in "0123456789abcdef" for c in name):raise ValueError("Invalid local model pointer")
        return bundle(self.root/"models"/name,brain_binding=self.binding)

    def promote(self,candidate,evaluation,healthcheck):
        if evaluation.get("decision")!="promote":raise ValueError("Candidate has not passed local promotion gates")
        candidate=Path(candidate)
        model=bundle(candidate,brain_binding=self.binding)
        manifest=json.loads((candidate/"beta-model.json").read_text(encoding="utf-8"))
        if manifest.get("evaluation_hash")!=digest(evaluation) or evaluation.get("candidate_checkpoint")!=model.checkpoint_hash:
            raise ValueError("Promotion evaluation does not bind this exact candidate")
        if not healthcheck(model):raise ValueError("Candidate health check failed")
        name=hashlib.sha256((candidate/"beta-model.json").read_bytes()).hexdigest()
        destination=self.root/"models"/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        if not destination.exists():shutil.copytree(candidate,destination)
        bundle(destination,brain_binding=self.binding)
        pointer=self.root/"active.json"
        previous=json.loads(pointer.read_text())["current"] if pointer.exists() else "base"
        if previous==name:return self.current()
        atomic_write_json(pointer,{"version":1,"current":name,"previous":previous,"evaluation_hash":digest(evaluation)})
        return self.current()

    def rollback(self):
        pointer=self.root/"active.json"
        data=json.loads(pointer.read_text(encoding="utf-8"))
        previous=data.get("previous")
        if previous is None:raise ValueError("No previous checkpoint")
        if previous!="base":
            if len(previous)!=64 or any(c not in "0123456789abcdef" for c in previous):raise ValueError("Invalid rollback pointer")
            bundle(self.root/"models"/previous,brain_binding=self.binding)
        else:self.base()
        atomic_write_json(pointer,{"version":1,"current":previous,"previous":data["current"]})
        return self.current()
