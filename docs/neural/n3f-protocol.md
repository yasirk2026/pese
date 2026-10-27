# FIRST CONTACT: frozen local BETA protocol

Historical protocol for the initial small pilot. The owner's subsequent normal
Windows update instruction supersedes the distribution identity and three-document
pilot limit below. See `n3f-windows-update.md`. Evidence independence, source review,
admission and promotion requirements continue to apply to collections of any size.

Starting source: `6c8caef0e22c4f5786eaba8853c41edee7853b68`.
The existing 111,426-parameter English BETA base, tokenizer, score bounds, MAAE
admission and answer gates remain fixed. No new base training or model growth.

## Evidence and independence

The owner supplies natural questions. A named human reviews the intended meaning,
source identity, date/currentness, every relevance grade (0 unrelated/wrong,
1 topical/incomplete/conflicted, 2 useful direct evidence), expected answer or
explicit abstention, and rationale. Unknown/unjudged never means negative.
Neural Genesis predictions, votes, journal generation and model confidence cannot
provide truth. Conflicts and missing evidence must be recorded, not guessed away.

`research/first_contact_english.py` contains fresh fictional proposals in twelve
families, with paraphrases, entity confusers, negation, dates, conflict and missing
evidence. Its grades are assistant-authored proposals. Runs using `--diagnostic`
are OPEN engineering diagnostics, never independent human evidence. They cannot
be relabelled as a final protected set after seeing results.

A separate protected packet has role `protected_evaluation_never_train`, complete
human grades, `answer_reviewed: true` on every query, and a named human review:

```json
{"approved":true,"reviewer":"<human name>","reviewed_at":"<ISO time>",
 "basis":"human_checked_source_evidence_and_all_labels"}
```

This attestation must come from actual human review. Do not populate it merely to
make the runner accept a packet. Owner questions and private review materials
remain outside the checkout. No private Brain is opened by the evaluator. A human
may supply non-private source excerpts to a separate packet; access to private
documents instead requires the separately approved, scoped in-app owner session.

All paraphrases of a question and documents from a source family share one role.
Train, validation and protected evaluation must have disjoint source families,
query families and passages, including candidate ancestry. Previously exposed
N3-E data is regression data. The runner refuses exact overlap with those data.
Human reviewers must also check semantic/family overlap: exact hash checks alone
cannot prove that independently worded questions are independent.

Freeze the full packet and model hashes before results. Run MAAE and MAAE + the
unchanged base on the same full corpus with real local BGE hybrid retrieval,
hard evidence gates and isolated CPU inference. Counterbalance three uncached
paired repetitions. Preserve all per-query orders, scores/adjustments in traces,
answers, abstentions, failures, regressions and latency, including cold inference.
Report NDCG@10 with grouped uncertainty, MRR/recall, category regressions, membership
violations and p50/p95 warm latency. Literal expected-answer checks are proxies;
blind human review of outputs is required for answer correctness claims.

Never tune against a protected final result. If a result informs a model or ranker
change, mark that set exposed regression and obtain a fresh human-reviewed set.
Insufficient questions, missing labels or no observed improvement means no claim.

## Installed channel and owner decision

Owner BETA uses package `ManiacSoftwares.PESE.OwnerBeta`, update channel
`win-owner-beta`, a separate Windows profile `ManiacSoftwares/PESE Owner BETA`,
and a separate single-instance identity. Stable PESE retains its existing package,
profile, paths and updater channel. The BETA cannot contact the stable GitHub feed;
reviewed local packages and explicit application are required. No package is
published automatically. Opening BETA does not accept its per-Brain agreement.
Native create/connect passes the separate profile's exact pointer path to Python;
the legacy stable pointer is preserved. Close a serving stable instance before
opening the same Brain in BETA; the existing writer lock prevents two writers.

Before private activation: verify G1 backup/inactive restore, installed identity,
native inference/fallback/offline/pause/exit and rollback, then the owner explicitly
accepts the existing hashed agreement and identifies a small document-ID scope.
Never automate agreement acceptance on the owner Brain. Do not guess scope from
document contents or enable journals. Keep the stable installation for rollback.

## First owner pilot

Start with at most 3 explicitly selected documents, journals off, 7-day retention,
and manual actions. Capture real query/result receipts and explicit reactions.
Unscoped targets are not retained, including metadata-only observations.
Have the owner assign trusted grades and rationale to exact source revisions;
do not convert a like/dislike directly to a relevance label. Assign disjoint
train/validation/protected roles before fitting. Pause on ambiguity or conflicts.
Keep real feedback counts separate from synthetic acceptance events and owner
questions that have not yet been searched.

Training is manual and blocked until the existing admission gate has at least
12 reviewed pairs, both positive and negative labels and three source families in
disjoint train/validation pools. Protected pools must remain separate. Do not
weaken these gates to accommodate a small first session. A three-document pilot
may therefore collect observations without admitting a training job.

Promotion retains existing preregistered gates: at least 12 fully reviewed heldout
query pools and three disjoint heldout families independent of ancestry; NDCG gain
>= .01 versus current, no worse than -.02 versus MAAE/base, category regression
<= .05, zero new wrong answers or gate violations, healthy isolated inference.
The FIRST CONTACT operational latency goal is warm neural p95 <= 150 ms for the
bounded six-candidate model call; report end-to-end latency separately. These are
local BETA gates, not broad English certification. Retain rejected models and
failed receipts. Roll back explicitly or exit to deterministic MAAE.

No automatic external sharing. No unreviewed journal text becomes truth.
No automated search, training or consent on the real owner Brain.

**NO EVIDENCE = NO ANSWER.**
