# N3-F FIRST CONTACT — 27 October 2026

Historical first-contact evidence. The later normal Windows training update is
documented in `n3f-windows-update.md`; its collection policy supersedes the small
pilot and separate-distribution proposal below. All counts here describe the
earlier local acceptance, not a public release or subsequent owner activation.

Starting revision: `6c8caef0e22c4f5786eaba8853c41edee7853b68`, clean at entry.
This work prepares the first owner session. It does not establish that Neural
Genesis improves real owner searches. The base weights, tokenizer, parameter
count and ranking/answer gates have not been tuned or enlarged.

## 1. Original Brain safety and recovery

The real saved pointer selects the existing default Brain under
`%LOCALAPPDATA%/ManiacSoftwares/PESE/Brain`. Its exact identity remains in the
private local safety receipt; the validator reports **2 documents**.
The installed application identifies itself as `ManiacSoftwares.PESE`, channel
`win`, version `0.1.0-alpha.5`, source `87475c03f786d7f1b26bb53b631a3bb903c1e71d`.
PE metadata agrees: product PESE, company Maniac Softwares, matching product
version. `n3f-work/application-identity.json` preserves this metadata and EXE hash.
The safety receipt records the OS-resolved pointer file, under this process's
package LocalCache, separately from the selected Brain path above. Evidence is
from the calling Windows account context; activation must select the matching
Brain identity through the native owner flow.

`scripts/n3f_owner_safety.py` used the existing G1 format-2 capture and restore
mechanisms. It checks the writer lock, receives metadata/counts from the existing
Brain validator, hashes files without inspecting passage text, creates an
allowlisted archive, and restores into a new inactive directory. No diagnostic
opens a serving engine or changes a pointer. G1 necessarily validates/copies the
canonical payload internally for backup and recovery; no private passages or
queries are displayed, interpreted or used for training.

Final evidence: `D:/Personal Evil Search Engine/n3f-work/owner-safety-final/`.
`safety-receipt.json` records successful checks for Brain ID, count, exact document
bytes (therefore document identities), canonical payload hashes, logical feedback,
desktop validation, excluded experimental assets, and unchanged original full
file tree, pointer and installed application hashes. The original and inactive
restore both have 2 documents. The backup ZIP, its SHA-256, manifest member hashes
and recovery receipt remain beside that receipt. Recovery was **not activated**.

The initial sandbox attempt could not open the existing writer lock with the
approved mechanism's required access. The owning-context run passed; the lock
was never removed or bypassed. No G1 allowlist, restore, Drive or OAuth contract
was changed. No remote Google Drive upload/download or account acceptance was
performed. This is local backup/recoverability evidence.

## 2. Installed Windows BETA readiness

Owner BETA now has a separate package ID `ManiacSoftwares.PESE.OwnerBeta`, update
channel `win-owner-beta`, profile `ManiacSoftwares/PESE Owner BETA`, window title
and single-instance identity. Stable defaults keep their original identity and
paths. The BETA's public update feed is disabled; local reviewed packages are
required. The existing affirmative, hash-bound per-Brain agreement remains the
authority for experiment participation. No inherited environment flag selects
the native BETA channel.

Review found and fixed an integration gap before owner activation: Python's
create/connect command formerly saved to its default stable pointer even when
the native host used a separate BETA profile. The host now passes its exact
settings path; Python restricts it to the two application profile pointers and
rejects other targets before creating a Brain. Legacy source callers retain the
stable default. Both an actual native connect and regression tests now verify
that BETA writes its own pointer and leaves a stable-pointer sentinel unchanged.
The real owner pointer was never selected through the incomplete BETA flow.
Final pointer-aware native preflight: `n3f-work/beta3-pointer-preflight`, passed.

The native acceptance harness now records installed identity and tests damaged
artifact fallback to the exact MAAE order plus explicit rollback to the pinned
base. This is a damaged-pointer mechanics fixture, **not a trained candidate,
promotion or quality improvement**. The existing tests cover actual neural
ranking, affirmative UI agreement, feedback provenance, pause, offline boundary,
restart persistence, safe exit and unchanged canonical documents.

