"""Verify Velopack artifacts and write a public source/artifact provenance manifest."""
import argparse
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(directory, version, commit, source, acceptance_only=False):
    feed_path = directory / "releases.win.json"
    feed = json.loads(feed_path.read_text(encoding="utf-8-sig"))
    assets = feed["Assets"]
    full = [a for a in assets if a["Version"] == version and a["Type"] == "Full"]
    assert len(full) == 1, "Expected exactly one target full package"
    asset = full[0]
    assert asset["PackageId"] == "ManiacSoftwares.PESE", "Wrong package identity"
    name = asset["FileName"]
    assert Path(name).name == name and name.endswith("-full.nupkg"), "Unsafe package filename"
    package = directory / name
    assert package.stat().st_size == asset["Size"], "Package size differs from feed"
    assert sha(package).upper() == asset["SHA256"].upper(), "Package SHA-256 differs from feed"
    compatibility = (directory / "RELEASES").read_text(encoding="utf-8-sig").split()
    with package.open("rb") as stream:
        expected_sha1 = hashlib.file_digest(stream, "sha1").hexdigest()
    assert len(compatibility) == 3 and compatibility[0].lower() == expected_sha1 and compatibility[1] == name and int(compatibility[2]) == asset["Size"], "Legacy feed differs from package"
    mapping = json.loads((directory / "assets.win.json").read_text(encoding="utf-8-sig"))
    assert {a["RelativeFileName"] for a in mapping if a["Type"] == "Installer"} == {"PESE-Setup.exe"}
    assert {a["RelativeFileName"] for a in mapping if a["Type"] == "Full"} == {name}
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)), "Duplicate package member"
        required_payload = {"PESE.exe", "PESE.dll", "PESE.runtimeconfig.json", "runtime/python/python.exe",
                            "runtime/python/python312.zip", "engine/api/main.py", "engine/desktop/launcher.py",
                            "engine/evaluation/synthetic_history.py", "ui/index.html", "ui/search/index.html",
                            "ui/settings/index.html", "engine/neural/checkpoints/peseng0_baseline_final.pt"}
        assert {"lib/app/" + n for n in required_payload} <= set(names), "Incomplete application payload"
        assert len([n for n in names if n.startswith("lib/app/models/") and n.endswith("/model_optimized.onnx")]) == 1
        forbidden = {"pese-brain.json", "firestore_documents.json", "behavioural_events.jsonl",
                     "privacy_settings.json", "desktop-settings.json", "google-client-secrets.json",
                     "google-oauth-config.json", "search_sync_feedback.db"}
        for member in names:
            assert not member.startswith(("/", "\\")) and "\\" not in member and ":" not in member and ".." not in member.split("/"), "Unsafe package path"
            leaf = Path(member).name.lower()
            assert leaf not in forbidden and not leaf.endswith((".db", ".sqlite", ".pese-bundle")), "Private Brain asset in package"
            assert not (leaf.endswith(".json") and (leaf.startswith("google-client-secrets") or leaf.startswith("google-oauth-config"))), "OAuth configuration in package"
            assert not any(p in member.lower().split("/") for p in (".git", ".env", "node_modules", "semantic_index")), "Development/cache asset in package"
        spec = ET.fromstring(archive.read("ManiacSoftwares.PESE.nuspec"))
        values = {e.tag.rsplit("}", 1)[-1]: e.text for e in spec.iter()}
        assert values["id"] == "ManiacSoftwares.PESE" and values["version"] == version
        assert values["channel"] == "win" and values["mainExe"] == "PESE.exe"
        notes = (source / f"docs/releases/{version}.md").read_text(encoding="utf-8")
        assert (values.get("releaseNotes") or "").strip() == notes.strip(), "Release notes differ from source"
        provenance = json.loads(archive.read("lib/app/source-provenance.json"))
        assert provenance["commit"] == commit and provenance["version"] == version
        assert provenance["acceptance_only"] == acceptance_only
    if (directory / "release-notes.md").read_text(encoding="utf-8").strip() != notes.strip():
        raise ValueError("Published Markdown notes differ from the packaged notes")
    required = ["PESE-Setup.exe", name, "releases.win.json", "RELEASES", "assets.win.json", "release-notes.md"]
    hashes = {n: sha(directory / n) for n in required}
    (directory / "checksums.sha256").write_text("".join(f"{h}  {n}\n" for n, h in hashes.items()), encoding="utf-8")
    manifest = {"version": version, "tag": "v" + version, "commit": commit,
                "repository": "yasirk2026/pese", "package_id": "ManiacSoftwares.PESE",
                "channel": "win", "prerelease": True, "signed": False,
                "acceptance_only": acceptance_only, "artifacts": hashes}
    (directory / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("version")
    parser.add_argument("commit")
    parser.add_argument("--acceptance-only", action="store_true")
    args = parser.parse_args()
    assert re.fullmatch(r"\d+\.\d+\.\d+-alpha\.\d+", args.version), "Invalid alpha SemVer"
    assert re.fullmatch(r"[a-f0-9]{40}", args.commit), "Expected an exact source commit"
    verify(args.directory, args.version, args.commit, Path(__file__).resolve().parents[1], args.acceptance_only)


if __name__ == "__main__":
    main()
