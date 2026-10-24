# PESE Development Guide

## Requirements

- **Python**: 3.10+ (Tested on Python 3.12.10)
- **Node.js**: 18+ (Tested on Node v24.13.0, npm 11.10.1)
- **OS**: Windows / Linux / macOS (Bound to localhost)

---

## One-Command / Two-Command Startup

### Option A: Launch Both Services (One Command)
Run from the `PESE` directory:
```powershell
.\scripts\start_all.ps1
```
*(or on Command Prompt: `scripts\start_all.bat`)*

This opens two dedicated terminal windows:
1. Python Search Engine API: `http://localhost:8000`
2. Next.js Web Frontend: `http://localhost:3000`

---

### Option B: Two-Command Independent Startup

**Terminal 1 — Python Search Engine:**
```powershell
cd PESE
.\engine\.venv\Scripts\python.exe -m uvicorn engine.api.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — Next.js Frontend:**
```powershell
cd PESE\web
npm run dev
```

Open `http://localhost:3000` in your web browser.

---

## Running Unit Tests

To run the complete pytest test suite:
```powershell
cd PESE
.\engine\.venv\Scripts\pytest.exe -v
```

All 18 unit tests cover:
- NLP Normalization, Contractions, Unicode, Stemming, Tokenization
- Multi-field BM25F scoring and Robertson-Spärck Jones IDF
- Passage extraction, density scoring, and date highlighting
- Link graph construction, PageRank, and bounded authority
- Spam detection (keyword stuffing, thin content, vocabulary diversity)
- End-to-end Ranking V1 scoring traces and explainability

---

## Resetting or Seeding the Evil Universe

To re-seed the 24 initial test documents:
```powershell
cd PESE
.\engine\.venv\Scripts\python.exe -m engine.data.seed_corpus
```
*(Or click **Reset Evil Universe** in the `/admin` web interface).*

---

## Firestore Configuration (Optional)

PESE defaults to local file persistence at `engine/data/firestore_documents.json`.

If you wish to connect to Google Cloud Firestore or the local Firestore Emulator:
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Set either:
   ```bash
   # For local emulator:
   FIRESTORE_EMULATOR_HOST=localhost:8080

   # Or for live Google Cloud:
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
   FIREBASE_PROJECT_ID=your-project-id
   ```
3. Restart the Python API. The engine will automatically detect and switch to Firestore with zero code changes.
