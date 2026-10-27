"""Execute actual Setup with an acceptance-only package identity and synthetic Brain.

The normal-ID updater is tested separately. This installer-mechanism fixture uses
the same payload without replacing the owner's stable uninstall registration.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import winreg
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stable_registration():
    result = {}
    for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
        path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ManiacSoftwares.PESE"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ | view) as key:
                for number in range(winreg.QueryInfoKey(key)[1]):
                    name, value, kind = winreg.EnumValue(key, number)
                    result[f"{view}:{name}"] = (value.hex() if isinstance(value, bytes) else value, kind)
        except FileNotFoundError:
            result[str(view)] = "absent"
    return hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("normal_artifacts", type=Path)
    p.add_argument("fixture_artifacts", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--safety-receipt", type=Path, required=True)
    a = p.parse_args()
    output = a.output.resolve()
    if output.exists() or ROOT == output or ROOT in output.parents:
        p.error("Fresh case outside checkout required")
    marker = json.loads((a.fixture_artifacts / "fixture-only.json").read_text(encoding="utf-8-sig"))
    if marker.get("acceptance_only") is not True or marker.get("package_id") != "ManiacSoftwares.PESE.AcceptanceOnly":
        p.error("Only the separate acceptance installer may run automatically")
    def payload(directory, identity):
        assets = json.loads((directory / "releases.win.json").read_text(encoding="utf-8-sig"))["Assets"]
        full = [v for v in assets if v["Type"] == "Full"]
        if len(full) != 1 or full[0]["PackageId"] != identity:
            raise ValueError("Installer package identity mismatch")
        path = directory / full[0]["FileName"]
        if sha(path).lower() != full[0]["SHA256"].lower():
            raise ValueError("Installer fixture digest mismatch")
        with zipfile.ZipFile(path) as z:
            values = {n.removeprefix("lib/app/"): hashlib.sha256(z.read(n)).hexdigest()
                      for n in z.namelist() if n.startswith("lib/app/") and not n.endswith("/")}
        return values
    normal = payload(a.normal_artifacts, "ManiacSoftwares.PESE")
    fixture = payload(a.fixture_artifacts, marker["package_id"])
    if normal != fixture:
        raise ValueError("Installer fixture application payload differs from normal release")
    safety = json.loads(a.safety_receipt.read_text(encoding="utf-8"))
    if not safety["passed"] or not all(safety["checks"].values()):
        p.error("Verified original safety evidence required")
    stable = Path(safety["application"]["install"])
    pointer = Path(safety["settings_path"])
    def originals():
        return {"registration": stable_registration(), "pointer": sha(pointer),
                **{n: sha(stable / n) for n in safety["application"]["hashes"]}}
    before = originals()
    output.mkdir(parents=True)
    brain, native, install = output / "Brain", output / "native", output / "install"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PESE_", "PYTHON"))}
    (output / "temp").mkdir()
    env.update(TEMP=str(output / "temp"), TMP=str(output / "temp"), HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    subprocess.run([sys.executable, "-B", str(ROOT / "scripts/create_n3e_fixture.py"), str(brain), "--count", "200"],
                   env=env, cwd=ROOT, check=True)
    setup = a.fixture_artifacts / "PESE-Setup.exe"
    with (output / "setup-console.log").open("w") as log:
        result = subprocess.run([str(setup), "--silent", "--installto", str(install), "--log", str(output / "setup.log")],
                                env=env, cwd=output, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    if result.returncode or not (install / "current/PESE.exe").is_file():
        raise RuntimeError("Actual installer failed; inspect retained setup log")
    if any(sha(install / "current" / n) != expected for n, expected in normal.items()):
        raise RuntimeError("Installed payload differs from normal release")
    process = subprocess.Popen([str(install / "current/PESE.exe"), "--accept-training-startup", str(brain), str(native), "accept"],
                               env=env, cwd=install / "current")
    code = process.wait(timeout=600)
    receipt = json.loads((native / "startup-acceptance.json").read_text(encoding="utf-8"))
    preserved = originals() == before
    report = {"passed": code == 0 and receipt["passed"] and preserved,
              "real_setup_executed": True, "portable_installation": False,
              "installer_fixture_identity": marker["package_id"], "compiled_identity": "ManiacSoftwares.PESE",
              "normal_identity_setup_executed": False, "normal_release_payload_identical": True,
              "payload_files_verified": len(normal), "source_commit": marker["source_commit"],
              "setup_sha256": sha(setup), "synthetic_document_count": 200, "synthetic_only": True,
              "stable_install_pointer_and_registration_preserved": preserved, "real_owner_activated": False,
              "native_receipt": str(native / "startup-acceptance.json")}
    (output / "installed-acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
