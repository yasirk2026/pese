# N3 baseline — 27 October 2026

Inspected checkout: `5b210ae`, branch `codex/g1-recovery-hardening`, initially clean.
Local `main` and `origin/main` resolve to the same commit; no remote refresh or
release publication was performed. Host targets .NET 10 Windows/WPF/WebView2;
FastAPI serves the static Next 16 frontend and local Python search engine.

Actual flow: query analysis → lexical BM25F and optional local BGE → fusion →
minimum evidence gate → composite deterministic score → bounded exact-query
Search Sync preference (+2/-4, clipped -6/+3) → sort → deterministic answer
extraction and relevance validation → optional QA and relation shadows.
Shadows cannot authorize answers or affect scores. Rel-0 is a 892,290 parameter
binary answer-support classifier, not a document relevance model.

Storage: canonical documents/history/profile/feedback are protected by the Brain
writer barrier. Snapshot v2 transports logical feedback schema v1, including raw
queries and shadow evidence summaries. Manual Drive backup is an explicit private
Brain transfer, **not** community contribution. New research storage must remain
outside its fixed payload allowlist. Recovery targets a separate inactive Brain.

Read N3-A, N3-B, neural genesis/DATA-0/N2, ranking, answer relevance, architecture,
Alpha.5/6 release and preservation documents. No separate N3-B.1 audit document
exists in this checkout; its findings in the assignment were independently checked.

## Before implementation

All executed Python imports bound `PESE_BRAIN_PATH` and `LOCALAPPDATA` to new
`.tmp/n3-baseline` fixtures. No real Brain was opened. Existing embedded Python
3.12.10 / torch 2.14.1 CPU / pytest 9.1.1 were reused, without downloads. The old
venv points to an unavailable account interpreter. Default OS temporary-directory
cleanup failed once; rerun with workspace TEMP/TMP completed successfully.

`engine.evaluation.independent_runner.run`: 64 exposed development cases;
document @1/@3 0.9531, passage @1 0.92/@3 0.94, direct-answer correctness 0.86,
correct abstention 1.0, 47 promotions including **1 wrong promotion**. Replay p50
42.56 ms / p95 63.16 ms while another test process ran; not a hardware budget.
These are different cases from the assignment's historical 45/48-case audit.

Replayed frozen Rel-0: test 102/120 correct (85%); exposed prospective 20/48
(41.67%), with 22 false positives and 6 false negatives. Loading 64.98 ms.
Weights/tokenizer remain frozen. Existing threshold sweep inspected the exposed
test: it cannot serve as untouched calibration or justify production activation.

Synthetic reproducer demonstrated wrong-context join, DISLIKE counted as both
agreement and disagreement, and disabled checkpoint trace calling the loader.
Code inspection also confirmed cached context reuse, target-type-blind summary
grouping, missing revision provenance, unverified feedback contexts, and absent
persisted model_versions. Initial selected pytest run stalled after nine unit
tests at TestClient API testing and was interrupted; it is not a pass. Separate
non-API baseline and subsequent verification are recorded in the final report.

Raw receipts are local `.tmp/n3-baseline/{defects,replay,rel0}.json`; synthetic
inputs only. Acceptance requires a new independently reviewed relevance dataset.
