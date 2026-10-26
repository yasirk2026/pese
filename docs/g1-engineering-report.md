# G1 recovery, Drive hardening and discovery engineering report

> Historical report from the preceding G1 mission. Its release-blocked verdict describes that earlier candidate. See the [Alpha.5 / Alpha.6 engineering report](alpha5-alpha6-engineering-report.md) for committed release source, packaged acceptance, publication and account-specific results.

## Verdict

**CONDITIONAL implementation; release blocked pending final acceptance.** Unsafe desktop Restore is disabled. The supported recovery boundary creates a new inactive Brain and never overwrites the current Brain. Active-Brain preservation must be checked in its owning Windows user context; this execution context was denied access and did not bypass permissions. Google browser authorization and real transfer results are recorded separately from local and mocked tests.

## Baseline and root causes

Work started on `main` at `428a9e6`, with six modified tracked files plus Flash's untracked sync implementation/tests. Those changes were retained on `codex/g1-recovery-hardening`; no reset, clean, commit, push, tag change or release publication was performed.

The initial isolated suite produced 345 passes and three failures. One path-resolution test was shadowed by the disposable runtime environment; that test now explicitly removes the two higher-priority environment variables when testing a saved pointer. Two frozen-dataset failures were CRLF checkout conversion: LF bytes reproduced the existing manifest hashes exactly. The public payloads were restored to those hashes and a narrowly scoped LF Git rule added. Dataset records, split membership, manifests and model weights were not changed.

Discovery endpoints depended on a primary ranking cache that did not exist when the frontend requested discovery in parallel. Debug searches bypassed that cache entirely. PAA also cooperatively stops while primary retrieval is pending. Discovery now follows primary completion and receives an explicit search context referencing that serving generation. There are no new hardcoded suggestions or relaxed Answerability Gate rules.

## Changes by subsystem

- **Brain capture:** one reentrant boundary across document, profile, history, feedback, observation and corpus-recovery writers; desktop writer registration and refusal of capture by another process; strict complete-state capture.
- **Transport contract:** format 2, logical Search Sync records, deliberate canonical allowlist, avatar preservation, no SQLite/vector/model transport, explicit rejection of legacy format 1 and unknown personalization data.
- **Validation/recovery:** exact archive/manifest membership, hashes, limits, portable paths, JSON/schema/identity checks, metadata agreement; fresh-directory staging, detached SQLite import, desktop validation and same-volume rename with recovery receipts. Existing targets are never replaced.
- **Network/OAuth:** exact HTTPS service paths, resolved public TCP/443 authorization, owner/expiry/nesting checks, no proxies or redirects, worker-thread permission, synchronized credentials, cancellation generations, correct account lookup, no premature connected state, secure platform storage and supported external Desktop configuration.
- **Drive lifecycle:** paginated Brain-filtered listing, explicit identity selection, local divergence confirmation, bounded streaming upload/download, timeouts and owned temporary cleanup. Existing download destinations and SQLite backup destinations are protected from replacement/removal.
- **Product UI:** primary-then-discovery sequencing, independent discovery loading/errors, accurate OAuth state, explicit snapshot browsing/divergence information, disabled Restore with an explanation, and accurate privacy/encryption wording. Existing visual design and SERP controls remain.
- **Verification:** disposable-only safety tests, controlled real loopback socket I/O, actual bundled-runtime HTTP comparison, native WPF/WebView2 capture harness and a separate opt-in synthetic Google acceptance harness.

## Original audit findings

