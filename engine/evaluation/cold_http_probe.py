"""Measure fresh API readiness and first HTTP requests; leave user server alone."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import httpx


def run():
    workspace=Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="cold-http-",dir=workspace/".tmp") as directory:
        root=Path(directory)
        shutil.copyfile(workspace/"engine/data/firestore_documents.json",root/"documents.json")
        (root/"vectors").mkdir()
        shutil.copyfile(workspace/"engine/data/semantic_index/cache_store.npz",root/"vectors/cache_store.npz")
        env=dict(os.environ,PESE_AUDIT_ROOT=str(root))
        env.pop("GOOGLE_APPLICATION_CREDENTIALS",None)
        env.pop("FIRESTORE_EMULATOR_HOST",None)
        start=time.perf_counter()
        with (root/"server.log").open("w",encoding="utf-8") as log:
            process=subprocess.Popen([sys.executable,"-m","uvicorn","engine.evaluation.audit_server:create_app","--factory","--host","127.0.0.1","--port","8001","--no-access-log"],cwd=workspace,env=env,stdout=log,stderr=log,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            try:
                with httpx.Client(base_url="http://127.0.0.1:8001",timeout=3,trust_env=False) as client:
                    while True:
                        if process.poll() is not None:raise RuntimeError("Disposable API exited before readiness")
                        if time.perf_counter()-start>90:raise TimeoutError("Disposable API failed readiness budget")
                        try:
                            health=client.get("/health").json()
                            if (root/"boot-id.txt").exists() and health.get("boot_id")== (root/"boot-id.txt").read_text():break
                        except (httpx.HTTPError,ValueError):pass
                        time.sleep(.1)
                    ready_ms=round((time.perf_counter()-start)*1000,2)
                    rows=[]
                    for q in ["when did japan enter ww2","when did japan enter ww2","does healing lounge offer flexible payments"]:
                        t=time.perf_counter();data=client.get("/api/search",params={"q":q}).json()
                        rows.append(dict(query=q,http_ms=round((time.perf_counter()-t)*1000,2),engine_ms=data["took_ms"],timing=data["timing"]))
                report=dict(readiness_ms=ready_ms,requests=rows,notes="Fresh single-worker API; preexisting vector cache and installed model files; both models prewarmed in lifespan. No network model download. User port 8000 unchanged.")
                (workspace/"docs/audit/cold-http.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
                print(json.dumps(report,indent=2))
            finally:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=="__main__":run()