**Final actual Setup + installed native acceptance: passed, BETA.3.** The
installed locator reports `installed: true`, package `ManiacSoftwares.PESE.OwnerBeta`,
channel `win-owner-beta`, version `0.1.0-beta.3`. The real installed executable
passed native Brain selection/pointer isolation, UI agreement and scope, actual
neural ranking/order change, membership preservation, feedback provenance,
pause, offline blocking, restart, damaged-pointer MAAE fallback, exact base
rollback, exit and unchanged canonical documents. Real stable application and
owner pointer hashes remained unchanged across installation.

Receipts: `n3f-work/installed-beta3/installed-acceptance.json` and
`native/native-beta-acceptance.json`. Seven synthetic observations were captured;
these are not owner evidence. The first model attempt fell back; the second
applied and changed order. Its successful cold call was 3588.38 ms / 219,709,440
sampled bytes; a warm call was 10.03 ms / 228,818,944 bytes. The initial failure
is retained, not represented as uninterrupted inference success. Cold-start
fallback remains an operational limitation.

The final package's 203 Python source files match its provenance record and its
base files match the application pin. Full package SHA-256:
`42184609012d521a65bdfc208ff7a644d1ec582edb223f7d8e30dc05cd5479d8`.
Setup SHA-256:
`34e9fca65aeb50f913ddeb8137ea1f7e44c09caf8056ae86c109d5fb1eb01f66`.
Artifacts: `n3f-work/artifacts-beta3-safe/`. The executable is under
`n3f-work/installed-beta3/install/current/PESE.exe`. Local packages are unsigned
acceptance artifacts and were not published. Both final stable and explicit
BETA builds succeed. Source/model receipts distinguish dirty acceptance source
from a clean production release; changes remain uncommitted.

The BETA.1 installer actually installed its separate package and registered its
uninstaller without changing stable PESE. Its native acceptance failed because
the diagnostic entry point had not initialized the Velopack locator. The entry
point now runs after the existing startup hooks. A later preflight also exposed
an incorrect test expectation: its synthetic dislike had changed saved Search
Sync preferences, so fallback must compare with a fresh MAAE run using those
same preferences. Both failures are retained. Corrected preflight in
`n3f-work/beta3-preflight2` passes all UI/inference/pause/offline/restart/fallback/
rollback/exit checks, with 4 synthetic events and unchanged documents. No model
or production ranking threshold changed in response to these harness failures.

The actual native BETA.1 → BETA.2 updater passed with a Unicode Brain path and
local feed: real restart, canonical files/pointer, profile/account sentinel and
feedback rows preserved. Bad metadata, interrupted download and checksum-failure
checks passed. This is a **portable disposable update installation**, separate
from real Setup acceptance; it does not claim a stable-owner update. A forced
interruption of update activation was not exercised in this new BETA run.
Receipt: `n3f-work/updater-beta1-to-beta2/acceptance.json`.

The BETA.1 and BETA.2 packages each pass privacy/channel/source verification:
203 packaged Python sources match their recorded hashes, and base weights and
tokenizer match application pins. These are acceptance-only packages from a
dirty working tree based on the stated starting revision, not clean releases.

## 3. Independent English evaluation

The protocol is `docs/neural/n3f-protocol.md`. Protected runs require named human
source/label review, every corpus document judged, and reviewed expected answers
or abstentions. The runner refuses missing judgments, model reviewers and exact
overlap with exposed development data. Human review must additionally check
semantic/family overlap; hash checks alone do not prove independence. The runner
freezes packet/model/source hashes before execution, preserves per-query results
and never trains or promotes anything.

The owner's three natural questions are preserved separately outside Git in
`n3f-work/evaluation/protected-owner-pending.json` and the adjacent review note.
No private Brain search was performed for those questions. The owner confirmed
the paraphrases and supplied reference answers, including one incomplete quote.
These remain outside Git. Exact source/revision binding and complete relevance
labels remain pending human review; missing evidence is not inferred. **There is no
completed independent human English evaluation.**

A separate **open, unreviewed fictional diagnostic** has 24 everyday questions
in 12 families, including paraphrases, hard negatives, dates, negation, conflict,
changed facts, missing evidence, identity and preferences. Its specification
grades were authored independently of Neural Genesis predictions, but are not
human-reviewed truth and cannot certify broad English quality. The opened
diagnostic must not later be renamed a blind protected set.

