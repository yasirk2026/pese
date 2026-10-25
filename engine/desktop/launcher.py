"""Private embedded-CPython entry point. One JSON command arrives on stdin.

No PATH interpreter, token on command line, persisted secret, or dev fallback.
The socket stays bound from OS allocation through Uvicorn ownership.
"""
import json
import os
import socket
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]


def require_user_storage(path):
    """Velopack replaces current/ but uninstalls its entire enclosing app tree."""
    target = Path(path).resolve()
    install_root = APP_ROOT
    if APP_ROOT.name.lower() == "current" and (APP_ROOT.parent / "Update.exe").is_file():
        install_root = APP_ROOT.parent
    if target == install_root or install_root in target.parents:
        raise ValueError("Choose a Brain folder outside the PESE installation. Application uninstall must never own your Brain files.")


def validate_brain(path):
    require_user_storage(path)
    from engine.brain import open_brain
    from engine.brain.contracts import BrainIdentity, BrainInvalidError
    info = open_brain(path)
    root = Path(info.path)
    try:
        BrainIdentity.model_validate_json((root / "pese-brain.json").read_text(encoding="utf-8"))
        required = ("firestore_documents.json", "privacy_settings.json", "search_sync_feedback.db", "behavioural_events.jsonl")
        for name in required:
            if not (root / name).is_file():
                raise ValueError(f"Missing required Brain file: {name}")
        docs = json.loads((root / required[0]).read_text(encoding="utf-8"))
        settings = json.loads((root / required[1]).read_text(encoding="utf-8"))
        if not isinstance(docs, dict) or not isinstance(settings, dict):
            raise ValueError("Brain documents and privacy settings must be JSON objects")
        import sqlite3
        with sqlite3.connect((root / required[2]).as_uri() + "?mode=ro", uri=True) as db:
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Search Sync database integrity check failed")
            # Reject the obsolete D0-C laboratory schema, without silent migration.
            columns = {row[1] for row in db.execute("PRAGMA table_info(active_preferences)")}
            shadow = {row[1] for row in db.execute("PRAGMA table_info(neural_shadow_observations)")}
            if not {"metadata_json", "normalized_query", "target_id"} <= columns or not {"search_context_id", "target_id"} <= shadow:
                raise ValueError("This Brain's Search Sync schema is incompatible. No data was changed. Use a compatible Brain or contact support.")
    except Exception as exc:
        raise BrainInvalidError(root, str(exc)) from exc
    return info


def brain_command(command):
    from engine.brain import initialize_brain
    from engine.brain.resolver import save_desktop_brain_pointer
    action = command["action"]
    path = Path(command["brainPath"]).resolve()
    require_user_storage(path)
    if action == "create":
        if path.exists() and any(path.iterdir()):
            raise ValueError("This folder is not empty. Choose an empty folder or a new PESE Brain subfolder.")
        initialize_brain(path, name="Local Brain")
    info = validate_brain(path)
    if action in ("create", "connect"):
        save_desktop_brain_pointer(path)
    return {"ok": True, "brain": info.model_dump(mode="json")}


def serve(command):
    from engine.desktop.offline import install_offline_boundary
    install_offline_boundary()
    import msvcrt
    import uvicorn
    from starlette.staticfiles import StaticFiles
    from starlette.responses import JSONResponse
    from engine.desktop.security import DesktopBoundary

    info = validate_brain(command["brainPath"])
    # A second Windows session/process must never become another Brain writer.
    lock = open(Path(info.path) / ".desktop-writer.lock", "a+b")
    lock.seek(0)
    if not lock.read(1):
        lock.write(b"0")
        lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as exc:
        raise RuntimeError("This Brain is already open in another PESE process.") from exc

    os.environ.update(PESE_ENV="production", PESE_BRAIN_PATH=info.path,
                      PESE_DATA_DIR=info.path, PESE_STORAGE_BACKEND="local", PESE_PROFILE="private",
                      PESE_STARTUP_PROGRESS="1",
                      HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
                      PESE_PREWARM_QA="0")
    for key in ("PESE_QA_CHECKPOINT", "PESE_REL_CHECKPOINT", "GOOGLE_APPLICATION_CREDENTIALS"):
        os.environ.pop(key, None)
    model_root = APP_ROOT / "models" / "fastembed"
    snapshots = list(model_root.glob("models--*/snapshots/*/model_optimized.onnx"))
    if len(snapshots) != 1:
        raise RuntimeError("Installation model assets are missing. Reinstall PESE; your Brain is preserved.")
    os.environ["PESE_FASTEMBED_CACHE"] = str(model_root)
    os.environ["PESE_FASTEMBED_MODEL_PATH"] = str(snapshots[0].parent)
    if not (APP_ROOT / "ui" / "index.html").is_file():
        raise RuntimeError("Installation UI assets are missing. Reinstall PESE; your Brain is preserved.")
    if not (APP_ROOT / "engine/neural/checkpoints/peseng0_baseline_final.pt").is_file():
        raise RuntimeError("Installation checkpoint assets are missing. Reinstall PESE.")
    token = command["token"]
    if not isinstance(token, str) or len(token) < 64 or not token.isascii():
        raise ValueError("Invalid desktop launch credentials")

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    print("PESE_PORT " + str(port), flush=True)

    from engine.startup_progress import emit_progress
    emit_progress("loading", 0, 0)
    from engine.api.main import app
    # CORS is for the separate Next development server only. Desktop is same-origin.
    app.user_middleware.clear()
    app.docs_url = app.redoc_url = app.openapi_url = None
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") not in
                           ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect")]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                           access_log=False, log_level="error"))

    shutdown_state = {"stopping": False}

    @app.post("/desktop/shutdown", include_in_schema=False)
    async def shutdown():
        # Existing ASGI requests finish under Uvicorn's graceful shutdown. Reject
        # new operations before acknowledging shutdown to the native supervisor.
        shutdown_state["stopping"] = True
        server.should_exit = True
        return JSONResponse({"stopping": True})

    @app.get("/desktop/offline-check", include_in_schema=False)
    async def offline_check():
        # A numeric TEST-NET address must be rejected before making a network call.
        try:
            with socket.socket() as probe:
                probe.connect(("192.0.2.1", 443))
        except OSError as exc:
            return {"external_connections_blocked": "disabled in PESE" in str(exc)}
        return {"external_connections_blocked": False}

    app.mount("/", StaticFiles(directory=APP_ROOT / "ui", html=True), name="desktop-ui")
    app.add_middleware(DesktopBoundary, token=token, origin=origin,
                       is_stopping=lambda: shutdown_state["stopping"])
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()
        lock.close()


def main():
    # Embedded runtime is isolated by python312._pth; make protocol UTF-8 explicit.
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        command = json.loads(sys.stdin.readline())
        if command.get("action") == "serve":
            serve(command)
        else:
            print(json.dumps(brain_command(command), ensure_ascii=True), flush=True)
    except Exception as exc:
        # No stack dump, documents, search terms or token in the host protocol/log.
        print(json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)}, ensure_ascii=True), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
