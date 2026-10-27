# N3-E engineering report — 27 October 2026

Neural Genesis now has actually trained relevance weights, a trained advisory
feedback classifier, bounded experimental search influence, and a working local
queue → review → training → evaluation → promotion/rollback implementation.
The staged Windows app exercised real inference and consent. These are engineering
milestones, not independent evidence of general English quality or a successful
continual-learning improvement. The synthetic journal candidate did not improve
the measured probe and was rejected. The owner's private Brain was not used for
training, searching, native acceptance, or backup experiments.

## 1. Revisions and scope

Initial: `2f6cd182db8151abe22c31cb95394bbcc2ddfcd0`, clean branch
`codex/g1-recovery-hardening`. Final executable implementation:
`3f7a57fe0e889323f5b8c67e31034ab0ca0ed509`. Native execution used the same runtime
and model bytes at `7829d30210c59563030ed014cc6f6e1d0f2c156e`; the subsequent
artifact-only commit preserves those tested tokenizer/manifest bytes in Git,
preventing Windows line-ending normalization from breaking future checkouts.
This report and public verification
receipts are in the subsequent documentation commit; the final response supplies
that exact final Git revision. No branch push, tag, installer release, public
deployment, or owner installation replacement was performed.

The reproduced baseline passed 464 tests in 34.43 seconds. Historical claims were
checked against source and isolated fixtures, not accepted as fresh evidence.

## 2. Architecture and data flow

```text
Hybrid retrieval → existing hard evidence gates → MAAE base scores
  → consented BETA: verified local artifact → isolated CPU relevance scores
  → bounded ordinal delta → existing preferences → deterministic answer grounding

Server presentation receipt + explicit reaction + eligible scoped passage
  → hard provenance/revision/dedup/conflict checks + advisory meaning classifier
  → uncertain/review/preference/quarantine queues
  → explicit receipt-bound owner relevance review + immutable split role
  → disjoint training/validation + protected evaluation snapshot
  → bounded subprocess trains a new candidate; active weights stay immutable
  → current/base/MAAE + protected regression + answer/resource checks
  → reject/review OR atomic local experimental pointer + previous checkpoint
```

Stable signing remains separate: `TRUSTED_RELEASE_KEYS` is still empty. The native
host's compiled `NeuralChannel` defaults to `stable`; inherited development flags
cannot select the BETA. Explicit `aggressive_learning_beta` builds additionally
require the current affirmative per-Brain agreement and neural permission.

## 3. Dataset provenance

DATA-BETA-1 is original CC0 synthetic specification data, generated without scraped
text, private documents, owner queries, cloud accounts, or model-produced labels.
Grades mean unrelated (0), topical (1), or specific retrieval utility (2). They
are not factual truth or answer-correctness certifications.

| Partition | Queries | Pairs | Purpose |
|---|---:|---:|---|
| Training | 128 | 768 | Weight fitting and training-only BPE |
| Validation | 64 | 384 | Candidate/checkpoint selection |
| Calibration | 48 | 288 | Temperature selection after candidate selection |
| Generated acceptance | 64 | 384 | Opened after selecting candidate A |

Names, exact query/prose templates, source families and passages are partitioned.
The generator covers eight topics, two main query families, paraphrases,
cross-sentence causes, wrong entities/relations, incomplete records, date
conflicts, and limited spelling variants. Topic/cause skeletons remain shared.
This is a narrow synthetic distribution: broad everyday English, relative dates,
rich temporal reasoning, arbitrary partial queries and independent real-world
generalization remain unproven. Split hashes and generator identity are packaged
in `engine/neural/assets/basic_english_beta_v1/dataset-manifest.json`.

## 4. Actual relevance training and artifact

`PESE-English-Beta-1:a300` is a dedicated retrieval cross-encoder initialized
separately from Rel-0: two 64-wide Transformer layers, four heads, 128-wide feed
forward, 128-token context, actual 496-token training-only BPE, 111,426 parameters.
Training used graded utility BCE, AdamW, batch 32, two CPU threads and fixed seeds.

Candidate A: seed 20261027, 300 steps, 55.281 seconds. Candidate B: seed 20261028,
600 steps, 106.156 seconds. A was chosen on validation before calibration or
generated acceptance was opened. No retuning against the final partition occurred.

| Artifact | SHA-256 |
|---|---|
| `weights.pt` | `4100367d3b0c9e60d40da204e85174a67aabe3d9c32ea160b721aefcb51dcb5e` |
| `tokenizer.json` | `a0d09cd0f4c9deee928da01392f7e2d69cb2ff0a819dd4c67f9bce589ffa8b32` |

The 460,008-byte checkpoint and tokenizer are application-pinned experimental
assets. Exact bytes are preserved by Git attributes. A local BETA manifest cannot
pass the official production signature verifier. Private adaptations bind to the
Brain and carry checkpoint, evaluation, dataset and training-lineage provenance.

