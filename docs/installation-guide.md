# Installing PESE Phase 2

Verified target: Windows x64, CPython 3.12.10, Node.js 24.13.0 and npm 11.10.1. Other operating systems and Python versions have not been clean-install tested. This is a local application; bind the unauthenticated API and CMS to loopback.

## Python

Run from the project root in PowerShell:

```powershell
py -3.12 -m venv engine/.venv
./engine/.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
./engine/.venv/Scripts/python.exe -m pip check
```

`requirements.txt` includes the pinned runtime closure in `requirements.lock.txt`. Development requirements add pytest and its dependencies. The CPU PyTorch wheel uses the official PyTorch CPU index. An internet connection is required for an uncached installation. No global Python packages are needed. The verified clean environment did not inherit system site packages.

## Local synthetic demo

In the engine terminal:

```powershell
$env:PESE_PROFILE = 'demo'
$env:PESE_STORAGE_BACKEND = 'local'
./engine/.venv/Scripts/python.exe -m uvicorn engine.api.main:app --host 127.0.0.1 --port 8000
```

The demo creates a synthetic corpus under `engine/data/demo_runtime/`. Its documents, history settings and vector-cache location are separate from the legacy personal store. History starts disabled. The public seed includes history, countries, technology, science, a fictional console, synthetic personal notes, a procedural article, FAQs, links and both short and longer pages. Startup seeds only an empty store.

Optional `PESE_DATA_DIR` selects another runtime directory. Choose a new empty directory for an isolated demo. Python reads exported environment variables; it does **not** automatically load the root `.env.example`.

Existing users can select `PESE_PROFILE=private` or leave the profile unset to keep the legacy `engine/data/firestore_documents.json` store. This does not migrate, overwrite or publish that corpus. Back up local data before changing profiles or resetting seed pages. For Windows Command Prompt, `start_engine.bat` (or `scripts/start_engine.bat`) provides the canonical launcher using this private local contract.

## Frontend

In a second terminal:

```powershell
cd web
npm ci
$env:NEXT_PUBLIC_ENGINE_API_URL = 'http://localhost:8000'
npm run build
npm run start -- --hostname 127.0.0.1 --port 3000
```

Open [PESE](http://localhost:3000). For development, `npm run dev` replaces the last two commands. Set `NEXT_PUBLIC_ENGINE_API_URL` **before building**: it is compiled into client JavaScript. `web/.env.local` can hold this local URL; never add credentials there. `.env.example` contains placeholders and local URLs only.

The API permits browser origins `http://localhost:3000` and `http://127.0.0.1:3000`. A different frontend port requires a deliberate CORS configuration change. An engine on another loopback port works when the compiled frontend URL points to it.

## Models and first startup

Semantic retrieval uses Fastembed/ONNX with `BAAI/bge-small-en-v1.5`, 384 dimensions, on CPU. The first uncached startup downloads the embedding model through Fastembed and embeds the corpus. Later startups can reuse installed model files and matching vector-cache entries. Download time is additional to measured startup time. If download or initialization fails, inspect engine logs; startup/index publication is not declared successful.

PESE-QA checkpoints are optional, excluded from the public source export and unnecessary for ordinary search. The reader stays experimental and runs only on explicit diagnostic/laboratory paths. `PESE_PREWARM_QA=1` opts into its startup warmup when compatible checkpoint and tokenizer files are present. The default is `0`. Do not train or fetch private checkpoints to make baseline search work.

Use a single API worker. Each process owns an in-memory generation; multiple workers and external Firestore writers are outside the verified consistency model. Avoid `--reload` during measurements and avoid watching virtual environments or audit copies.

## CMS and recovery

Open [CMS](http://localhost:3000/admin). **Publish & Index** saves and indexes a page. **Save Draft** removes it from public search. FAQs remain attached to their source. Saving, editing, deleting or unpublishing builds the next lexical, passage, semantic, FAQ and graph generation before publication.

If the canonical save succeeds but indexing fails, the API returns `503` with `SAVED_NOT_INDEXED`; search returns `INDEX_NOT_CURRENT`. The saved document remains recoverable in the CMS. `/health` exposes the canonical version, active versions, failure stage and error type. Resolve the reported problem, then retry `POST /api/index`. Do not interpret an HTTP error as proof that the canonical write was rolled back.

The local canonical JSON uses a flushed temporary file and atomic replacement. Derived API generations are rebuilt in memory on startup. A crash does not make a partially written derived generation authoritative. This is a single-process local publication design, not a distributed transaction protocol.

## Optional Firebase

Local mode is the default even when unrelated cloud credentials exist in the environment. Firebase requires `PESE_STORAGE_BACKEND=firestore` explicitly. For an emulator, configure `FIRESTORE_EMULATOR_HOST` and the emulator project environment. For a real project, configure `GOOGLE_APPLICATION_CREDENTIALS` outside the repository and the project environment required by Firebase Admin.

Do not check in service-account JSON, private keys, real project identifiers or user documents. Configured Firebase initialization errors are surfaced instead of silently falling back to JSON. Cloud permissions, Firestore rules, concurrent external writers and public deployment were not accepted by this local release audit.

## Verification

```powershell
./engine/.venv/Scripts/python.exe -m pytest engine/tests -q
cd web
./node_modules/.bin/tsc.cmd --noEmit
npm run lint
npm run build
```

The source-only demo test run passed 126 tests with two skips for absent optional QA artifacts. The installed-checkpoint environment passed 128 tests. Two warnings remain: Starlette TestClient deprecates its current httpx integration, and checkpoint metadata uses datetime.utcnow(). Frontend lint has zero errors and 29 existing warnings; see the final report. No Python type checker or lint configuration is currently enforced; all release Python sources pass syntax parsing.

Useful evaluation tools include `engine.evaluation.independent_runner`, `phase2f_studies`, `qa_v2`, `release_manifest` and `release_hygiene`. Existing development datasets are exposed regression data. The final holdout is also regression data after its recorded reveal. `holdout_run` refuses to overwrite its output file; do not describe a repeat evaluation as blind.

## Troubleshooting and release limits

- A blank SERP with browser network errors: check the engine port, compiled API URL and allowed frontend origin. An HTTP 200 HTML shell does not prove hydrated search works.
- An empty result set can be deliberate evidence gating. Inspect developer traces before changing thresholds.
- Failed CMS save: inspect the structured response and `/health`; the canonical document may already be saved.
- Missing neural checkpoint: normal search still works. Two optional model tests skip in a source-only installation.
- Model initialization errors: check model-download access and available disk space; do not replace real embeddings with a mock in production.
- `npm audit` reported zero production advisories and five high development dependency paths through the same `braces` advisory during this audit. Its proposed automatic remedy downgraded the Next lint stack across a major version. No forced downgrade was applied; review the development advisory separately.

Do not publish this working directory wholesale. Private stores, histories, checkpoints, old reports and local environment files coexist with source. The readiness inventory is `docs/audit/phase2f-public-readiness.json`; ignored files and the absence of a Git repository are not proof of a clean publication history.
