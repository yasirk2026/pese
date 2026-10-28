# N3-F normal Windows training update

Starting source: `6c8caef0e22c4f5786eaba8853c41edee7853b68`.
The owner superseded the initial two-document restriction and explicitly requested
a normal update with mandatory acceptance and application shutdown on decline.
This document records implementation and preflight evidence; published artifact
and installed-update claims require the separate exact-package receipts.

## Application and privacy behavior

Alpha.7 uses the explicit `standard_update_beta` distribution profile with
`aggressive_learning_beta` capability. Package `ManiacSoftwares.PESE`, channel
`win`, `%LOCALAPPDATA%/ManiacSoftwares/PESE`, single-instance identity and saved
Brain pointer retain their established contracts. The default stable build and
the separate Owner BETA build remain available. Capability never means consent.

Before search indexing starts, the native first-start screen presents the full
versioned agreement and current document metadata. Acceptance requires an
unchecked affirmative checkbox. Decline or closing the agreement closes updated
PESE before its engine starts. A successful acceptance first creates an approved
G1 backup, verifies an inactive restore and exact document bytes, and probes the
pinned model using a fixed public synthetic passage. Runtime failure disables
neural ranking and permits deterministic MAAE. It does not start training.

Approval can include every current document, of any collection size, minus
explicit exclusions. The server binds the reviewed snapshot to Brain ID and the
actual Windows account SID hash; inherited environment variables cannot select
another account. Future IDs require explicit approval. Deleting an ID removes
its authorization. Other accounts and Brains never inherit participation.
Legacy ordinary feedback preferences and restrictive exclusions may migrate;
legacy neural/research/journal/community consent does not.

The agreement and Privacy & Intelligence screen prohibit sensitive material,
explain possible memorization and the limits of deletion, and state that local
processing is not risk-free. Journals and community contributions default off.
Excluded passages are never forwarded to experimental ranking or stored in
research contexts. Normal indexing and canonical Search Sync feedback continue
under their existing settings. No private content, queries, vectors or private
checkpoints are automatically uploaded.

Raw observations, queued examples and reviewed labels expire after seven days
by default. Private job datasets and checkpoint files use configured file age.
Maintenance prunes storage while the application runs. Consent and operational
receipts persist until Clear; privacy exclusions remain with BETA disabled.
Canonical documents, ordinary feedback/history, packaged base, backups and
outside copies are outside this policy. Newer models may retain older influence.
Clear removes only this account's experimental queue, labels, jobs and models.
Drive snapshot/restore, OAuth and canonical-backup allowlists are unchanged.

## Measured source and native preflight evidence

The clean synthetic offline suite passed **493 tests**, with zero failed,
errored, skipped or deselected tests, including candidate fitting in disposable
directories. TypeScript and production Next export passed. Explicit Alpha.7 WPF
publish with SDK 10.0.403 passed without warnings. Later release-verifier privacy
checks and their fixture metadata are verified separately before packaging.

Retained failures: an initial TTL test incorrectly left its SQLite handle open;
the test fixture now closes it. A later full test process reported a Windows
native access violation without a final receipt. Nine focused checks, two
1,000-call SID stress runs and two clean full runs subsequently passed. The
native exception is unreproduced, not represented as a diagnosed product fix.

`n3f-update-work/native-preflight-1` contains real WPF/WebView2 receipts and
screenshots using only marked public synthetic Brains:

| Check | Result |
|---|---|
| Decline with 200 documents | Closed before engine start, no enrollment |
| Accept with 200 documents | All 200 approved; backup and inactive restore verified |
| Accept with 400 documents | All 400 approved; backup and inactive restore verified |
| Both acceptance cases | Original document bytes and pointer preserved; journals off; no training |
| Normal-package 200-document search | Real neural order change after one timeout fallback |
| Successful cold inference | 4,961.42 ms, 227,004,416 sampled bytes |
| Warm inference | 10.73 ms |
| Pause, offline, restart, invalid pointer | Passed |
| Fallback and rollback | Exact MAAE order, exact pinned base restored |
| Exit | Experimental collection stopped; canonical documents unchanged |

Both first-start safety probes fell back. A direct fixed-public worker diagnostic
completed successfully in 5.93 seconds, exceeding the unchanged five-second cold
budget. The successful native ranking attempt followed an earlier fallback;
cold-start reliability remains a limitation. Warm inference retains its 150 ms
budget. No ranking bounds, answer gates, quality thresholds or model weights were
changed to make these checks pass.

These preflight runs used acceptance-only source at the starting revision with
working changes. They are not exact clean-release installation evidence.
`pack_training_update.ps1` requires a clean commit, explicit distribution flags,
fresh frontend build, model pins, native dependency audit and source provenance.
`verify_release.py --training-update` verifies ordinary package/feed identity,
private-payload exclusion, engine source hashes and frozen model bytes.
The final focused scope/privacy/release-fixture run passed **25 tests**. A separate
two-document native startup with the packaged base deliberately held aside passed
in MAAE mode; the original base was restored with its exact SHA-256 afterward.
`publish_windows_release.ps1` still requires exact-package native updater,
restart, default/Unicode pointer preservation, UI and interrupted-update evidence.
It must never be weakened to publish an untested artifact.

