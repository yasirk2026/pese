# PESE — Personal Knowledge Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows_x64-0078D6.svg)](https://github.com/yasirk2026/pese)
[![Release: 0.1.0-alpha.6](https://img.shields.io/badge/Release-v0.1.0--alpha.6-green.svg)](https://github.com/yasirk2026/pese/releases/tag/v0.1.0-alpha.6)

**PESE** searches your personal knowledge locally using fielded BM25F, local dense embeddings and grounded extractive answers. Search has no hosted dependency. Optional native updates contact GitHub; optional Google Drive backup sends an explicitly requested canonical snapshot to the app's private Drive storage.

See the [Alpha.5 / Alpha.6 engineering report](docs/alpha5-alpha6-engineering-report.md), [release procedure](docs/release-engineering.md) and [G1 backup/recovery contract](docs/g1-hardening.md). Existing Alpha.4 clients require a one-time installer transition; Alpha.5 establishes the in-app update path.

---

## Key Highlights

- **Offline-first privacy**: Search and the Brain work locally. Updates contact the official GitHub feed. Drive backup requires separate configuration and authorization; it does not own local search.
- **Hybrid Retrieval Architecture**: Combines fielded BM25F ranking, dense vector semantics (via local ONNX FastEmbed `bge-small-en-v1.5`), and Reciprocal Rank Fusion (RRF k=60) for robust keyword and conceptual relevance.
- **Grounded Featured Answers**: Conservative extractive QA pipeline extracts direct answers with exact source document attribution and passage score verification, abstaining safely when confidence thresholds are not met.
- **Discovery Intelligence & "You Might Also Ask"**: Generates grounded discovery questions and related search topics derived from corpus graph connectivity and passage relationships.
- **Native Windows Host**: Packaged as a single-instance Windows WPF application with Microsoft Edge WebView2, managing the background Python engine supervisor, lifecycle synchronization, and IPC security.
- **Local Brain authority**: Velopack updates replace application files while preserving the separate Brain and settings. G1 provides optional backup and inactive-directory recovery; it does not merge devices or restore over a running Brain.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      PESE.exe (WPF Host)                    │
│  - Single Instance Gate (Named Pipe & Mutex)                │
│  - Microsoft Edge WebView2 (Authenticated Loopback Origin) │
│  - Brain Process Supervisor & Job Object Ownership          │
│  - Velopack Hooks and Explicit Update Activation           │
└──────────────────────────────┬──────────────────────────────┘
                               │ Loopback IPC (X-PESE-Token Auth)
┌──────────────────────────────▼──────────────────────────────┐
│                  Packaged CPython 3.12.10 Engine               │
│  - FastAPI / Uvicorn (Bound strictly to 127.0.0.1:0)        │
│  - Offline Boundary (Socket Interception)                   │
│  - Fielded BM25F Lexical Inverted Index                     │
│  - Local ONNX FastEmbed Dense Semantic Index               │
│  - SQLite Search Sync Feedback & Behavioural Signals        │
│  - Conservative Grounded Extractive QA Engine               │
└──────────────────────────────┬──────────────────────────────┘
                               │ Static Export Served Over Loopback
┌──────────────────────────────▼──────────────────────────────┐
│                    Next.js Static Frontend                  │
│  - Modern Visual Genesis Search UI & Shell                  │
│  - Search Autocomplete & Typo Recovery Banners              │
│  - "You Might Also Ask" Accordion with Direct Query Links   │
│  - Related Searches Chips & Quick Discovery                 │
│  - Search Sync Feedback Controls (👍 / 👎)                  │
│  - Real-Time Developer Diagnostics & Ranking Traces        │
└─────────────────────────────────────────────────────────────┘
```

---

## System Requirements

- **Operating System**: Windows 10 / 11 (x64)
- **Runtime**: Microsoft Edge WebView2 Evergreen Runtime (preinstalled on modern Windows)
- **Memory**: Acceptance ran on a 16 GB host. A 212-document cold rebuild peaked at about 2.83 GB for Python alone; allow additional memory for Windows and WebView2. Lower-memory minimums are not certified.
- **Disk Space**: About 1.1 GB of application payload, plus the separate Brain, derived caches and update packages. Full updates need space for a replacement payload and its approximately 457 MB compressed package.

---

## Repository Structure

```
├── engine/              # Python search engine core
│   ├── brain/           # Brain storage format, integrity, & recovery tools
│   ├── desktop/         # Desktop launcher, offline boundary, & security
│   ├── index/           # Fielded BM25F lexical index & schema
│   ├── neural/          # Dense vector embedding pipelines & ONNX models
│   ├── nlp/             # Tokenization, passage extraction, & text processing
│   └── qa/              # Grounded extractive question answering
├── host/
│   └── PESE.Desktop/    # C# WPF desktop host application (.NET 10)
├── web/                 # Next.js frontend application (TypeScript, Tailwind CSS)
├── scripts/             # Windows release build, acceptance, & packaging automation
└── tests/               # Python unit, regression, and desktop boundary test suite
```

---

## Development Setup

### 1. Prerequisites
- [.NET 10.0.402 SDK](https://dotnet.microsoft.com/)
- [Node.js 20+ / 24](https://nodejs.org/)
- [Python 3.12.10](https://www.python.org/)

### 2. Python Engine Setup
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.lock.txt
pytest engine/tests/
```

### 3. Frontend Setup
```bash
cd web
npm install
npm run build
```

### 4. Desktop Host Build
```bash
cd host/PESE.Desktop
dotnet build -c Release
```

### 5. Full Windows Release Build
To package the self-contained installer and Velopack update feed with embedded CPython and local neural models, prepare the pinned assets described in [release engineering](docs/release-engineering.md), then run:
```powershell
pwsh -NoProfile -File .\scripts\release_windows.ps1 -Version "0.1.0-alpha.6" -BuildRoot <new-build-directory> -AssetSource <offline-assets-directory> -Dotnet <dotnet-10.0.402.exe> -Vpk <vpk-0.0.1298.exe>
```

---

## Security & Privacy Model

1. **Strict Loopback Binding**: The Python FastAPI service allocates an ephemeral loopback port (`127.0.0.1:0`) and accepts connections only with a per-launch cryptographically random 64-character token (`X-PESE-Token`).
2. **Offline Enforcement**: The `engine.desktop.offline` boundary dynamically intercepts Python socket calls, preventing outbound HTTP/HTTPS connections outside loopback.
3. **Data Isolation**: Your personal documents, notes, search history, and feedback databases reside in `%LOCALAPPDATA%\ManiacSoftwares\PESE\Brain` (or your chosen directory) and are never packaged into Git, release installers, or update deltas.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Release engineering

See [release engineering](docs/release-engineering.md) for pinned offline assets, exact-source builds, disposable update acceptance, per-user installation safety and deliberate publication gates. Alpha.5 remains a candidate until installed-update acceptance and publication complete.
