"""Installer-fixture identity differences cannot mask application/manifest tampering."""
import hashlib
import json
import sys
import zipfile

import pytest
pytest.importorskip("winreg")
from scripts import accept_training_update_install as runner


def artifact(folder, identity, *, content=b"public synthetic application", version="0.1.0-alpha.7", extra=False):
    folder.mkdir()
    fixture=identity.endswith("AcceptanceOnly")
    shortcuts="None" if fixture else "Desktop,StartMenuRoot"
    xml=f'<package xmlns="urn:synthetic-fixture"><metadata><id>{identity}</id><version>{version}</version><shortcutAmuid>velopack.{identity}</shortcutAmuid><shortcutLocations>{shortcuts}</shortcutLocations></metadata></package>'
    package=folder/"fixture.nupkg"
    with zipfile.ZipFile(package,"w") as archive:
        archive.writestr("lib/app/sq.version",xml)
        archive.writestr("lib/app/PESE.dll",content)
        if extra:archive.writestr("lib/app/unexpected.py",b"unapproved code")
    feed={"Assets":[{"Type":"Full","PackageId":identity,"FileName":package.name,
                      "SHA256":hashlib.sha256(package.read_bytes()).hexdigest()}]}
    (folder/"releases.win.json").write_text(json.dumps(feed))
    if fixture:(folder/"fixture-only.json").write_text(json.dumps({"acceptance_only":True,"package_id":identity}))


@pytest.mark.parametrize("change",["none","application","manifest","extra"])
def test_only_fixture_registration_metadata_may_differ(tmp_path,monkeypatch,change):
    normal=tmp_path/"normal";fixture=tmp_path/"fixture";unused=tmp_path/"unused"
    artifact(normal,"ManiacSoftwares.PESE")
    artifact(fixture,"ManiacSoftwares.PESE.AcceptanceOnly",
             content=b"changed application" if change=="application" else b"public synthetic application",
             version="0.1.0-alpha.8" if change=="manifest" else "0.1.0-alpha.7",extra=change=="extra")
    monkeypatch.setattr(sys,"argv",["verify",str(normal),str(fixture),str(unused),"--verify-payload-only"])
    def no_owner_access():raise AssertionError("Payload-only verification must not inspect a real installation")
    monkeypatch.setattr(runner,"stable_registration",no_owner_access)
    if change=="none":assert runner.main()==0
    else:
        with pytest.raises(ValueError):runner.main()
    assert not unused.exists()
