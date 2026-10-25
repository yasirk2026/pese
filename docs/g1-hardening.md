# Google Drive G1 backup contract and recovery boundary

Google Drive is optional backup storage. The selected local Brain remains authoritative. There is no automatic cloud restore, record merge, last-writer-wins replacement, or experimental neural ranking authority.

## Transport version 2

Version 1 archives are explicitly rejected. They are not silently interpreted as the new format.

The allowlisted payload is `pese-brain.json`, `firestore_documents.json`, `privacy_settings.json`, `behavioural_events.jsonl`, `search-sync-records.json`, and an optional `profile/profile.json` with its referenced `avatar.png/jpg/jpeg/webp/gif`. Semantic indexes, vector caches, model weights, machine pointers, locks, credentials and SQLite sidecars are excluded. Nonempty personalization directories fail capture until a portable schema is specified.

Search Sync records use `format: pese-search-sync-records`, `version: 1`, and the three explicit tables `active_preferences`, `feedback_audit_events`, and `neural_shadow_observations`. Fields, stable IDs, timestamps and audit links are preserved. Observations retain `authority: NONE`. SQLite remains the local runtime engine; import builds a new database using the existing canonical DDL. No live database file is uploaded.

Canonical runtime writers and capture share one process-local reentrant barrier. The desktop owns the cross-process writer lock. A separate capture process refuses an active desktop Brain; external editors are unsupported while it is open. Capture validates all required files and references before publishing an archive.

Archives require exact correspondence between the allowlist, manifest and ZIP entries, explicit versions, hashes, sizes and selected identities. Duplicate/aliased paths, duplicate JSON keys, unexpected entries, symlinks, encrypted entries and incompatible records are rejected. Limits are 128 MiB compressed, 512 MiB uncompressed, and an allowlist-bounded file count. Downloaded archives are checked against selected authenticated Drive metadata.

## Recovery

The desktop Restore control is disabled and the API returns 409 before network or file mutation. Host-controlled activation into the running application has not been verified and is not advertised as available.

Offline recovery only creates a **new, nonexistent user-owned directory**. It validates the complete payload, imports logical records into detached SQLite, and runs the desktop Brain validator before a same-volume directory rename. The original Brain and machine-local pointer are never changed. A sibling recovery receipt records validated/complete state. An interrupted receipt prevents an automatic retry; inspect the receipt and retained fixture before choosing a new target. A recovered Brain is inactive until explicitly inspected and connected through the existing native Brain-selection flow. Initialization failure therefore cannot replace the original serving generation.

Example using an already downloaded archive and its explicitly selected metadata:

```powershell
& $EmbeddedPython -B -m engine.sync.recovery_cli $Archive $NewDirectory --brain-id $BrainId --snapshot-id $SnapshotId --sha256 $SelectedDriveDigest
```

The programmatic Drive recovery boundary additionally requires exact file ID, snapshot ID, Brain ID, archive digest and confirmed local content digest. It rechecks local state after download. Divergent histories are preserved separately, never merged or overwritten.

## OAuth configuration

For the packaged desktop, put the Google **Desktop** client JSON at `%LOCALAPPDATA%\ManiacSoftwares\PESE\google-oauth-config.json`. Keep it outside the Brain and source control. Web clients and non-Google endpoint overrides are rejected. Official legacy Google authorization URLs in downloaded Desktop JSON are normalized to the supported v2 endpoint.

The WPF host intentionally removes inherited `PESE_*` variables. Environment-based OAuth configuration is for source development only. The only requested scope is `https://www.googleapis.com/auth/drive.appdata`. Credentials use Windows DPAPI outside the Brain; other platforms need an explicit secure storage adapter. There is no plaintext production fallback.

The system browser handles consent; the loopback callback captures a code and does not claim connection success. PESE reports connected only after token exchange, account identification and credential persistence. Disconnect invalidates pending authorization/refresh before removing local credentials. Remote revocation is reported separately if Google is unavailable.

The Python transport permits exact HTTPS OAuth/Drive endpoints, rejects redirects and proxies, authorizes resolved public TCP address/443 pairs only within the owning thread/task scope, and expires nested permission scopes correctly. This is a trusted-process Python boundary, not an operating-system firewall. Core search, startup and local Settings status do not require Google access.

## Discovery

Primary search completes before PAA/Related requests. Each request carries its primary search ID and uses that search's serving snapshot and top slugs, including debug and typo-recovery searches. PAA retains the real retrieval and Answerability Gate; empty results remain legitimate. Discovery loading/errors are separate from normal SERP results.

## Acceptance boundaries

All mutation tests use disposable Brains. `scripts/accept_g1_runtime.py` exercises real bundled Python HTTP behavior. `PESE.exe --accept-ui <marked-disposable-brain> <private-output-directory>` exercises the WPF/WebView2 supervisor and captures UI evidence without changing the saved Brain pointer. `scripts/accept_g1_google.py` is an opt-in real Google test using a fresh synthetic Brain, a temporary external OAuth profile, manual browser consent, and cleanup of its own cloud artifact.

Successful tests or builds alone do not certify release readiness. Final active-Brain integrity checks must occur in the owning Windows user context; real Google acceptance and cold recovery startup must be reported independently.
