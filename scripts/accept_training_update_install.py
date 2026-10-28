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
import xml.etree.ElementTree as ET

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
    p.add_argument("--safety-receipt", type=Path)
    p.add_argument("--resume-verified-setup", action="store_true")
    p.add_argument("--verify-payload-only", action="store_true")
    a = p.parse_args()
    output = a.output.resolve()
    if (output.exists() and not a.resume_verified_setup) or ROOT == output or ROOT in output.parents:
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
            package_manifest = z.read("lib/app/sq.version")
        return values, package_manifest
    normal, normal_xml = payload(a.normal_artifacts, "ManiacSoftwares.PESE")
    fixture, fixture_xml = payload(a.fixture_artifacts, marker["package_id"])
    if {n:h for n,h in normal.items() if n!="sq.version"} != {n:h for n,h in fixture.items() if n!="sq.version"}:
        raise ValueError("Installer fixture application payload differs from normal release")
    # The fixture must change only registration metadata, never application
    # files. Validate the full manifest after precisely these three changes.
    expected_manifest_changes = {
        "id": ("ManiacSoftwares.PESE", marker["package_id"]),
        "shortcutAmuid": ("velopack.ManiacSoftwares.PESE", "velopack." + marker["package_id"]),
        "shortcutLocations": ("Desktop,StartMenuRoot", "None"),
    }
    normal_tree = ET.fromstring(normal_xml)
    for field, (before_value, after_value) in expected_manifest_changes.items():
        elements = [e for e in normal_tree.iter() if e.tag.rsplit("}",1)[-1]==field]
        if len(elements)!=1 or elements[0].text!=before_value:
            raise ValueError("Unexpected canonical registration manifest")
        elements[0].text=after_value
    if ET.canonicalize(ET.tostring(normal_tree,encoding="unicode"),rewrite_prefixes=True) != ET.canonicalize(fixture_xml.decode("utf-8-sig"),rewrite_prefixes=True):
        raise ValueError("Unexpected installer metadata difference")
    if a.verify_payload_only:
        print(json.dumps({"passed":True,"application_files_verified":len(normal)-1,
                          "package_manifest_changes_verified":list(expected_manifest_changes)}))
        return 0
    if a.safety_receipt is None:p.error("Verified owner safety receipt required before Setup execution")
    safety = json.loads(a.safety_receipt.read_text(encoding="utf-8"))
    if not safety["passed"] or not all(safety["checks"].values()):
        p.error("Verified original safety evidence required")
    stable = Path(safety["application"]["install"])
    pointer = Path(safety["settings_path"])
    def originals():
        return {"registration": stable_registration(), "pointer": sha(pointer),
                **{n: sha(stable / n) for n in safety["application"]["hashes"]}}
    if a.resume_verified_setup:
        before=json.loads((output/"original-preservation-before.json").read_text())
        if not (output/"Brain/.pese-disposable-fixture").is_file() or (output/"native").exists() or "Installation completed successfully!" not in (output/"setup.log").read_text():
            raise ValueError("Only the previously completed marked Setup fixture may resume")
    else:
        before = originals()
        output.mkdir(parents=True)
        (output / "original-preservation-before.json").write_text(json.dumps(before,indent=2),encoding="utf-8")
    brain, native, install = output / "Brain", output / "native", output / "install"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PESE_", "PYTHON"))}
    (output / "temp").mkdir(exist_ok=a.resume_verified_setup)
    env.update(TEMP=str(output / "temp"), TMP=str(output / "temp"), HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    setup = a.fixture_artifacts / "PESE-Setup.exe"
    if not a.resume_verified_setup:
        subprocess.run([sys.executable, "-B", str(ROOT / "scripts/create_n3e_fixture.py"), str(brain), "--count", "200"],
                       env=env, cwd=ROOT, check=True)
        with (output / "setup-console.log").open("w") as log:
            result = subprocess.run([str(setup), "--silent", "--installto", str(install), "--log", str(output / "setup.log")],
                                    env=env, cwd=output, stdout=log, stderr=subprocess.STDOUT, timeout=600)
        if result.returncode:raise RuntimeError("Actual Setup failed")
    if not (install / "current/PESE.exe").is_file():
        raise RuntimeError("Actual installer failed; inspect retained setup log")
    installed_expected={n:h for n,h in fixture.items() if n!="PESE_ExecutionStub.exe" or (install/"current"/n).exists()}
    actual_current={p.relative_to(install/"current").as_posix() for p in (install/"current").rglob("*") if p.is_file()}
    if actual_current != set(installed_expected)-{"Squirrel.exe"}:raise RuntimeError("Unexpected installed file membership")
    if any(sha(install / "Update.exe" if n=="Squirrel.exe" else install/"current"/n) != expected for n, expected in installed_expected.items()):
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
              "payload_files_verified": len(normal)-1, "source_commit": marker["source_commit"],
              "package_manifest_changes_verified": list(expected_manifest_changes),
              "installed_files_verified": len(installed_expected),
              "consumed_installer_resources": [n for n in fixture if n not in installed_expected],
              "relocated_installer_resources": {"Squirrel.exe":"../Update.exe"},
              "resumed_completed_setup_after_layout_assertion": a.resume_verified_setup,
              "setup_sha256": sha(setup), "synthetic_document_count": 200, "synthetic_only": True,
              "stable_install_pointer_and_registration_preserved": preserved, "real_owner_activated": False,
              "native_receipt": str(native / "startup-acceptance.json")}
    (output / "installed-acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