An installer-mechanism fixture may use package ID
`ManiacSoftwares.PESE.AcceptanceOnly` with the same application payload to preserve
the existing stable uninstall registration. Such a test must disclose its
different installer identity and cannot claim a normal-ID Setup execution.

## Model readiness, owner activation and learning evidence

The fixed base remains 111,426 parameters. Weights SHA-256:
`4100367d3b0c9e60d40da204e85174a67aabe3d9c32ea160b721aefcb51dcb5e`.
Tokenizer SHA-256:
`a0d09cd0f4c9deee928da01392f7e2d69cb2ff0a819dd4c67f9bce589ffa8b32`.
There was no base retraining, enlargement or protected-set retuning.

The earlier unreviewed fictional diagnostic had three ranking improvements and
one regression; its grouped interval included zero. It is not independent human
evidence. Owner-supplied questions and answers remain outside Git. Source binding,
complete relevance review and protected evaluation remain unfinished.

Neither the original owner Brain nor the other Windows account's Brain was
activated or used in automated training. The original backup/inactive restore
passed before this expansion; its exact private metadata remains local. Real
owner searches, feedback receipts and trusted labels collected in this work: **0**.
Real owner training and quality-earned promotions: **0**. Synthetic candidate tests
prove lifecycle mechanics only. Rejected candidates and failed receipts remain.

Admission still needs twelve reviewed pairs, both relevance classes and three
disjoint training/validation source families. Promotion requires sufficient
protected heldout pools, independence including ancestry, gain against the active
model, comparisons to MAAE/base and answer/resource/category safety. Collection
size and agreement alone cannot supply relevance truth or earn promotion.

Remaining evidence gaps: exact clean-artifact update/installer acceptance until
their receipts pass, actual per-account owner activation, independent human
English evaluation, genuine feedback, enough diverse trusted examples, and
improved cold-start reliability. This update offers experimental capability;
improvement in real owner search has not been established.

## Exact release acceptance — 28 October 2026

[Alpha.7](https://github.com/yasirk2026/pese/releases/tag/v0.1.0-alpha.7)
is published on the normal `win` channel, from application source
`5365e1343fbcd243b11b0fde2eadb633851aa956`. All eight GitHub assets were downloaded,
matched against local SHA-256 values and checked for anonymous availability.
An interrupted draft-verification download resumed using validated HTTP ranges;
publication occurred only after complete-file hashes passed. The tag and assets
were not replaced.

Actual Alpha.6-to-Alpha.7 updates passed on two 200-document synthetic Brains:
standard-path WPF Settings and Unicode-path interrupted staging/retry. Canonical
data, feedback, pointers, appearance, synthetic Drive configuration and DPAPI
storage were preserved. Neither updater enrolled its Brain. The actual updated
normal-ID installation passed neural order changes, pause, offline, restart,
damaged-pointer exact MAAE fallback, base rollback and exit. Its first neural call
fell back; the successful cold call was 4,952.44 ms and warm call 10.46 ms. The
updated normal-ID decline check closed before engine startup, preserving 200
documents and the pointer.

Real Setup and full-current-collection native startup acceptance passed under
test registration `ManiacSoftwares.PESE.AcceptanceOnly`, preserving the existing
stable installation, pointer and uninstall registration. All 20,495 application
payload files matched the sealed normal release. Only `sq.version` registration
ID, shortcut ID and shortcut locations differ. Installed hashes account for
Velopack consuming the generated execution stub and relocating `Squirrel.exe`
to `../Update.exe`. Normal-ID Setup was not run against the owner installation;
the normal-ID updater and test-registration Setup evidence are distinct.

Reproduce a test-registration installer with `scripts/pack_installer_fixture.ps1`
and its explicit `-CanonicalArtifacts` input. It restores sealed frontend/native
build outputs, then verifies the entire fixture payload and only the three
permitted manifest differences. Do not rebuild Next for this fixture: build IDs
can differ despite identical source. The old `pack_training_update.ps1
-InstallerFixture` path now rejects that unreliable method. The installer runner
supports payload-only verification without owner access, persists its preservation
baseline before Setup, and can resume a marked completed Setup after a verifier
layout assertion. Four synthetic ZIP checks cover expected metadata differences,
changed code, changed version metadata and extra files.

The application/model bytes in the published release remain those of `5365e13`;
the subsequent source changes repair only acceptance tooling and reporting.
Real owner activation, searches, feedback, trusted labels, training and earned
promotions in this work remain zero. Independent English improvement is unproven;
cold timeout fallback remains a measured limitation. The original Brain's final
metadata/hash inventory and recovery evidence remain unchanged. Exact local
receipts are under `n3f-update-work/`; owner questions and private source material
are not included in the public repository or release assets.