| Finding | Resolution status |
|---|---|
| 1. Unsafe live restoration, WAL, backup and rollback | **Contained and redesigned:** live restoration removed; new-directory recovery tested; original Brain/lock/pointer untouched. Host-controlled active recovery remains unavailable. |
| 2. Runtime activation outside rollback | **Contained:** no hot replacement or serving-generation activation occurs through sync. Recovered copies remain inactive. |
| 3. Wrong Brain/stale snapshot | **Implemented/tested:** explicit file/snapshot/Brain/digest selection; metadata agreement; Brain filtering and local-state recheck; no automatic latest restore or merge. |
| 4. Incomplete archive/schema checks | **Implemented/tested:** exact payload contract, strict versions/identities/records, duplicate/alias/size checks and authenticated-metadata digest verification. |
| 5. Incoherent capture | **Implemented/tested:** shared canonical writer barrier and independent-process refusal; transactional logical database read. External editors remain unsupported. |
| 6. Broken packaged networking | **Implemented/tested and real Google passed:** hostname resolution and numeric connection are tied to scoped capabilities; OAuth worker uses the dedicated transport. Service acceptance was separate from the native UI harness. |
| 7. Excessive/noncomposable network permission | **Implemented/tested:** exact hosts/paths, HTTPS/TCP/443, no wildcard services, task/thread isolation, expiry and nesting restoration. This is not an OS firewall. |
| 8. Vector cache export | **Removed/tested:** caches are excluded from format 2; unknown personalization is refused. |
| 9. SQLite-only portability | **Implemented/tested:** versioned logical export/import preserves IDs, timestamps, audit state and NONE authority; no multi-device merge claim. Android execution remains unverified. |
| 10. OAuth/credential races | **Implemented/tested:** serialized atomic storage, cancellation generations, refresh synchronization, correct account identity and verified-persistence connection state. |
| 11. Packaged configuration mismatch | **Implemented/tested locally:** external Desktop JSON route documented; WPF environment stripping retained. Public source contains no personal configuration. |
| 12. Cleanup/timeouts/memory | **Implemented/tested:** owned temporary directories, bounded streaming transfers, effective transport timeouts/deadlines and preservation of existing destinations. |

## Discovery before and after

Both HTTP runs used the real preserved alpha.4/candidate embedded runtimes with separate disposable clones of the accessible 212-document source-reference corpus. This is not fresh verification of the inaccessible active Brain reported to contain 222 documents. Only discovery/search/feedback results from the legacy comparison are used; absent legacy sync endpoints were not exercised.

| Query | Alpha.4 PAA / Related | Candidate PAA / Related |
|---|---:|---:|
| when did I buy my bicycle | 0 / 0 | 0 / 5 |
| Japanese beginner roadmap | 0 / 0 | 0 / 3 |
| Next.js server components vs client components | 0 / 0 | 0 / 4 |
| PageRank internal linking | 0 / 0 | 0 / 3 |
| japanise begnner roadmp | 0 / 0 | 0 / 3 |
| PESE | 0 / 0 | 2 / 3 |

The five requested queries produced no passing PAA questions in that corpus under the existing gate; candidates were evaluated where available. The PESE probe demonstrated positive PAA eligibility, and both returned questions were independently re-run through real retrieval and checked for a featured answer from the same source. The native candidate rendered these same counts. Typo recovery, featured answers, source attribution and feedback controls remained present.

## Verification and evidence

The final complete source regression passed **403 tests, zero failures, zero skips in 27.51 seconds**. The separate host suite passed **13 tests in 0.47 seconds**. Two pre-existing deprecation warnings remain. TypeScript checks, Next.js static production build, self-contained .NET 10 WPF publish and staging of 69 pinned distributions passed. `git diff --check` passed. No production ranking or neural-authority source changed.

The final private candidate's 173 staged Python source files matched the workspace byte-for-byte; root, search and Settings HTML matched the final production build. No acceptance engine processes remained after verification.

Commands used (with the interpreter/SDK and environment bound to the existing local tools):

```powershell
& $Python -B -u -m pytest -q -o faulthandler_timeout=45 -p no:cacheprovider --basetemp $DisposableTestDirectory
& $Python -B -m pytest host/tests -q -p no:cacheprovider --basetemp $DisposableHostTestDirectory
& web/node_modules/.bin/tsc.cmd --noEmit --incremental false
npm.cmd run build # from web/
& $Dotnet publish host/PESE.Desktop/PESE.Desktop.csproj -c Release -r win-x64 --self-contained true -o $CandidateDirectory --no-restore
& $Python -B scripts/stage_desktop.py $CandidateDirectory
& $Python -B scripts/accept_g1_runtime.py $CandidateDirectory $MarkedDisposableBrain $PrivateReport
& $Python -B scripts/accept_g1_runtime.py $PreservedAlpha4Directory $OtherDisposableBrain $PrivateBeforeReport --legacy
& $CandidateExe --accept-ui $MarkedDisposableBrain $PrivateEvidenceDirectory
& $CandidatePython -B scripts/accept_g1_google.py $ExternalDesktopClientJson $PrivateGoogleReport $PrivateProgress
git diff --check
```

Python runtime storage, OAuth profiles and all mutation fixtures were isolated. The regression suite explicitly blocks external network calls; a dedicated controlled test exercises actual local TCP I/O through resolution/connection policy. Mocked Drive tests are not described as real Google verification.

