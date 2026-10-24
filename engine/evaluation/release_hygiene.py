"""Readiness inventory with redacted findings; never publishes or reads private stores."""
import hashlib
import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path
from engine.evaluation.release_manifest import ROOT, source_manifest


def scan():
    categories=Counter();source_flags=[];credential_signatures=[]
    skipped={".tmp",".venv","node_modules",".next","__pycache__",".git"}
    for folder,dirs,files in os.walk(ROOT):
        dirs[:]=[d for d in dirs if d not in skipped]
        for name in files:
            path=Path(folder)/name;relative=path.relative_to(ROOT).as_posix()
            low=name.lower()
            if low.startswith(".env") and not low.endswith(".example"): categories["local_environment_files"]+=1
            if any(t in low for t in ("service-account","serviceaccount","firebase-adminsdk")) or path.suffix in {".pem",".key"}:
                categories["credential_filename_candidates"]+=1
            if relative.startswith("engine/data/") and (path.suffix in {".json",".jsonl",".db",".sqlite"} or "knowledge_corpus" in relative): categories["local_data_files_review_or_exclude"]+=1
            if path.suffix in {".pt",".pth"}: categories["checkpoint_files_exclude"]+=1
            if path.suffix in {".npy",".npz"}: categories["derived_vector_files_exclude"]+=1
    for row in source_manifest()["files"]:
        path=ROOT/row["path"]
        if path.suffix not in {".py",".ts",".tsx",".js",".ps1",".bat"}: continue
        text=path.read_text(encoding="utf-8")
        counts={"personal_name_references":len(re.findall(r"\byasir\b",text,re.I)),
                "absolute_user_path_references":len(re.findall(r"[A-Za-z]:[/\\]+Users[/\\]",text)),
                "private_store_references":text.count("firestore_documents.json")}
        if any(counts.values()): source_flags.append(dict(file=row["path"],counts=counts))
        signatures=[label for label,pattern in (("private_key_block",r"-----BEGIN (?:RSA )?PRIVATE KEY-----"),
                   ("google_api_key_shape",r"AIza[0-9A-Za-z_-]{30,}"),
                   ("service_account_private_key_assignment",r'"private_key"\s*:\s*"[^"\n]{20,}')) if re.search(pattern,text)]
        if signatures: credential_signatures.append(dict(file=row["path"],signatures=signatures))
    report=dict(status="NOT READY FOR BLIND WHOLE-FOLDER PUBLICATION",git_available=(ROOT/".git").exists(),
        categories=dict(categories),source_review_flags=source_flags,source_credential_signatures=credential_signatures,
        boundary="Default demo store/history/vectors are isolated; explicit demo startup uses synthetic data. Legacy seed and neural playground personal passage replaced with synthetic examples; originals preserved only under ignored .tmp.",
        required_before_publication=["Export an explicit source allowlist; never upload this entire working directory", "Review historical docs/evaluations and name references for publication consent", "Exclude all environment files, local stores/history, checkpoints, vectors, logs and .tmp", "Audit Git tracked files and history after creating a repository; none exists here", "Keep the unauthenticated CMS/API bound to loopback; public hosting requires a separate authentication review"],
        limits="Pattern scan is not proof that secrets never existed; private file contents were not copied into this report. No publication occurred.")
    target=ROOT/"docs/audit/phase2f-public-readiness.json";target.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({"status":report["status"],"categories":dict(categories),"source_flags":len(source_flags),"credential_signatures":len(credential_signatures)}))


def export_source(destination):
    """Isolated clean-install working copy, not a publication action."""
    destination=Path(destination).resolve()
    assert destination.is_relative_to((ROOT/".tmp").resolve())
    destination.mkdir(parents=True,exist_ok=True)
    manifest=source_manifest()
    for row in manifest["files"]:
        target=destination/row["path"];target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/row["path"],target)
    (destination/"source-manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest


if __name__=="__main__": scan()
