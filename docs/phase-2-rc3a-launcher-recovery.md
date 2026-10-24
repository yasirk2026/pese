# PESE Phase 2 RC3-A — Launcher Recovery Report

## Root Cause

`start_engine.bat` failed to provide a reliable entry point after Phase 2 installation and reproducibility updates due to five concrete defects:

1. **Unbounded `--reload` Watcher Overhead**: The legacy launcher passed `--reload` to Uvicorn, activating `StatReload` over the entire repository root. This caused the watcher to continuously scan hundreds of thousands of files across `engine\.venv` (PyTorch, heavy ML wheels) and `web\node_modules`, causing excessive CPU and disk churn, spawning complex subprocess trees, and directly violating `docs/installation-guide.md` line 56 ("Avoid `--reload` during measurements and avoid watching virtual environments or audit copies").
2. **Missing Canonical Environment Configuration**: The launcher did not explicitly set `PESE_PROFILE=private` or `PESE_STORAGE_BACKEND=local`, leaving startup behavior vulnerable to ambient environment variables or cloud credential defaults.
3. **Fragile Working-Directory Assumptions**: The launcher assumed execution strictly from `scripts/` via a hardcoded `cd /d "%~dp0\.."`, breaking if launched from other working directories or from the project root.
4. **Missing Environment Guard & Diagnostic**: If `engine\.venv\Scripts\python.exe` was absent, the script failed with a raw shell error (`'engine\.venv\Scripts\python.exe' is not recognized...`) without actionable guidance to consult `docs/installation-guide.md`.
5. **Exit Code Suppression**: The launcher did not capture or propagate Uvicorn's errorlevel (`exit /b %ERRORLEVEL%`), obscuring startup failures.

---

## Fix

The launcher was repaired to strictly enforce the Phase 2 installation contract:

- **Directory Resolution**: Dynamically resolves the project root from `%~dp0` whether executed from `PESE/`, `PESE/scripts/`, or an external working directory.
- **Strict Virtual Environment Pinning**: Targets `engine\.venv\Scripts\python.exe` directly. Never falls back to global `python`, `py`, or `python3`.
- **Pre-flight Environment Validation**: If the project virtual environment is not found, displays:
  ```text
  PESE Python environment was not found.

  Expected:
  engine\.venv\Scripts\python.exe

  Please follow docs/installation-guide.md first.
  ```
  and terminates immediately with exit code `1`.
- **Explicit Profile Pinning**: Explicitly exports `PESE_PROFILE=private` and `PESE_STORAGE_BACKEND=local`.
- **Canonical Uvicorn Invocation**: Runs `"%PYTHON_EXE%" -m uvicorn engine.api.main:app --host 127.0.0.1 --port 8000 %*` without `--reload`, preserving server output and single-worker integrity.
- **Exit Code Propagation**: Captures `%ERRORLEVEL%` upon server exit and returns it cleanly via `exit /b %EXIT_CODE%`.
- **Availability**: Provided identically at `scripts/start_engine.bat` (canonical) and `start_engine.bat` (root convenience).

---

## Files Changed

- `PESE/scripts/start_engine.bat` — Canonical engine launcher script.
- `PESE/start_engine.bat` — Root convenience engine launcher script.
- `PESE/docs/installation-guide.md` — Minimal note documenting `start_engine.bat`.
- `PESE/engine/tests/test_launcher.py` — Focused static regression contract tests.
- `PESE/docs/phase-2-rc3a-launcher-recovery.md` — RC3-A recovery report.

---

## Verification

### 1. Run from Project Root (Test A)
- Executed `start_engine.bat` and `scripts\start_engine.bat` from `C:\Users\Yasir\Desktop\Personal Evil Search Engine\PESE`.
- Engine started cleanly on `http://127.0.0.1:8000` with single server process.

### 2. Run from Another Directory (Test B)
- Executed `C:\Users\Yasir\Desktop\Personal Evil Search Engine\PESE\start_engine.bat` while working directory was `C:\Users\Yasir\Desktop`.
- Resolved project root cleanly and started FastAPI on `127.0.0.1:8000`.

### 3. Local Venv Used
- Verified process binary was strictly `engine\.venv\Scripts\python.exe`.

### 4. Environment Profile
- Verified environment variables `PESE_PROFILE=private` and `PESE_STORAGE_BACKEND=local` active.

### 5. Health Endpoint Check
- `GET http://127.0.0.1:8000/health`:
  - HTTP Status: `200 OK`
  - `status`: `"healthy"`
  - `storage_backend`: `"local"`
  - `publication.stage`: `"ready"`
  - `canonical_document_version`: `"6d0d10e8ad03b547"`
  - `documents_indexed`: `212`
  - `passages_indexed`: `1314`

### 6. One Search Smoke Test
- `GET http://127.0.0.1:8000/api/search?q=search`:
  - HTTP Status: `200 OK`
  - Returned 20 ranked hybrid results, query intent classified, zero errors.

### 7. Clean Shutdown
- Sent interrupt/termination signal to launcher task.
- Process exited cleanly, child terminated, and port `8000` was immediately released with zero orphaned processes.

### 8. Missing-Environment Handling (Test C)
- Executed launcher in an isolated directory without a virtual environment.
- Printed expected error message referencing `docs/installation-guide.md`.
- Exited with code `1`.

### 9. Port-Conflict Behavior
- Tested startup while port 8000 was held by an existing instance.
- Second launcher reported visible `[Errno 10048]` socket bind collision from Uvicorn without task-killing.
- Exited with non-zero exit code (`3`). Original engine process remained healthy and unaffected.

### 10. Automated Regression Suite
- Ran `pytest engine/tests`: 160 passed (including `test_launcher.py`), 0 failed.

---

## Unchanged

No search retrieval, ranking, BM25, dense embeddings, semantic indexing, RRF fusion, answer extraction, QueryFrame, candidate generation, Featured Answers, PAA, Related queries, autocomplete, PESE-QA, Neural Genesis, CMS behavior, ranking constants, corpus files, or private user data were modified.

---

## Unrelated Issue Observed

- `scripts/start_engine.ps1` still retains legacy `--reload` flag. Preserved without modification in accordance with task boundaries.

---

## Verdict

```text
RC3-A ACCEPTED
```
