"""Application version from the app-owned build stamp, never from Brain data."""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def application_version(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    stamp = root / "source-provenance.json"
    if stamp.is_file():
        version = json.loads(stamp.read_text(encoding="utf-8"))["version"]
    else:
        project = root / "host/PESE.Desktop/PESE.Desktop.csproj"
        version = ET.parse(project).findtext("PropertyGroup/Version")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version):
        raise ValueError("Invalid application version metadata")
    return version