## 5. Development versus independent evaluation

| Measurement | Candidate A | Candidate B |
|---|---:|---:|
| Validation decisive balanced accuracy | 95.0521% | 92.1875% |
| Validation NDCG@10 | 0.993677 | 0.983840 |

A's generated acceptance: decisive balanced accuracy 88.6719%, NDCG@10 0.999297,
MRR 1.0, pairwise accuracy 0.998698, Brier 0.050208, ECE 0.111805 after selecting
temperature 0.75 on calibration. Decisive classification excludes grade 1.
Temperature does not change the runtime ordinal ranking policy.

All of these labels are synthetic specifications. The named acceptance split is
not independently human-adjudicated acceptance. High ranking metrics on this
template family do not establish broad understanding. The full measured report is
`docs/neural/n3e-english-experiment-v1.json`; candidate B's worse result is retained.

## 6. Feedback-judge architecture

Hard rules retain admission authority. The trained advisory model is a 15-feature,
three-class linear softmax over explicit reaction/reason features. It suggests
relevance review, preference or ambiguity. It receives no model relevance score
as truth and cannot grant verified labels. Six deterministic outcomes remain:
verified evidence, review candidate, preference, ambiguous, contradictory, invalid.

The reason classifier was actually trained for 250 steps, seed 42, on 28 original
synthetic reason examples. Its weights/bias are shipped in
`engine/neural/assets/feedback_judge_beta_v1.json`.

## 7. Feedback evaluation

Unseen wording: 9/12 correct (75%), ECE 0.056122. Errors include “not about what i
asked”, “beautiful styling”, and “interesting despite no answer”. This small test
is not an independent human evaluation and confidence is not reliable enough for
trusted admission. Zero trusted false admissions is a structural property of the
human-review guard, not a measured claim of perfect classifier precision.

Tests exercised missing/forged provenance, stale revisions, repeated reactions,
contradictory votes, model-claimed review, cross-role reassignment, unknown schema,
scopes, exclusions and resource/storage bounds. Contradictions remain quarantined;
an explicit conflict-resolution workflow is not yet implemented.

## 8. Concrete feedback outcomes

| Experience | Outcome |
|---|---|
| LIKE without clarification | Ambiguous; no relevance label |
| DISLIKE + “not relevant” on a valid eligible result | Review candidate; no automatic negative |
| “wrong information” or “outdated” | Clarify objective/revision; no automatic relevance label |
| “presentation” or “duplicate” | Preference only |
| Forged receipt or stale source revision | Rejected/quarantined |
| Repeated identical action | Deduplicated; no extra independent weight |
| Conflicting LIKE/DISLIKE | Quarantined; prior review removed, protected split retained |
| Explicit owner grade 0/1/2 + rationale bound to exact receipt | Accepted local supervision, subject to current scope/revision |

The positive/negative grades exercised in tests are explicit synthetic fixture
reviews, not invented observations from the owner.

## 9. Actual ranking influence

On 64 validation queries through real MAAE admission/scoring, 63 orders changed.
Mean NDCG@10 delta was +0.033875, grouped bootstrap interval [0.025474, 0.042791].
There were zero membership/gate violations and zero new wrong-answer *proxies*.
That answer check uses synthetic utility and literal grounding, not human answer
adjudication. Offline research used actual model predictions directly to avoid
transport overhead; separate native acceptance exercised the isolated process.

The final native hybrid query “what made iris revise neural search?” swapped
positions 5 and 6 while preserving all 20 returned members. It did not improve the
top answer. This proves influence, not useful native ranking improvement. No MAAE
gate was relaxed. At most six admitted candidates receive deltas bounded by 3% of
their base score and 75% of the median adjacent score gap. Failure retains MAAE.

## 10. Operational local pipeline

The per-Brain versioned SQLite sidecar stores up to 2,000 events and 16 MiB of
UTF-8 payload, with 30-day default retention (configurable 1–90 days). Events have
exact query, target/revision/evidence hashes, rank, MAAE/neural/preference deltas,
model identity and reason. Only explicitly scoped passages are retained; other
eligible observations are metadata-only. Oversized passages are metadata-only.
Queue failure cannot break search.

Training requires 12 reviewed pairs across three document families and both
positive/negative classes in disjoint train/validation groups. Protected evaluation
roles cannot become training roles. New checkpoints retain hashed ancestry, so
past training material cannot later masquerade as independent evaluation.

Jobs run manually, one at a time, with cancellation, 100 fine-tuning steps,
180-second training and 60-second evaluation subprocess deadlines, two CPU
threads, sampled 512 MiB training and 384 MiB inference limits. These are sampled
working-set budgets, not kernel allocation ceilings. Jobs/models have count,
age and 128 MiB-per-category disk budgets; SQLite/file overhead is additional.
There is no idle/battery-aware automatic training scheduler yet.

