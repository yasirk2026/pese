import json
import pytest
from engine.app_version import application_version


def test_packaged_version_uses_app_stamp_without_brain_access(tmp_path):
    (tmp_path / "source-provenance.json").write_text(json.dumps({"version": "0.1.0-alpha.6"}))
    assert application_version(tmp_path) == "0.1.0-alpha.6"


def test_development_version_uses_host_source(tmp_path):
    project = tmp_path / "host/PESE.Desktop/PESE.Desktop.csproj"
    project.parent.mkdir(parents=True)
    project.write_text("<Project><PropertyGroup><Version>0.1.0-alpha.6</Version></PropertyGroup></Project>")
    assert application_version(tmp_path) == "0.1.0-alpha.6"


def test_invalid_packaged_version_fails_closed(tmp_path):
    (tmp_path / "source-provenance.json").write_text('{"version": "incorrect"}')
    with pytest.raises(ValueError, match="version metadata"):
        application_version(tmp_path)
