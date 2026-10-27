"""Loopback-test intake factory. No default server, credentials, or deployment.

Every valid submission stays quarantined. Contract v1 contains no training labels
or example text, so it cannot enter supervised training automatically.
"""
import hashlib
import json
from pathlib import Path
import secrets
from threading import RLock
import time
from fastapi import FastAPI, HTTPException, Request
from engine.intelligence.contributions import parse_package, MAX_BYTES
from engine.intelligence.evidence import digest


def create_mock_app(root, *, token, max_per_minute=10, max_packages=1000):
    if not token:
        raise ValueError("Explicit test authentication required")
    root = Path(root)
    lock = RLock()
    attempts = []
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.post("/v1/contributions")
    async def ingest(request: Request):
        if not secrets.compare_digest(request.headers.get("authorization", "").encode(), ("Bearer " + token).encode()):
            raise HTTPException(401, "Authentication required")
        if request.headers.get("x-pese-test-review") != "reviewed-loopback-only-v1":
            raise HTTPException(403, "Explicit test ingestion review required; export alone does not authorize upload")
        with lock:
            now = time.monotonic()
            attempts[:] = [t for t in attempts if now-t < 60]
            if len(attempts) >= max_per_minute:
                raise HTTPException(429, "Rate limit")
            attempts.append(now)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise HTTPException(415, "JSON required")
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise HTTPException(413, "Size limit")
        try:
            package = parse_package(bytes(data))
        except (ValueError, TypeError):
            # No body, query text, paths or raw pydantic errors in logs/responses.
            raise HTTPException(400, "Invalid contribution contract")
        content = package.model_dump(mode="json")
        key = digest(content)
        with lock:
            quarantine = root / "quarantine"
            quarantine.mkdir(parents=True, exist_ok=True)
            path = quarantine / (key + ".json")
            if path.exists():
                return {"status": "duplicate", "training_eligible": False}
            if sum(1 for _ in quarantine.glob("*.json")) >= max_packages:
                raise HTTPException(503, "Intake capacity reached")
            # Exclusive creation; no overwrite. File name contains no caller IDs.
            with path.open("x", encoding="utf-8") as out:
                json.dump({"contract": content, "received_unix": int(time.time()), "retention_days": 30,
                           "status": "quarantine", "training_eligible": False}, out, sort_keys=True)
        return {"status": "quarantined", "training_eligible": False}

    return app


def expire_quarantine(root, *, now=None):
    """Explicit operational deletion; never runs from desktop/backup/recovery."""
    now = time.time() if now is None else now
    deleted = 0
    for path in (Path(root) / "quarantine").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if now-data["received_unix"] >= data["retention_days"]*86400:
            path.unlink()
            deleted += 1
    return deleted
