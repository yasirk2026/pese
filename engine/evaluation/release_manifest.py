"""Named source freeze without Git; excludes runtime/private data and reports."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def source_manifest():
    files=[]
    for path in (ROOT/"engine").rglob("*.py"):
        relative=path.relative_to(ROOT)
        if any(part in {".venv","__pycache__","private","downloaded","checkpoints"} for part in relative.parts): continue
        files.append(path)
    files.extend(p for p in (ROOT/"web/src").rglob("*") if p.is_file())
    files.extend(p for p in (ROOT/"scripts").rglob("*") if p.is_file() and p.suffix in {".py",".ps1",".bat"})
    files.extend(p for p in (ROOT/"web").iterdir() if p.is_file() and p.name in {"package.json","package-lock.json","tsconfig.json","next.config.ts","eslint.config.mjs","postcss.config.mjs"})
    files.extend(ROOT/name for name in ("requirements.txt","requirements.lock.txt","requirements-dev.txt",".env.example",".gitignore","pytest.ini"))
    rows=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(set(files))]
    digest=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
    return dict(name="PESE Phase 2 — Search Intelligence Baseline",version="2.0.0-rc.2",sha256=digest,files=rows,
        excluded="Private/runtime stores, histories, environment files, model checkpoints, caches, dependencies, reports and holdout data. Provider/checkpoint identities are recorded separately by evaluations.")


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--output");parser.add_argument("--verify")
    args=parser.parse_args();manifest=source_manifest()
    if args.verify:
        expected=json.loads(Path(args.verify).read_text(encoding="utf-8"))["sha256"]
        assert expected==manifest["sha256"],"Source changed after freeze"
    if args.output: Path(args.output).write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(manifest["sha256"])
