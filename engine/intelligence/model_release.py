"""Signed, immutable model bundles. No keys, downloads or activation at import.

Only fixed application code implements model architectures. A bundle contains
weights, tokenizer JSON and a signed manifest, never Python or pickle globals.
"""
from dataclasses import dataclass
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
from threading import RLock
from ..brain.atomic import atomic_write_json

ARCHITECTURE = "pese-relevance-crossencoder-v1"
MAX_MODEL_BYTES = 16 * 1024 * 1024
# Must be populated by an independently approved application release. A key in a
# downloaded bundle, environment variable or contribution is never trusted.
TRUSTED_RELEASE_KEYS = {}
_MODEL_STORE_LOCK = RLock()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode()


def semver(value):
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-alpha\.(\d+))?", value)
    if not m:
        raise ValueError("Unsupported application version")
    return tuple(map(int, m.groups()[:3])) + ((int(m[4]) if m[4] is not None else 10**9),)


@dataclass(frozen=True)
class ApprovedModel:
    directory: Path
    identity: str
    checkpoint_hash: str
    tokenizer_hash: str
    relative_cap: float
    gap_cap: float


def verify_bundle(directory, *, trusted_keys=None, app_version="0.1.0-alpha.6"):
    directory = Path(directory).resolve()
    if {p.name for p in directory.iterdir()} != {"manifest.json", "weights.pt", "tokenizer.json"}:
        raise ValueError("Unexpected bundle content; executable/support files are not permitted")
    keys = TRUSTED_RELEASE_KEYS if trusted_keys is None else trusted_keys
    if not keys:
        raise ValueError("No approved model publisher keys installed")
    raw = (directory / "manifest.json").read_bytes()
    if len(raw) > 32768:
        raise ValueError("Manifest exceeds size limit")
    manifest = json.loads(raw)
    signature = base64.b64decode(manifest.pop("signature"), validate=True)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    Ed25519PublicKey.from_public_bytes(keys[manifest["key_id"]]).verify(signature, canonical(manifest))
    required = {"version", "key_id", "model_id", "model_version", "architecture", "tokenizer_id", "min_app_version",
                "files", "acceptance", "provenance", "rollback_contract", "relative_cap", "gap_cap"}
    if (set(manifest) != required or manifest["version"] != 1 or
            manifest["architecture"] != ARCHITECTURE or manifest["rollback_contract"] != 1 or
            semver(manifest["min_app_version"]) > semver(app_version)):
        raise ValueError("Incompatible model release contract")
    if not all(isinstance(manifest[k], str) and manifest[k] for k in ("model_id", "model_version", "tokenizer_id")):
        raise ValueError("Missing versioned model/tokenizer identities")
    if manifest["model_id"] == "PESE-Rel-0":
        raise ValueError("Answer-support Rel-0 has no relevance ranking authority")
    a = manifest["acceptance"]
    if not (a.get("independent") is True and a.get("queries", 0) >= 300 and a.get("query_families",0) >= 30 and
            a.get("ndcg10_delta", -1) >= .02 and a.get("paired_lower95", -1) > 0 and
            a.get("critical_regression", 1) <= .02 and a.get("new_wrong_promotions") == 0 and
            a.get("gate_violations") == 0 and 0 <= a.get("warm_added_p95_ms", -1) <= 50 and
            0 <= a.get("cold_load_ms", -1) <= 2000 and 0 < a.get("worker_peak_mb", -1) <= 256):
        raise ValueError("Independent acceptance gate failed")
    if (not manifest["provenance"].get("dataset_sha256") or not manifest["provenance"].get("code_sha256")
            or not manifest["provenance"].get("environment_sha256") or not manifest["provenance"].get("protocol_sha256")):
        raise ValueError("Incomplete release provenance")
    if not (0 < manifest["relative_cap"] <= .03 and 0 < manifest["gap_cap"] <= .75):
        raise ValueError("Unapproved ranking bounds")
    files = manifest["files"]
    if set(files) != {"weights.pt", "tokenizer.json"}:
        raise ValueError("Only fixed-architecture weights and tokenizer are permitted")
    for filename, expected in files.items():
        path = directory / filename
        size = path.stat().st_size
        if path.is_symlink() or size != expected["bytes"] or not 0 < size <= MAX_MODEL_BYTES:
            raise ValueError("Invalid artifact size/path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
            raise ValueError("Artifact integrity failure")
    return ApprovedModel(directory, manifest["model_id"] + ":" + manifest["model_version"],
                         files["weights.pt"]["sha256"], files["tokenizer.json"]["sha256"],
                         manifest["relative_cap"], manifest["gap_cap"])


class ModelStore:
    """Stage → verify → health check → atomic pointer; preserve previous bundle.

    No desktop updater is enabled yet. Callers serialize active-search leases
    around activation, or keep each immutable ApprovedModel for the request.
    """
    def __init__(self, root, trusted_keys=None):
        self.root = Path(root)
        self.trusted_keys = trusted_keys
        self._lock = _MODEL_STORE_LOCK

    def activate(self, source, healthcheck):
        with self._lock:
            approved = verify_bundle(source, trusted_keys=self.trusted_keys)
            self.root.mkdir(parents=True, exist_ok=True)
            destination = self.root / hashlib.sha256((Path(source) / "manifest.json").read_bytes()).hexdigest()
            if not destination.exists():
                shutil.copytree(source, destination)
            installed = verify_bundle(destination, trusted_keys=self.trusted_keys)
            if not healthcheck(installed):
                raise ValueError("Model health check failed; current pointer preserved")
            pointer = self.root / "active.json"
            old = json.loads(pointer.read_text()) if pointer.exists() else {}
            atomic_write_json(pointer, {"version": 1, "current": destination.name, "previous": old.get("current")})
            return installed

    def rollback(self):
        with self._lock:
            pointer = self.root / "active.json"
            old = json.loads(pointer.read_text())
            previous = old.get("previous")
            if not previous or not re.fullmatch(r"[a-f0-9]{64}", previous):
                raise ValueError("No compatible rollback")
            result = verify_bundle(self.root / previous, trusted_keys=self.trusted_keys)
            atomic_write_json(pointer, {"version": 1, "current": previous, "previous": old["current"]})
            return result
