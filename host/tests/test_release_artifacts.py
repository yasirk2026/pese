"""Release privacy and corruption gates; all packages are disposable ZIP fixtures."""
import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from scripts.verify_release import verify
from scripts.stage_desktop import tracked_engine_sources
import subprocess


def fixture_package(tmp_path, extra=None):
    version, commit = "0.1.0-alpha.5", "a" * 40
    notes = "# Synthetic release fixture\n"
    source = tmp_path / "source"
    (source / "docs/releases").mkdir(parents=True)
    (source / f"docs/releases/{version}.md").write_text(notes, encoding="utf-8")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    name = f"ManiacSoftwares.PESE-{version}-full.nupkg"
    package = artifacts / name
    with zipfile.ZipFile(package, "w") as z:
        for relative in ("PESE.exe", "PESE.dll", "PESE.runtimeconfig.json", "runtime/python/python.exe",
                         "runtime/python/python312.zip", "engine/api/main.py", "engine/desktop/launcher.py",
                         "engine/evaluation/synthetic_history.py", "ui/index.html", "ui/search/index.html",
                         "ui/settings/index.html", "engine/neural/checkpoints/peseng0_baseline_final.pt",
                         "models/synthetic/model_optimized.onnx"):
            z.writestr("lib/app/" + relative, b"synthetic")
        z.writestr("ManiacSoftwares.PESE.nuspec", f"<package><metadata><id>ManiacSoftwares.PESE</id><version>{version}</version><channel>win</channel><mainExe>PESE.exe</mainExe><releaseNotes>{notes}</releaseNotes></metadata></package>")
        z.writestr("lib/app/source-provenance.json", json.dumps({"commit": commit, "version": version, "acceptance_only": False}))
        if extra:
            z.writestr(extra, b"synthetic forbidden content")
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    (artifacts / "releases.win.json").write_text(json.dumps({"Assets": [{"PackageId": "ManiacSoftwares.PESE", "Version": version, "Type": "Full", "FileName": name, "Size": package.stat().st_size, "SHA256": digest}]}), encoding="utf-8")
    (artifacts / "PESE-Setup.exe").write_bytes(b"synthetic installer")
    (artifacts / "RELEASES").write_text(f"{hashlib.sha1(package.read_bytes()).hexdigest()} {name} {package.stat().st_size}\n", encoding="utf-8")
    (artifacts / "assets.win.json").write_text(json.dumps([{"RelativeFileName": "PESE-Setup.exe", "Type": "Installer"}, {"RelativeFileName": name, "Type": "Full"}]), encoding="utf-8")
    (artifacts / "release-notes.md").write_text(notes, encoding="utf-8")
    return artifacts, version, commit, source


@pytest.mark.parametrize("member", ["lib/app/firestore_documents.json", "lib/app/search_sync_feedback.db",
                                   "lib/app/google-client-secrets-other.json", "lib/app/.env",
                                   "lib/app/semantic_index/cache_store.npz", "../escape.txt"])
def test_release_rejects_private_or_unsafe_payload(tmp_path, member):
    with pytest.raises(AssertionError):
        verify(*fixture_package(tmp_path, member))


def test_release_rejects_changed_package(tmp_path):
    args = fixture_package(tmp_path)
    package = next(args[0].glob("*.nupkg"))
    package.write_bytes(package.read_bytes() + b"corrupted")
    with pytest.raises(AssertionError, match="size"):
        verify(*args)


def test_release_records_complete_artifact_hashes(tmp_path):
    artifacts, version, commit, source = fixture_package(tmp_path)
    result = verify(artifacts, version, commit, source)
    assert result["commit"] == commit and not result["signed"] and not result["acceptance_only"]
    assert result["artifacts"]["release-notes.md"] == hashlib.sha256((artifacts / "release-notes.md").read_bytes()).hexdigest()


def test_release_rejects_mismatched_public_notes(tmp_path):
    args = fixture_package(tmp_path)
    (args[0] / "release-notes.md").write_text("Wrong release", encoding="utf-8")
    with pytest.raises(ValueError, match="notes"):
        verify(*args)


def test_staging_never_includes_ignored_private_python(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "engine").mkdir()
    (tmp_path / "engine/public.py").write_text("# public fixture", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("*private_history.py\n", encoding="utf-8")
    (tmp_path / "engine/private_history.py").write_text("# private fixture must not ship", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "engine/public.py", ".gitignore"], check=True)
    assert tracked_engine_sources(tmp_path) == [tmp_path / "engine/public.py"]
