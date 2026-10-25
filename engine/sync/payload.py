"""Allowlisted G1 format-2 payload built on Brain schema 1; no vector/model transport."""
import hashlib
import json
from pathlib import Path
from ..brain.contracts import BrainIdentity
from ..brain.profile import UserProfile
from ..brain.events import QuerySessionEvent
from ..indexing.document import Document
from .contracts import CorruptSnapshotError
from .logical import LOGICAL_FILENAME, validate_records

REQUIRED = frozenset({"pese-brain.json", "firestore_documents.json", "privacy_settings.json",
                      "behavioural_events.jsonl", LOGICAL_FILENAME})
AVATARS = frozenset("profile/avatar" + ext for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"))
ALLOWED = REQUIRED | AVATARS | {"profile/profile.json"}
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_PAYLOAD_BYTES = 512 * 1024 * 1024
MAX_FILES = len(ALLOWED) + 1


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def strict_json_loads(value):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise CorruptSnapshotError("Duplicate JSON object key in canonical payload.")
            result[key] = item
        return result
    def finite_only(value):
        raise CorruptSnapshotError("Non-finite JSON value in canonical payload.")
    return json.loads(value, object_pairs_hook=unique, parse_constant=finite_only)


def content_digest(directory, paths):
    h = hashlib.sha256()
    for name in sorted(paths):
        h.update(name.encode("utf-8") + b":" + hashlib.sha256((Path(directory) / name).read_bytes()).hexdigest().encode())
    return h.hexdigest()


def validate_payload(directory, files, brain_id):
    directory = Path(directory)
    paths = set(files)
    if not REQUIRED <= paths or not paths <= ALLOWED:
        raise CorruptSnapshotError("Snapshot payload does not match the versioned canonical allowlist.")
    try:
        raw_identity = strict_json_loads((directory / "pese-brain.json").read_text(encoding="utf-8"))
        identity = BrainIdentity.model_validate(raw_identity)
        if (raw_identity.get("format") != "pese-brain" or raw_identity.get("schemaVersion") != 1
                or identity.brain_id != brain_id):
            raise ValueError("Brain identity/schema mismatch")
        docs = strict_json_loads((directory / "firestore_documents.json").read_text(encoding="utf-8"))
        if not isinstance(docs, dict):
            raise ValueError("Documents must be an object")
        ids, slugs = set(), set()
        for key, record in docs.items():
            doc = Document.model_validate(record)
            if key != doc.id or doc.id in ids or doc.slug in slugs or doc.content_schema_version not in (1, 2):
                raise ValueError("Incompatible or duplicate document identity")
            ids.add(doc.id)
            slugs.add(doc.slug)
        settings = strict_json_loads((directory / "privacy_settings.json").read_text(encoding="utf-8"))
        if not isinstance(settings, dict) or type(settings.get("history_enabled")) is not bool:
            raise ValueError("Invalid privacy settings")
        for line in (directory / "behavioural_events.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                QuerySessionEvent.model_validate(strict_json_loads(line))
        validate_records(strict_json_loads((directory / LOGICAL_FILENAME).read_text(encoding="utf-8")))
        profile_path = directory / "profile/profile.json"
        if profile_path.exists():
            profile = UserProfile.model_validate(strict_json_loads(profile_path.read_text(encoding="utf-8")))
            if profile.schema_version != 1:
                raise ValueError("Unsupported profile schema")
            avatar = profile.avatar.relative_path if profile.avatar else None
            if avatar and (avatar not in AVATARS or avatar not in paths):
                raise ValueError("Missing or unsupported profile avatar")
            if paths & AVATARS != ({avatar} if avatar else set()):
                raise ValueError("Unexpected profile avatar")
        elif paths & AVATARS:
            raise ValueError("Avatar without profile")
    except CorruptSnapshotError:
        raise
    except Exception as exc:
        raise CorruptSnapshotError("Snapshot contains incompatible canonical records.") from exc
    return identity
