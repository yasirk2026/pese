"""Run real Owner BETA Setup into a separate install, with SYNTHETIC UI consent.

Never launches the owner Brain, selects its pointer, or consents for the owner.
Only the separate ManiacSoftwares.PESE.OwnerBeta package may be installed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--safety-receipt", required=True, type=Path)
    args = parser.parse_args()
    artifacts, output = (Path(os.path.abspath(p)).resolve() for p in (args.artifacts, args.output))
    if output.exists() or output.is_relative_to(ROOT):
        parser.error("A new case outside the checkout is required")
    feed = json.loads((artifacts / "releases.win-owner-beta.json").read_text(encoding="utf-8-sig"))
    targets = [a for a in feed["Assets"] if a["Type"] == "Full"]
    if len(targets) != 1 or targets[0]["PackageId"] != "ManiacSoftwares.PESE.OwnerBeta":
        parser.error("Only a separate Owner BETA package is permitted")
    asset = targets[0]
    if Path(asset["FileName"]).name != asset["FileName"]:
        parser.error("Invalid package filename")
    package = artifacts / asset["FileName"]
    if sha(package).lower() != asset["SHA256"].lower():
        parser.error("Package digest mismatch")
    with zipfile.ZipFile(package) as archive:
        metadata = {e.tag.rsplit("}", 1)[-1]: e.text for e in ET.fromstring(archive.read("ManiacSoftwares.PESE.OwnerBeta.nuspec")).iter()}
        if metadata.get("id") != asset["PackageId"] or metadata.get("channel") != "win-owner-beta":
            parser.error("Package identity/channel mismatch")
        if any(Path(n).name in {"pese-brain.json", "firestore_documents.json", "desktop-settings.json", "learning.db"} for n in archive.namelist()):
            parser.error("User data must never ship")
    setups = list(artifacts.glob("*Setup.exe"))
    if len(setups) != 1:
        parser.error("Expected one BETA installer")
    safety = json.loads(args.safety_receipt.read_bytes())
    if not safety["passed"] or not all(safety["checks"].values()):
        parser.error("Verified owner backup required")
    stable = Path(safety["application"]["install"])
    pointer = Path(safety["settings_path"])
    before = {"pointer": sha(pointer), **{n: sha(stable / n) for n in safety["application"]["hashes"]}}
    output.mkdir(parents=True)
    fixture, native, install = output / "synthetic-Brain", output / "native", output / "install"
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("PESE_", "PYTHON"))}
    environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    (output / "temp").mkdir()
    environment.update(TEMP=str(output / "temp"), TMP=str(output / "temp"))
    subprocess.run([sys.executable, "-B", str(ROOT / "scripts/create_n3e_fixture.py"), str(fixture)],
                   env=environment, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    (fixture / ".pese-require-installed").write_text("Require actual installed Owner BETA identity")
    command = [str(setups[0]), "--silent", "--installto", str(install), "--log", str(output / "setup.log"),
               "--", "--accept-neural-beta", str(fixture), str(native)]
    with (output / "setup-console.log").open("w") as log:
        setup = subprocess.run(command, env=environment, cwd=output, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    # Silent Velopack setup installs but does not launch the application. Some
    # setup modes may launch it, in which case the harness creates native first.
    if setup.returncode == 0 and not native.exists():
        subprocess.Popen([str(install / "current/PESE.exe"), "--accept-neural-beta", str(fixture), str(native)],
                         env=environment, cwd=install / "current")
    receipt_path = native / "native-beta-acceptance.json"
    deadline = time.monotonic() + 600
    while not receipt_path.exists() and time.monotonic() < deadline:
        time.sleep(.25)
    receipt = json.loads(receipt_path.read_bytes()) if receipt_path.exists() else {"passed": False, "error": "No installed native receipt"}
    after = {"pointer": sha(pointer), **{n: sha(stable / n) for n in safety["application"]["hashes"]}}
    installed = (install / "current/PESE.exe").is_file() and (install / "Update.exe").is_file()
    passed = setup.returncode == 0 and installed and receipt["passed"] and before == after
    result = {"passed": passed, "real_setup_executed": True, "portable_installation": False,
              "package_id": asset["PackageId"], "version": asset["Version"], "package_sha256": sha(package),
              "setup_sha256": sha(setups[0]), "setup_exit_code": setup.returncode,
              "install": str(install), "native_receipt": str(receipt_path), "synthetic_only": True,
              "stable_application_and_pointer_unchanged": before == after,
              "owner_brain_used": False, "owner_acceptance_inferred": False, "owner_beta_activated": False}
    (output / "installed-acceptance.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