## 11. Journal adaptation evidence and limits

Notes require explicit IDs plus separate journal permission. A deterministic
title question and passage create unlabelled review candidates. No synthetic
question, LIKE, high confidence or unobserved result is converted to a gold label.

A disposable synthetic journal fixture completed real 100-step fine-tuning,
changed weights, evaluated the candidate and kept the base because protected
heldout pools were insufficient. One measured run took 11.36 seconds and produced
checkpoint `96cf6e532a3919a2258f92a2f8a0622ab988671e27f739eeea234ee80fbe3e69`.
An additional eight-pair synthetic note probe gave 4/8 binary decisions for both
models and identical NDCG 0.630930. Broad synthetic NDCG worsened from 0.993677 to
0.987490. This is failed improvement, preserved in
`docs/neural/n3e-local-learning-probe.json`; no more tuning followed that probe.

No owner journals were opened. Removing/excluding/deleting a source drops all
private adaptations and returns to the public base; selective parameter unlearning
is not claimed. Re-entry with reduced scope does the same. Editing a source makes
pending snapshots stale and prevents their promotion; it does not erase all past
influence from an already active adaptation.

## 12. Functional dashboard

The static `/neural-genesis/` route shows actual channel, agreement, checkpoint,
inference, fallbacks, queue categories, job receipts and privacy settings. Controls
call local token-protected APIs for consent, scope/retention, neural on/off,
pause/resume, exact example review, protected roles, expected answer/abstention,
journal candidate generation, train/evaluate/cancel, rollback, exit and confirmed
deletion. Insufficient data yields an explicit refusal. The real WebView2 run
accepted the agreement and document scope through these UI controls. Native
agreement/dashboard screenshots were visually checked.

## 13. Promotion and rollback

The preregistered local gate needs 12 fully reviewed heldout query pools, three
disjoint document families, independence from candidate ancestry, ≥0.01 NDCG gain
over current, no worse than −0.02 against MAAE/base, ≤0.05 regression in every
protected broad category, zero new wrong answers/gate violations, and actual
isolated inference health. Thresholds were not lowered after failures.

Evaluation binds the exact checkpoint and source snapshot, rechecks permissions
and revisions before promotion, and atomically preserves the previous pointer.
Tests promoted the genuinely trained fixture checkpoint using an explicitly
labelled *numerical policy fixture*, loaded it, and rolled back to the exact base.
That demonstrates replacement/recovery mechanics. No locally trained candidate
earned automatic promotion from independent quality results in this work.

## 14. Windows build and execution

Restored isolated .NET SDK 10.0.403 from Microsoft's release metadata, checked
SHA-512 `7a114c318fa7f1d9822991b534b2814d0e78386ceda816b371f5141acefe741d87ccb606ede06cadac8f9ac5070e32b708a67bbd1619ff5e5a7858a27874ef48`.
Source: [official release metadata](https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json).
Existing SDK/application installations were not replaced. NuGet dependencies
were restored from the official feed into the experiment workspace.

Default stable host build: zero warnings/errors, final repeat 2.97 seconds.
Explicit BETA self-contained publish: passed. Actual WPF/WebView2 acceptance on a
fresh 48-document synthetic Brain: passed. UI agreement/scope, bounded real hybrid
inference/order change, selective feedback capture, pause, engine restart with
checkpoint identity, offline rejection, safe exit and unchanged canonical document
hash all passed. Cold inference: 2720.17 ms / 217,235,456 sampled bytes; warm:
10.30 ms / 220,307,456 sampled bytes. Four local events were captured.

This is a runnable self-contained acceptance stage, not an installed/updater
release acceptance or owner-private session. Receipt:
`docs/neural/n3e-native-acceptance.json`. Stage and screenshots remain under
`D:/Personal Evil Search Engine/n3e-work/native-beta/` and are acceptance-only.

## 15. Regression evidence

| Run | Passed | Failures/errors/skips | Time |
|---|---:|---:|---:|
| Reproduced baseline | 464 | 0/0/0 | 34.43 s |
| Intermediate complete suite | 474 | 0/0/0 | 82.97 s |
| Final complete suite | 477 | 0/0/0 | 85.50 s |

Final suite includes actual resident inference, integrity fallback, actual local
training, rejection, real model replacement/rollback, scope/revision controls,
API consent and snapshot recovery. Two existing deprecation warnings remain
(Starlette/httpx and utcnow). Frontend production/TypeScript/static export passed,
including the new route (13 static pages). `git diff --check` passed.
Machine receipt: `docs/neural/n3e-verification.json`.

