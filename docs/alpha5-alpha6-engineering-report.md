# Alpha.5 and Alpha.6 engineering report

Evidence date: 26 October 2026. Public, privacy-filtered receipts are in
[the acceptance record](evidence/alpha5-alpha6-acceptance.json). Private local
receipts retain the account-specific comparisons; personal identities, Brain
paths, document contents and credentials are excluded from this report.

## 1. Release verdict

**CONDITIONAL.** Alpha.5 and Alpha.6 are public prereleases. The accessible
account's actual desktop installation is **0.1.0-alpha.6**, independently recorded
with source commit `de829ce48ba2c68a59c7e12e1251b14adc3fbbfa`.
The owner completed the real Alpha.5 → Alpha.6 in-app update, connected Google
Drive, and confirmed successful searches against documents already in the Brain.
No test document needed to be added to the personal corpus.

The future-update mechanism is functional: the exact Alpha.5 package updated to
a controlled newer package and to the exact integrated Alpha.6 package in four
native activation/restart cases. This establishes the mechanism for subsequent
releases; it does not certify a future package before that package is tested.

Conditions remain: the inaccessible second Windows account requires acceptance
in its owning context, and the Windows binaries are unsigned. These limitations
do not invalidate the demonstrated update on the accessible account.

## 2. Updater investigation

Inspection of the original installed Alpha.4 assembly established that it selects
its local package cache as the update source. Its GitHub fallback excludes
prereleases. Consequently it cannot be relied on to discover the public alpha
feed. The historical tag and the originally installed assembly also had different
build metadata; installed IL, rather than a source-only assumption, established
the defect. A genuine in-app Alpha.4 → Alpha.5 pass is **not claimed**.

The owner performed the necessary one-time Alpha.5 installer transition in the
normal Windows desktop context, then updated through Alpha.5 Settings. The first
visible Alpha.6 download attempt failed verification/download and left the
installed version unchanged. The owner retried successfully. The exact reason
for that individual failed download was not established; it is not evidence of
a confirmed checksum implementation defect.

The shipped changes retain Velopack 0.0.1298 and package identity
`ManiacSoftwares.PESE`, executable `PESE.exe`, channel `win`:

- `host/PESE.Desktop/SoftwareUpdates.cs` uses the fixed official GitHub source
  with prereleases enabled, serialized operations, real native versions, target
  package notes, bounded metadata requests and a separate long-running download
  budget. Size and SHA-256 are checked before ready/apply.
- `MainWindow.cs` accepts fixed commands only from the trusted WebView document
  origin and displays real check/download/activation state. The frontend carries
  no fake production update response or hardcoded future release.
- `Program.cs` initializes Velopack before the main single-instance gate and
  explicitly disables startup auto-apply. Cached packages require explicit
  activation rather than a second application launch.
- `BrainProcess.cs` requests authenticated engine shutdown and waits for clean
  exit. `engine/desktop/launcher.py` rejects new operations during stopping and
  lets accepted requests drain. Update activation does not force-kill the engine.
- `DesktopPreferences.cs` persists appearance/developer choices per account,
  independently of the engine's changing loopback port and Brain pointer.

