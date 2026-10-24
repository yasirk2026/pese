"""Static regression protection for PESE engine launchers."""
import re
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("launcher_path", [
    ROOT / "scripts" / "start_engine.bat",
    ROOT / "start_engine.bat",
])
def test_start_engine_bat_contract(launcher_path: Path):
    assert launcher_path.is_file(), f"Launcher not found: {launcher_path}"
    content = launcher_path.read_text(encoding="utf-8")

    # Working-directory independence / self-root resolution
    assert "%~dp0" in content, "Launcher must resolve directory using %~dp0"

    # Virtual environment pinning: local project venv only
    assert r"engine\.venv\Scripts\python.exe" in content, (
        "Launcher must target engine\\.venv\\Scripts\\python.exe"
    )

    # Must NOT silently execute global python / py / python3
    naked_py = re.findall(r"^\s*(?:python|py|python3)\s+", content, re.MULTILINE | re.IGNORECASE)
    assert not naked_py, f"Launcher must not invoke global Python directly: {naked_py}"

    # Missing environment guard
    assert "if not exist" in content, "Launcher must check if python.exe exists"
    assert "PESE Python environment was not found" in content, "Missing informative error message"
    assert "docs/installation-guide.md" in content, "Must guide user to installation-guide.md"
    assert "exit /b 1" in content, "Must exit with non-zero code when venv is missing"

    # Explicit canonical configuration: local private profile
    assert "PESE_PROFILE=private" in content, "Must set PESE_PROFILE=private"
    assert "PESE_STORAGE_BACKEND=local" in content, "Must set PESE_STORAGE_BACKEND=local"

    # Verified FastAPI entrypoint on loopback
    assert "engine.api.main:app" in content, "Must target engine.api.main:app"
    assert "--host 127.0.0.1" in content, "Must bind to loopback 127.0.0.1"
    assert "--port 8000" in content, "Must use verified port 8000"

    # Single-worker production mode: avoid fragile --reload
    assert "--reload" not in content, "Must avoid --reload to prevent unbounded watcher overhead"

    # Exit code preservation
    assert "ERRORLEVEL" in content or "EXIT_CODE" in content, "Must capture and preserve exit code"
    assert re.search(r"exit /b (?:%ERRORLEVEL%|%EXIT_CODE%)", content, re.IGNORECASE), (
        "Must propagate real exit code on exit"
    )