The actual candidate `PESE.exe → WPF → WebView2 → embedded Python → FastAPI` harness passed six queries, native DOM rendering, offline-boundary checks, disabled-Restore rejection and engine-exit checks. Private screenshots include grounded PAA, Related Searches, normal SERP results, typo recovery, feedback controls and Brain Settings. Screenshots, runtime logs and reports remain in the ignored private build area, not public source.

Real Google acceptance **passed** using the candidate's bundled Python and the normal external-configuration loader with a temporary profile and a fresh synthetic Brain. It verified manual system-browser authorization, account identity retrieval, real multipart upload, Drive listing, checksum-verified download, recovery into a new directory with matching canonical digest, source preservation, deletion of the test cloud artifact, successful remote revocation and local credential removal. No personal Brain contents were uploaded. This service-level Google test was separate from the WPF UI harness; real token refresh and a connected-account Settings screen were not independently exercised. The initial Google Testing-audience `403 access_denied` was resolved by the project owner adding the test account; the application did not bypass that restriction.

## Implemented, tested and not yet verified

| Boundary | Evidence/status |
|---|---|
| Canonical capture, logical records, validation, ownership, OAuth races and cleanup | Implemented; full Python regression and focused disposable safety tests passed. |
| Native search/discovery/feedback controls/offline boundary/shutdown | Verified in the actual separately staged WPF/WebView2 candidate, including positive PAA and Related screenshots. |
| Real Google authorization/upload/list/download/new-directory recovery/delete/revoke | Passed in the candidate's bundled Python service with synthetic data and an isolated profile. |
| Active user's existing Brain and saved pointer | No mutation attempted; fresh preservation verification pending because access was denied. |
| Existing installed alpha.4 application | Preserved; the user's installation was not overwritten or used as a destructive test target. |
| Active-Brain restore, automatic activation/rollback and cold large-Brain startup | Not production-verified; desktop Restore remains disabled. |
| Android execution, multi-device merging and real refresh-token expiry | Not independently verified; no such completion claim is made. |

## Preservation and release limits

- The active Brain was inaccessible. Its last-known identity/count were supplied by the user and were not represented as fresh verification. No ownership change, permission bypass, creation, reset, replacement or pointer update was attempted.
- Five canonical files in the accessible source-reference Brain were hashed before/after the acceptance work and remained identical. Five checkpoint files also matched the preserved alpha.4 build byte-for-byte. This evidence does not substitute for the active-Brain check.
- Existing alpha.4 release artifacts/tag and installed application were not overwritten. The executable exercised was a separately staged candidate using the actual packaged architecture.
- Cold vector rebuilding for the full disposable corpus exceeded the existing startup acceptance budget. Warm-cache native startup passed. Large cache-free recovered Brains need an independently verified rebuild/startup path before recovery activation can be advertised.
- Desktop Restore remains unavailable. There is no verified automatic host activation/restart/rollback feature, no CRDT or multi-device conflict merging, and no Android runtime acceptance.
- Real Google acceptance passed after manual browser consent and the provider's test-user configuration was corrected. No cloud artifact or local credentials from that acceptance remain. Public production OAuth verification is a separate release consideration.

## Files and working tree

Affected files are `.env.example`, `.gitignore`, `.gitattributes`; `engine/api/main.py`; `engine/brain/{coordination,events,profile,recovery}.py`; `engine/desktop/{launcher,offline}.py`; `engine/discovery/{history,models}.py`; `engine/indexing/{__init__,store}.py`; `engine/search_sync/feedback_store.py`; the `engine/sync/` contract/manifest/payload/logical/snapshot/restore/recovery_cli/transport/drive_client/oauth/credentials/service/sqlite_safety modules; focused sync/discovery tests, `engine/tests/conftest.py` and the pointer-isolation test; `host/PESE.Desktop/{MainWindow,Program,UiAcceptance}.cs`; Settings/search/frontend API files; the two acceptance scripts; and these engineering documents. Frozen public dataset line endings were restored to existing manifest hashes without logical changes.

The branch remains `codex/g1-recovery-hardening`, based on `428a9e6`, with uncommitted implementation work including the preserved initial G1 changes. No new commit SHA exists. Credentials, private documents, archives, screenshots, machine-local pointers and machine-specific paths are excluded from the public changes.

**Recommendation:** do not publish G1 as production-safe recovery. Complete the owning-user active-Brain integrity check, and retain disabled desktop Restore until its activation lifecycle and cold recovery startup are independently verified. Manual backup and discovery have local/native evidence plus the separate successful real Google service acceptance.