Owning-context result, unchanged base and real local BGE hybrid retrieval:

| Measurement | MAAE | MAAE + Neural Genesis |
|---|---:|---:|
| Mean NDCG@10, unreviewed proposals | .767355 | .798110 |
| MRR | .729167 | .770833 |
| Recall@10 | .875 | .875 |
| Unanswered questions | 21/24 | 21/24 |
| Warm end-to-end median | 4.52 ms | 10.57 ms |
| Warm end-to-end p95 | 5.93 ms | 15.22 ms |
| First cold query | 24.60 ms | 2900.69 ms |

Three questions improved in NDCG, one regressed and five changed order. The date
category regressed by .184535. Mean delta is +.030756; grouped 95% interval
[-.030756, +.092268] includes zero. There were zero membership violations,
66 applied model calls and zero model fallbacks. The first pair for each question
is excluded from warm summaries; response caches are cleared for each run while
semantic query embeddings may remain warm. Literal answer checks are proxies;
human output review is still needed. Most answer abstentions persisted.

Results: `n3f-work/evaluation/diagnostic-3/results.json`; complete frozen input,
model pins, orders, judgments, traces, answers and latency samples remain there.
An earlier process-sandbox run is preserved in `diagnostic-2`: 66 model failures
fell back, with approximately five-second latency and no ranking changes. It
does not count as successful model evaluation. Repeating in the owning context
changed no weights, thresholds, questions or labels.

## 4. Actual owner activation

**Not activated.** There is no owner agreement, chosen private document scope,
permission change, experiment sidecar creation, private search or owner model
training in this work. Synthetic in-app consent must not be mistaken for the
owner's participation. The pending owner decision is explicit acceptance plus
the document IDs to include; journals stay off and the proposed first-pilot
retention is 7 days. Backup existence does not imply experimental consent.

## 5. Real learning evidence

Real owner searches executed: **0**. Real feedback receipts: **0**. Trusted owner
relevance labels: **0**. The three supplied questions and reference answers are
owner input for protocol design, not observed feedback or admitted training examples. Synthetic
native acceptance events are reported separately.

Collection is now strictly scoped: unselected documents produce no persisted
experimental observation, including metadata. This closes the earlier behavior
that retained metadata-only events for out-of-scope targets. Journal permission,
source revision, review and immutable pool controls remain in force.

## 6. Training and promotion

New owner/candidate training runs: **0**. Promotions earned: **0**. Base model:
111,426 parameters; weights SHA-256
`4100367d3b0c9e60d40da204e85174a67aabe3d9c32ea160b721aefcb51dcb5e`;
tokenizer SHA-256
`a0d09cd0f4c9deee928da01392f7e2d69cb2ff0a819dd4c67f9bce589ffa8b32`.
These hashes match the starting application pin. No final protected set was used
for tuning. Prior rejected N3-E candidates/results are preserved.

The local admission gate remains at 12 reviewed pairs, both classes and three
disjoint training/validation document families. Promotion additionally needs 12
complete heldout query pools, three disjoint heldout families, independence from
ancestry, gain versus current, comparison to MAAE/base, answer/resource safety
and category gates. The current 2-document Brain and zero reviewed pairs cannot
meet those gates. Do not lower the thresholds to force a pilot training run.

## 7. Verification and remaining blockers

Final whole suite including the metadata-only inventory and pointer-isolation
fixes: **479 passed, 2 deliberately deselected**, zero failures/errors/skips,
73.06 seconds. The
deselected tests fit candidate parameters; FIRST CONTACT does not require another
training run. Two pre-existing deprecation warnings remain. Tests use disposable
Brains, explicit profiles, local BGE files and blocked external test networking.
Receipts and JUnit output: `n3f-work/regression-pointer-final/`. Stable publish succeeds;
no frontend source changed. Exact base bytes are unchanged. `git diff --check`
passes. The earlier focused metadata/host run additionally passed 27 checks.

Independent human source/relevance/answer review, actual owner agreement and
scope, genuine feedback collection, and enough diverse disjoint evidence for
training/promotion remain required. The diagnostic's regression and uncertainty
preclude a claim that real owner search improved. No automatic external sharing,
public release, branch push or private-data training was performed.

**NO EVIDENCE = NO ANSWER.**