## 16. Offline, privacy, Brain and Drive compatibility

Native requests require the in-memory launch token and same origin. The host and
workers enforce offline operation; the native TEST-NET connection probe was
blocked before external connection. No private uploader, federated weight upload,
community ingestion service or new external destination was enabled.

A snapshot of the completed synthetic native Brain restored into a new inactive
directory with identical canonical document SHA-256
`8d635ac38237af9b6f1c8752d76619263291f03603934df7e23b27f815568236`.
The learning database, jobs and private weights were excluded by the unchanged
Drive snapshot allowlist. Receipt: `docs/neural/n3e-snapshot-verification.json`.
This proves local format/recovery compatibility; no live Google Drive account or
remote sync acceptance was exercised. Private sidecars intentionally do not roam.

One diagnostic mistakenly changed the default desktop configuration's Brain
pointer to a synthetic fixture. No owner document text was read or trained on.
The mistake was disclosed; the user explicitly chose restoration of the existing
default. Configuration alone was restored to
`C:/Users/frypa/AppData/Local/ManiacSoftwares/PESE/Brain`, without opening that Brain.
All subsequent diagnostics explicitly isolate LOCALAPPDATA or use the guarded
native acceptance profile. This incident is not concealed as a clean privacy run.

## 17. Failed experiments and remaining limits

Candidate B's longer training was worse. Journal adaptation changed weights but
did not improve the measured probe. Early native runs failed because staging
omitted version provenance and the harness raced startup navigation; both were
fixed. One concurrent-load native run fell back at inference; a six-document run
applied scores without changing order. The later declared 16-query/48-document
fixture passed on its first query, without changing model weights or score caps.
Earlier failed receipts/stages remain in the external experiment directory.

Independent human English/judge evaluation, broad natural queries, useful private
adaptation, quality-earned promotion, rich conflict resolution, battery scheduling,
installer/update acceptance and live Drive acceptance remain outstanding. Protected
local evaluation is training-independent review, not a fresh globally blind test
on every candidate. Grouped synthetic confidence intervals do not remove template
bias. Model/tokenizer context and vocabulary constrain generalization.

## 18. Explicit activation status

| Milestone | Result |
|---|---|
| Model architecture implemented | Yes |
| Relevance model actually trained | Yes, packaged candidate A |
| Feedback judge trained or rule-based | Both: trained advisory classifier + authoritative hard rules |
| Feedback judge independently evaluated | No; synthetic unseen-wording test only |
| Search ordering actually influenced | Yes, offline MAAE and native hybrid |
| Local training queue operational | Yes, synthetic consented sessions |
| Candidate updated through real training | Yes, synthetic journal/review fixture |
| Candidate evaluated independently | No human-independent acceptance; separate synthetic probe + insufficient protected pools |
| Experimental checkpoint promoted | Base activated after consent; local replacement/rollback only under labelled policy fixture |
| Native installed BETA verified | Staged native execution passed; installed owner/update acceptance remains incomplete |
| Public production acceptance achieved | No; official trust policy unchanged |

The owner pointer is restored, but experimental participation was not enabled on
the owner's Brain. A recoverable owner backup and affirmative in-app scope/consent
remain prerequisites before the first owner-private session.

## 19. Coherent commits and reproducibility

`62f7123` baseline/preregistered BETA contract; `4304f36` real English training;
`4ffc8c7` evidence admission and learned advisory judge; `6831d1a` runtime/local
lifecycle; `ae455b7` functional UI/native channel; `5fb318f` source/evaluation/privacy
corrections; `7829d30` scope, category, byte budgets and native/recovery hardening;
`3f7a57f` exact-byte artifact preservation across checkouts.
The final documentation commit preserves this report and measured receipts.

Entry points: `scripts/train_n3e.py`, `scripts/package_n3e_base.py`,
`research/train_feedback_judge.py`, `scripts/verify_n3.py`,
`scripts/create_n3e_fixture.py`, `scripts/stage_n3e_acceptance.py`,
`scripts/verify_n3e_snapshot.py`, and `PESE.exe --accept-neural-beta` with a marked
synthetic fixture and isolated output. Never run an unscoped desktop `connect`
diagnostic. Experiment artifacts are outside the checkout, in `n3e-work`.

## 20. Next learning milestone

Freeze a broader independently reviewed English/feedback evaluation set before
further tuning. Include temporal questions, partial queries, multilingual/noisy
notes, missing evidence and conflicting facts. Then complete installed/updater
acceptance and a verified recoverable owner backup. With affirmative UI consent,
collect a small explicitly scoped real-world queue, review disjoint training and
protected evaluation pools, and seek the first quality-earned local promotion.
Preserve the failed journal result and current base as the comparison point.

**NO EVIDENCE = NO ANSWER.**