**Verification-context correction:** the automation host's MSIX AppData view
exposed a stale redirected application copy. Early tool-side installer/version
and OAuth configuration observations did not prove the real desktop install.
The owner reinstalled the verified Alpha.5 installer normally. A small user-run
native configuration utility subsequently recorded the real Alpha.6 version,
exact commit and matching Brain metadata, and configured the external OAuth
client in that real context. The owner then confirmed Google connected.
Existing canonical Brain files were separately resolved to the physical profile
and matched the before/after receipts. No cache cleanup, ACL change or ownership
bypass was used. Microsoft's
[MSIX filesystem documentation](https://learn.microsoft.com/en-us/windows/uwp/porting/desktop-to-uwp-behind-the-scenes)
explains the redirection that required this distinction.

## 3. Two Windows installations

| Check | Account A: accessible current account | Account B: other profile |
| --- | --- | --- |
| Actual desktop version | Alpha.6, exact commit independently recorded | Not freshly verified |
| Update path | Owner-installed Alpha.5, then real in-app Alpha.6 | Pending owner-context acceptance |
| Installation | Per-user Velopack layout, updater/package directory present | Inaccessible; topology not established |
| Brain | Same saved pointer, identity, schema 1 and 11 documents | Historical report of 222 documents only |
| Search | Owner confirms normal existing-corpus results | Not verified |
| Google | External Desktop client configured; owner confirms connected | Not inspected or changed |

The relationship between the two installations is still unknown. Account A's
success must not be used to infer Account B's version, installation independence,
credential state or preservation. No data was copied between accounts and no
permissions were bypassed. Disposable account-sentinel tests passed, but they do
not substitute for inspecting the inaccessible real installation.

## 4. Brain preservation

For Account A, read-only before/after receipts establish the same Brain identity,
schema **1 → 1**, documents **11 → 11**, saved pointer hash and Brain manifest
hash. The real-desktop receipt agrees with the physical canonical-file checks.
Document content, profile, privacy and existing appearance were preserved.
The history's previous byte prefix and existing logical database rows were
preserved. Read-only SQLite inspection used a transaction only when the database
was in rollback-journal mode with no WAL; no unsafe immutable live-WAL read was
used as integrity evidence.

Normal app use appended search history and neural shadow observations. The final
recorded database inspection showed seven neural observations, all with
authority **NONE**, with no feedback/audit row loss. Later owner searches may
append more normal observations. Preservation therefore means retained existing
canonical state, not a claim that ordinary app use produced no writes.

The agent did not restore, migrate, reset or upload the active personal Brain.
The configuration utility wrote only the external OAuth client configuration;
its receipt records no Brain modification or credential replacement. The real
Google connection remains intact.

All interruption, corrupt download, checksum, recovery/import, feedback mutation
and forced fixture-process termination tests used marked disposable Brains and
portable installations. Native update tests retained the pointer, canonical
files, profile/privacy, feedback, account sentinel and appearance across real
activation and restart. Accepted searches completed while shutdown drained.

## 5. G1 and discovery

Alpha.6 retains the hardened V2 format and inactive recovery design. The snapshot
allowlist is `pese-brain.json`, `firestore_documents.json`,
`privacy_settings.json`, `behavioural_events.jsonl`, logical
`search-sync-records.json`, and optional `profile/profile.json` with its referenced
avatar. The avatar is intentional canonical binary data. Vector/semantic
indexes, model weights, SQLite files and sidecars, local pointers, writer locks
and credentials are excluded. Export no longer treats rebuildable
`semantic_index/` as portable canonical data.

Logical stable records carry feedback, metadata and audit state across the
three Search Sync tables while retaining neural authority NONE. SQLite remains
the local runtime store. Portable logical records are a foundation for later
platform work; Android execution and record-conflict merging are not certified.

Canonical writer coordination and the desktop writer lock guard capture.
Strict manifest/schema/payload checks reject incompatible, incomplete and
tampered snapshots. Recovery validates and imports into a new nonexistent,
inactive target and commits with a same-volume rename. Desktop in-place Restore
remains disabled and its endpoint returns 409 before mutation. Recovery never
selects the new Brain automatically. Unsupported personalization and malformed
legacy history are refused rather than repaired or silently normalized.

Google uses a separately configured Desktop OAuth client, PKCE and system-browser
loopback consent, Drive app-data scope and DPAPI credentials outside the Brain.
The scoped transport constrains Google endpoints, redirects/proxies and
thread/task ownership; disconnect epochs prevent late credential persistence.
Search remains available without Google. This is optional manual backup and
separate recovery, not automatic two-way synchronization.

The real-service disposable test passed authorization/account identity, upload,
listing, verified download, new-directory recovery and source preservation. Its
own synthetic cloud snapshot was deleted and its temporary grant/credentials
were revoked/cleared. All **175** final Alpha.6 Python engine files matched that
Google-tested runtime byte-for-byte. Separately, the owner connected the actual
installed app after configuration; no personal backup was run for acceptance.

Cold recovered-Brain startup was caused chiefly by rebuilding local embeddings.
The host now reports rebuild phases and allows a bounded 15-minute startup,
requiring both ready progress and authenticated healthy API status. Valid local
caches are atomically saved and reused; interrupted cache writes retain old
bytes. Models, embedding order/normalization and ranking math were not changed.

| Native fixture measurement | Cold | Warm | Cold / warm peak Python working set |
| --- | ---: | ---: | --- |
| Separate idle run | 234.260 s | 10.264 s | 2,833,137,664 / 525,844,480 bytes |
| Interrupted rebuild, resumed under parallel I/O load | 271.777 s | 49.516 s | 2,831,077,376 / 526,503,936 bytes |

Both runs reached **212 documents, 1,314 passages and 1,314 vectors**, with grounded
search. In the loaded run, passage embedding took 205.939 s and document embedding
44.073 s. Interruption targeted only the owned fixture Python process; canonical
and source state survived and the writer lock was reacquired. These are measured
fixtures, not the inaccessible historical 222-document Brain or a performance
guarantee for other hardware.

Discovery runs after the primary search and uses that search's index generation.
Actual WPF/WebView2 checks returned results and Related Searches for six queries,
one eligible positive PAA case, typo correction and visible feedback controls,
without discovery errors. Other queries correctly left PAA empty under its
evidence gates. Separate HTTP tests exercised positive PAA, LIKE feedback and its
existing +2.0 adjustment, offline isolation and Restore refusal. Native startup
pixel captures were blank and are excluded as visual proof; progress protocol,
authenticated readiness, valid WebView captures and owner search confirmation
provide the reported evidence. MAAE ranking/retrieval, Search Sync adjustment math
and neural authority remain unchanged.

## 6. Source and tests

The initial G1 work was preserved in checkpoint `ed03240` before updater
integration. Bootstrap work used `codex/alpha5-update-genesis`; integrated G1 work
used `codex/g1-recovery-hardening`. The unpublishable controlled update target
used a separate `codex/alpha6-update-test` worktree.

Principal source areas are the native files listed in section 2,
`engine/startup_progress.py`, semantic provider/index cache code,
`engine/desktop/{launcher,offline}.py`, `engine/brain/`, `engine/sync/`, API and
Settings/discovery integration. `engine/evaluation/synthetic_history.py` makes
the public startup dependency available in a clean checkout. Staging includes
tracked Python sources only. An empty private Brain stays empty; demo seeding
requires explicit demo mode.

| Gate | Alpha.5 | Alpha.6 |
| --- | --- | --- |
| Python tests | 332 passed | 413 passed |
| Host tests | 24 passed | 24 passed |
| TypeScript / Next production export | Passed | Passed |
| WPF publish / isolated runtime import and dependencies | Passed | Passed |
| Package/feed identity, version, source provenance and privacy checks | Passed | Passed |
| Native update acceptance | Two exact-base cases | Two exact-target cases |

Two existing Python deprecation warnings remain. The four native cases used
default and Unicode/space-containing custom Brain paths, real Velopack package
activation and restart, and exact package SHA-256 matching. Default cases
covered offline/no-notes/duplicate/partial/checksum failures, interrupted
fixture-only updater activation, explicit retry and an accepted search pending
at shutdown. WPF cases displayed package notes and preserved a nondefault
appearance. The controlled target is explicitly acceptance-only and was never
published. The integrated target is the exact public Alpha.6 payload.

The clean-asset provisioner extracted **19,765** pinned runtime/model assets from
the verified public Alpha.4 package without importing private data. Logical
payload sizes were 1,074,662,085 bytes for Alpha.5 and 1,074,795,995 for Alpha.6.
Concurrent packaging exhausted C: temporary space and failed before publication.
Packaging was retried from the same tested stages using isolated D: temporary
directories; the resulting artifacts passed verification and native acceptance.

Post-publication changes affect tooling/documentation only: explicit release
version, build root outside the checkout, build-local TEMP/TMP, caller environment
restoration, publisher PATH restoration and an isolated temporary profile for
HTTP acceptance. A deliberate model-preflight failure verified restoration of
all 16 scoped variables and caller directory without opening a real Brain.
The 24 host tests passed again. The isolated-profile HTTP test passed six query
cases, positive PAA, feedback preservation, offline boundaries, optional Google,
search after sync rejection and clean engine exit. Syntax and diff checks cover
these follow-ups; published payloads/tags were not rebuilt or replaced.

Build and publication instructions are in
[release engineering](release-engineering.md). They pin .NET 10.0.402,
CPython 3.12.10, Velopack 0.0.1298 and dependency lockfiles. They document isolated
portable native acceptance rather than running fault tests against the owner's
installed updater. Publication requires exact matching source, package and
native acceptance receipts.

## 7. GitHub

Official repository: [yasirk2026/pese](https://github.com/yasirk2026/pese).
Both releases are prereleases, with complete installer, full package and feed
assets. Every uploaded artifact was downloaded and compared before publication;
anonymous availability was checked afterward. No delta package is claimed.

| Release | Exact source commit | Public release |
| --- | --- | --- |
| Alpha.5 | `87475c03f786d7f1b26bb53b631a3bb903c1e71d` | [v0.1.0-alpha.5](https://github.com/yasirk2026/pese/releases/tag/v0.1.0-alpha.5) |
| Alpha.6 | `de829ce48ba2c68a59c7e12e1251b14adc3fbbfa` | [v0.1.0-alpha.6](https://github.com/yasirk2026/pese/releases/tag/v0.1.0-alpha.6) |

| Artifact | SHA-256 |
| --- | --- |
| Alpha.5 PESE-Setup.exe | `470abe4f9edd8698d7e1c0dc017dfa7d83a9383465101dd5a83895f2b4686e2b` |
| Alpha.5 full.nupkg | `795df970557c5d26c87297f242a00424a2c009fbb1dfc19e3f02150b068af8c4` |
| Alpha.6 PESE-Setup.exe | `1c754334330a5ef2b3f00193485979482abcc9b96d7e67f90e968543b59a6f4f` |
| Alpha.6 full.nupkg | `ae5d1cf5fbdc58c2ec29b63f3cb5a50bb2c2ef22cae77136792669acd6a12adf` |

The linked acceptance record contains feed, compatibility metadata and notes
hashes too. The original Alpha.4 annotated tag
`703e4a3ec9eb254e0e04058e0be48843ad05fee7` still resolves to
`428a9e603d68d0f3d4ee7cbe344338eac9a70393`; its assets were not replaced.
Source integration uses normal fast-forward pushes. Alpha.6 draft uploads ran in
parallel with Alpha.5 verification, with an additional verified-public-Alpha.5
prerequisite before making Alpha.6 public.

The final reviewed tooling and report commits follow the immutable release
commits on `main`; they do not change what the two release tags identify. The
completed handoff has no tracked or untracked source changes outstanding.
Ignored private evidence, fixture/build directories and the local configuration
utility are retained outside the public source/artifacts. Credential and known
private-value scans found no matches in the release source. Binaries are
**unsigned**: hashes establish consistency, not publisher identity or SmartScreen
reputation.

## 8. Exact user-facing release notes

The following blocks reproduce the packaged and published Markdown files.

### Alpha.5

```markdown
# PESE Alpha 5

## Added
- Settings shows the installed version, available update, package release notes and download progress.
- An explicit **Update and restart** action downloads and verifies the package through Velopack.

## Fixed
- Alpha update checks use the official GitHub prereleases instead of the installation's local package cache.
- Duplicate update operations are blocked; failed checks and downloads leave local search available.
- Update activation waits for the search engine to drain its requests and exit cleanly.
- Cached packages do not auto-install during startup or a second application launch.
- Clean-checkout builds include the public evaluation dependency required by engine startup.
- Rebuilt local vector caches are saved atomically so the next launch can reuse them.
- Appearance choices persist per Windows account across engine restarts and updates.
- An empty private Brain stays empty during startup; demo notes are only seeded in explicit demo mode.

## Improved
- Cache-free startup shows local rebuild progress and waits for verified search readiness.

## Known limitations
- Alpha.4 requires a one-time Alpha.5 installer transition because its updater selects the wrong source.
- Windows binaries are unsigned. SHA-256 checksums do not provide a Windows publisher signature or SmartScreen reputation.
- This updater bootstrap does not include the G1 Google Drive backup/recovery or discovery repairs under review.
- Full updates replace the bundled Python runtime and can take several minutes on this Windows environment. Wait for Velopack to finish and restart PESE.
```

### Alpha.6

```markdown
# PESE Alpha 6

## Added
- Optional Google Drive backup to the app's private Drive storage, with verified recovery into a new, inactive Brain folder.
- Portable snapshot format V2 carries canonical records and logical Search Sync feedback. Search indexes rebuild locally.

## Fixed
- Grounded discovery runs after the primary search and uses that search's index generation, restoring eligible You Might Also Ask and Related Searches.
- Backup validation rejects incompatible, incomplete or tampered snapshots before recovery.
- Snapshot version metadata reflects the packaged application version.

## Preserved
- Alpha.5's native updater, explicit activation, clean engine shutdown, local rebuild progress, atomic vector cache and per-account appearance preferences.
- MAAE ranking, retrieval and Search Sync adjustment math; neural shadow models retain zero ranking authority.

## Known limitations
- Drive is optional backup and separate recovery, not automatic two-way synchronization or multi-device conflict merging.
- In-place desktop Restore remains disabled. Recovery does not activate the new folder automatically.
- Unsupported personalization payloads and malformed legacy history are refused safely; this release does not repair or migrate personal data.
- Google OAuth testing access requires an approved test account and a separately configured Desktop client.
- Windows binaries are unsigned. Checksums do not provide a publisher signature or SmartScreen reputation.
- Full runtime updates and a first local index rebuild can take several minutes.
```

## 9. Remaining work

**Next smallest task: perform read-only installation/Brain inventory in Account
B's normal owning Windows context, before attempting its update.** Record the
resolved installation and pointer paths privately and compare installation roots
with Account A to establish whether any state is shared. No ACL or ownership
change is needed or authorized for that check.

Then close that account's PESE, record identity/schema/count, pointer and canonical
hashes, logical feedback state, profile/privacy and credential presence without
printing credentials. If it is Alpha.4 and its installation is confirmed safe to
update, use the verified one-time Alpha.5 installer, then its in-app Alpha.6
update. After restart verify version/commit, same pointer/identity/count and
existing data, settings, search and independent Google state. Do not infer any
of this from Account A. Do not run fixture fault cases on the real Brain.

Other established limitations are unsigned Windows distribution; full-runtime
update size/time; a potentially several-minute first local rebuild; externally
configured Google Desktop OAuth and approved test-user access; safe refusal of
unsupported legacy payloads; no active in-place Restore, automatic two-way merge
or Android runtime acceptance; and the native pixel-capture limitation described
above. General UI automation was unavailable because its native helper failed
initialization, so actual personal-install actions were performed by the owner.
There is no evidence supporting a new ranking defect or a need to modify the
owner's documents following the successful existing-corpus searches.
