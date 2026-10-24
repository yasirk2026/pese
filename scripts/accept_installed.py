"""Non-GUI installed acceptance: isolated PATH, real assets, offline networking.

Use only a disposable Brain copy. No production document is edited or removed.
"""
import argparse
import json
import os
import secrets
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def discard_output(stream):
    for _ in stream:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("install", type=Path)
    parser.add_argument("brain", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--verify-reinstall", action="store_true")
    parser.add_argument("--cleanup-fixtures", action="store_true")
    parser.add_argument("--cleanup-ui-fixture", action="store_true")
    parser.add_argument("--source-reference", type=Path,
                        help="Separate integration comparison against current frozen source; does not pass the fixed-score contract.")
    args = parser.parse_args()
    results = {}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    child = None
    token = secrets.token_hex(32)
    origin = None
    output_reader = None

    def request(path, body=None, method=None, authenticated=True, headers=None, timeout=120):
        request_headers = dict(headers or {})
        if authenticated:
            request_headers["X-PESE-Token"] = token
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        req = urllib.request.Request(origin + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers=request_headers, method=method)
        with opener.open(req, timeout=timeout) as response:
            data = response.read()
            return json.loads(data) if "json" in response.headers.get("Content-Type", "") else data

    def start():
        nonlocal child, origin, token, output_reader
        token = secrets.token_hex(32)
        environment = {k: v for k, v in os.environ.items() if not k.startswith(("PESE_", "PYTHON"))}
        environment["PATH"] = os.path.join(os.environ["SystemRoot"], "System32")
        child = subprocess.Popen([str(args.install / "runtime/python/python.exe"), "-B", "-u", "-m", "engine.desktop.launcher"],
                                 cwd=args.install, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
        child.stdin.write(json.dumps({"action": "serve", "brainPath": str(args.brain), "token": token}) + "\n")
        child.stdin.flush()
        child.stdin.close()
        while True:
            line = child.stdout.readline()
            if line.startswith("PESE_PORT "):
                origin = "http://127.0.0.1:" + line.split()[1]
                break
            if not line or line.startswith('{"ok": false'):
                raise RuntimeError("Installed runtime failed: " + line[:400])
        # Match the production host: keep draining engine diagnostics so the
        # finite Windows stdout pipe cannot block CMS rebuilds or shutdown.
        output_reader = threading.Thread(target=discard_output, args=(child.stdout,), daemon=True)
        output_reader.start()
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError("Installed runtime stopped before readiness")
            try:
                health = request("/health")
                if health["status"] == "healthy":
                    return health
            except (OSError, urllib.error.URLError):
                time.sleep(.2)
        raise RuntimeError("Readiness timeout")

    def stop():
        nonlocal child, output_reader
        if child is None:
            return
        forced = False
        try:
            response = request("/desktop/shutdown", method="POST", timeout=2)
            assert response["stopping"]
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # The product contract explicitly includes bounded forced
                # cleanup. Test persistence after that path as well.
                forced = True
                child.kill()
                child.wait(timeout=5)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            if output_reader is not None:
                output_reader.join(timeout=2)
                output_reader = None
            child.stdout.close()
            child = None
        with sqlite3.connect((args.brain / "search_sync_feedback.db").resolve().as_uri() + "?mode=ro", uri=True) as database:
            assert database.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        json.loads((args.brain / "firestore_documents.json").read_text(encoding="utf-8"))
        results.setdefault("shutdown_cycles", []).append({"graceful_request_acknowledged": True,
            "forced_after_grace_window": forced, "database_integrity": "ok", "canonical_json_valid": True})

    def search():
        data = request("/api/search?q=when%20did%20I%20buy%20my%20bicycle&debug=true")
        top = data["results"][0]
        return {"slug": top["slug"], "score": top["final_score"], "answer": top["featured_answer"],
                "semantic_similarity": top["semantic_similarity"], "evidence_gate": top["trace"]["evidence_gate_passed"],
                "adjustment": top["search_sync_adjustment"]}

    try:
        identity = json.loads((args.brain / "pese-brain.json").read_text(encoding="utf-8"))["brainId"]
        results["brainId"] = identity
        results["health"] = start()
        results["system_python_and_node_removed_from_child_PATH"] = True
        results["offline"] = request("/desktop/offline-check")
        assert results["offline"]["external_connections_blocked"]
        if args.cleanup_ui_fixture:
            fixture = request("/api/documents/pese-desktop-ui-acceptance")
            assert fixture["title"] == "PESE Desktop UI Acceptance"
            assert fixture["content"] == "This disposable draft was reopened, edited, and saved in installed PESE."
            request("/api/documents/pese-desktop-ui-acceptance", method="DELETE")
            results["ui_fixture_removed_through_product_api"] = True
            results["passed"] = True
            return
        for path in ("/health", "/api/stats", "/api/documents", "/desktop/shutdown"):
            try:
                request(path, method="POST" if path.endswith("shutdown") else None, authenticated=False)
                raise AssertionError("Unauthenticated endpoint was accepted")
            except urllib.error.HTTPError as exc:
                assert exc.code == 401
        results["unauthenticated_requests_rejected"] = True
        for path in ("/", "/search/", "/admin/", "/admin/new/", "/admin/edit/", "/admin/eval/", "/admin/neural-lab/", "/doc/"):
            assert b"<html" in request(path)
        results["static_routes"] = "8/8 served"
        for path in ("/docs", "/openapi.json"):
            try:
                request(path)
                raise AssertionError("Development API docs exposed")
            except urllib.error.HTTPError as exc:
                assert exc.code == 404
        results["canonical"] = search()
        expected_base = 39.6136
        if args.source_reference:
            reference = json.loads(args.source_reference.read_text(encoding="utf-8"))
            assert all(reference["frozen_source_hash_matches"].values())
            expected_base = reference["source_base_score"]
            results["acceptance_scope"] = "Installed integration against current unmodified source"
        expected_score = round(expected_base + (2.0 if args.verify_reinstall else 0.0), 4)
        results["fixed_score_contract_passed"] = results["canonical"]["score"] == (41.6136 if args.verify_reinstall else 39.6136)
        assert results["canonical"] == {"slug": "my-bicycle-story", "score": expected_score, "answer": "17 March 2024",
                                         "semantic_similarity": .8361, "evidence_gate": True,
                                         "adjustment": 2.0 if args.verify_reinstall else 0.0}
        results["autocomplete_count"] = len(request("/api/suggest?q=bicy")["suggestions"])
        results["related"] = bool(request("/api/related?q=when%20did%20I%20buy%20my%20bicycle"))
        results["paa"] = bool(request("/api/questions?q=when%20did%20I%20buy%20my%20bicycle"))
        results["neural_checkpoints"] = len(request("/api/neural/checkpoints")["checkpoints"])
        generated = request("/api/neural/generate", {"prompt": "PESE is", "max_new_tokens": 5, "temperature": 0.0, "top_k": 5})
        results["neural_inference"] = generated
        assert generated
        results["qa_inference"] = request("/api/neural/qa/read", {
            "question": "When did LUMEN launch?", "passage": "Nora created LUMEN. LUMEN launched in 2025."})
        assert results["qa_inference"]["model"] == "PESE-QA-0"
        if not args.verify_reinstall:
            request("/api/search/feedback", {"query": "when did I buy my bicycle", "target_type": "SERP_RESULT",
                    "target_id": "my-bicycle-story", "target_slug": "my-bicycle-story", "rank_position": 1, "feedback": "LIKE"})
            results["search_sync"] = search()
            assert results["search_sync"]["score"] == round(expected_base + 2.0, 4)
            assert results["search_sync"]["adjustment"] == 2.0
            fixture = {"id": "pese-desktop-disposable-acceptance", "slug": "pese-desktop-disposable-acceptance",
                       "title": "Desktop acceptance fixture", "content": "A disposable acceptance document.", "status": "draft"}
            request("/api/documents", fixture)
            fixture["content"] = "The disposable acceptance document was edited and persisted."
            request("/api/documents", fixture)
            assert request("/api/documents/" + fixture["slug"])["content"] == fixture["content"]
            results["cms_create_edit"] = True
            stop()
            start()
            assert request("/api/documents/" + fixture["slug"])["content"] == fixture["content"]
            assert search()["score"] == round(expected_base + 2.0, 4)
            results["restart_persistence"] = True
            # Keep the draft fixture and LIKE through actual uninstall/reinstall.
        else:
            fixture = request("/api/documents/pese-desktop-disposable-acceptance")
            assert fixture["content"] == "The disposable acceptance document was edited and persisted."
            results["cms_survived_uninstall_reinstall"] = True
            assert request("/api/search/feedback?q=when%20did%20I%20buy%20my%20bicycle")
            results["preferences_survived_uninstall_reinstall"] = True
            assert json.loads((args.brain / "pese-brain.json").read_text(encoding="utf-8"))["brainId"] == identity
            if args.cleanup_fixtures:
                # Only the explicitly disposable acceptance copy is eligible.
                assert args.brain.parent == Path(r"D:\PESE Desktop Acceptance\2026-10-24")
                request("/api/documents/pese-desktop-disposable-acceptance", method="DELETE")
                request("/api/search/feedback", method="DELETE")
                results["after_disposable_fixture_cleanup"] = search()
                assert results["after_disposable_fixture_cleanup"]["score"] == expected_base
        results["passed"] = True
    except Exception as exc:
        results["passed"] = False
        results["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        stop()
        args.report.write_text(json.dumps(results, indent=2, ensure_ascii=True), encoding="utf-8")


if __name__ == "__main__":
    main()
