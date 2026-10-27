"""Verify local Owner BETA package privacy, channel, model pins and source bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def verify(directory):
    from engine.intelligence.beta.base_lock import BASE_FILES
    directory = Path(directory)
    assets = json.loads((directory / "releases.win-owner-beta.json").read_text(encoding="utf-8-sig"))["Assets"]
    full = [a for a in assets if a["Type"] == "Full"]
    if len(full) != 1:
        raise ValueError("Exactly one full BETA package required")
    asset = full[0]
    if asset["PackageId"] != "ManiacSoftwares.PESE.OwnerBeta" or Path(asset["FileName"]).name != asset["FileName"]:
        raise ValueError("Wrong package identity")
    package = directory / asset["FileName"]
    with package.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    if checksum.lower() != asset["SHA256"].lower() or package.stat().st_size != asset["Size"]:
        raise ValueError("Package differs from feed")
    checked = 0
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate package path")
        forbidden = {"pese-brain.json", "firestore_documents.json", "behavioural_events.jsonl", "privacy_settings.json",
                     "desktop-settings.json", "google-client-secrets.json", "google-oauth-config.json", "permissions.json", "participation.json"}
        for name in names:
            if name.startswith(("/", "\\")) or "\\" in name or ":" in name or ".." in name.split("/"):
                raise ValueError("Unsafe package path")
            leaf = Path(name).name.lower()
            if leaf in forbidden or leaf.endswith((".db", ".sqlite", ".pese-bundle")) or any(p in name.lower().split("/") for p in (".git", ".env", "node_modules", "semantic_index", ".pese-intelligence-v1")):
                raise ValueError("Private or development data in package")
        metadata = {e.tag.rsplit("}", 1)[-1]: e.text for e in ET.fromstring(archive.read("ManiacSoftwares.PESE.OwnerBeta.nuspec")).iter()}
        if metadata.get("id") != asset["PackageId"] or metadata.get("version") != asset["Version"] or metadata.get("channel") != "win-owner-beta" or metadata.get("mainExe") != "PESE.exe":
            raise ValueError("Package metadata mismatch")
        provenance = json.loads(archive.read("lib/app/source-provenance.json"))
        if provenance["acceptance_only"] is not True or provenance["version"] != asset["Version"]:
            raise ValueError("Local BETA provenance required")
        for name in names:
            if name.startswith("lib/app/engine/") and name.endswith(".py"):
                relative = name.removeprefix("lib/app/")
                if hashlib.sha256(archive.read(name)).hexdigest() != provenance["tracked_files_sha256"].get(relative):
                    raise ValueError("Packaged source differs from its provenance")
                checked += 1
        for name, expected in BASE_FILES.items():
            if hashlib.sha256(archive.read("lib/app/engine/neural/assets/basic_english_beta_v1/" + name)).hexdigest() != expected:
                raise ValueError("The frozen base model changed")
    result = {"passed": True, "package_id": asset["PackageId"], "channel": "win-owner-beta", "version": asset["Version"],
              "package_sha256": checksum, "engine_source_files_verified": checked, "base_model_unchanged": True,
              "private_payload_excluded": True, "acceptance_only": True, "source_commit": provenance["commit"],
              "source_clean": provenance["source_clean"]}
    (directory / "owner-beta-verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts")
    verify(parser.parse_args().artifacts)
