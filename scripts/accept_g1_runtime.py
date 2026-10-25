"""Real bundled Python/HTTP acceptance; only a marked disposable Brain is accepted.

Reports contain counts and safety booleans, never document bodies or credentials.
"""
import argparse
import hashlib
import json
import os
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

QUERIES = ("when did I buy my bicycle", "Japanese beginner roadmap", "Next.js server components vs client components",
           "PageRank internal linking", "japanise begnner roadmp", "PESE")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("install", type=Path)
    parser.add_argument("brain", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--legacy", action="store_true", help="Compare the preserved alpha.4 runtime without G1 endpoints")
    args = parser.parse_args()
    if not (args.brain / ".pese-disposable-fixture").is_file():
        parser.error("A marked disposable Brain is required.")
    args.install, args.brain = args.install.resolve(), args.brain.resolve()
    results = {"passed": False, "queries": [], "legacy_comparison": args.legacy}
    environment = {k:v for k,v in os.environ.items() if not k.startswith(("PESE_", "PYTHON"))}
    environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    token = secrets.token_hex(32)
    child = subprocess.Popen([str(args.install / "runtime/python/python.exe"), "-B", "-u", "-m", "engine.desktop.launcher"],
                             cwd=args.install, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    origin = None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def request(path, data=None, method=None, auth=True, timeout=120):
        headers = {"X-PESE-Token":token} if auth else {}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(origin + path, data=json.dumps(data).encode() if data is not None else None,
                                     headers=headers, method=method)
        with opener.open(req, timeout=timeout) as response:
            return json.load(response)
    try:
        child.stdin.write(json.dumps({"action":"serve", "brainPath":str(args.brain), "token":token}) + "\n")
        child.stdin.close()
        def read_port():
            nonlocal origin
            for line in child.stdout:
                if line.startswith("PESE_PORT "):
                    origin = "http://127.0.0.1:" + line.split()[1]
        reader = threading.Thread(target=read_port, daemon=True)
        reader.start()
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError("Bundled runtime exited before readiness.")
            try:
                if origin and request("/health", timeout=1)["status"] == "healthy":
                    break
            except OSError:
                pass
            time.sleep(.2)
        else:
            raise TimeoutError("Bundled runtime readiness timeout.")
        results["offline_boundary"] = request("/desktop/offline-check")["external_connections_blocked"]
        assert results["offline_boundary"]
        for index, query in enumerate(QUERIES):
            params = urllib.parse.urlencode({"q":query, "debug":"true"})
            primary = request("/api/search?" + params)
            assert primary["results"]
            discovery = urllib.parse.urlencode({"q":query, "search_id":primary["search_id"]})
            paa = request("/api/questions?" + discovery)
            related = request("/api/related?" + discovery)
            for item in paa["questions"]:
                verified = request("/api/search?" + urllib.parse.urlencode({"q":item["question"]}))["results"][0]
                assert verified["is_featured"] and verified["slug"] == item["source_slug"]
            results["queries"].append({"query_index":index+1, "results":len(primary["results"]), "paa":len(paa["questions"]),
                                       "related":len(related["related_searches"]), "featured":primary["results"][0]["is_featured"],
                                       "corrected":primary.get("has_corrections",False), "paa_gate_verified":True,
                                       "paa_evaluated":paa.get("total_candidates_evaluated",0)})
        first = request("/api/search?" + urllib.parse.urlencode({"q":QUERIES[0]}))["results"][0]
        request("/api/search/feedback", {"query":QUERIES[0], "target_type":"SERP_RESULT", "target_id":first["doc_id"], "feedback":"LIKE"})
        after = request("/api/search?" + urllib.parse.urlencode({"q":QUERIES[0]}))["results"]
        assert next(r for r in after if r["doc_id"] == first["doc_id"])["search_sync_adjustment"] == 2.0
        results["feedback_preserved"] = True
        for path, expected in (() if args.legacy else (("/api/sync/restore",409), ("/api/sync/now",401))):
            try:
                request(path, method="POST")
                raise AssertionError("Unsafe or unauthenticated sync operation accepted.")
            except urllib.error.HTTPError as error:
                assert error.code == expected
        assert request("/api/search?" + urllib.parse.urlencode({"q":QUERIES[0]}))["results"]
        if not args.legacy:
            results["search_survives_sync_rejection"] = True
        results["google_optional"] = True
        results["passed"] = True
    except Exception as error:
        results["error_type"] = type(error).__name__
    finally:
        if origin and child.poll() is None:
            try:
                request("/desktop/shutdown", method="POST", timeout=2)
                child.wait(timeout=8)
            except Exception:
                child.kill()
                child.wait(timeout=5)
        elif child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        results["engine_exited"] = child.poll() is not None
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
