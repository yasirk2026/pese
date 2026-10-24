# PESE Phase 2F exposed regression replay

This is an exposed regression replay after a patch informed by the revealed holdout. It is not blind and provides no new independent acceptance evidence. The original blind outputs, labels, score, and report remain unchanged.

`syn-q-030` now abstains: the validator rejects the clock-stopping sentence with `PREDICATE_MISMATCH`. The prior wrong promotion is removed, but the question is still answerable and the replay does not identify its repairer. It remains incorrect for answer/abstention accuracy.

| Metric | Original blind | Exposed replay |
|---|---:|---:|
| Doc@1 | 43/45 (95.56%) | 43/45 (95.56%) |
| Doc@3 | 45/45 (100%) | 45/45 (100%) |
| Passage@1 | 41/45 (91.11%) | 41/45 (91.11%) |
| Passage@3 | 45/45 (100%) | 45/45 (100%) |
| Answerable recall | 5/45 (11.11%) | 5/45 (11.11%) |
| Overall answer/abstention accuracy | 8/48 (16.67%) | 8/48 (16.67%) |
| Unanswerable abstention accuracy | 3/3 | 3/3 |
| Wrong promotions | 1 | 0 |
| Promoted answer precision | 5/6 (83.33%) | 5/5 (100%) |
| False abstentions on answerable questions | 39/45 | 40/45 |

Recall changed by 0 correct answers and 0 percentage points. All document ranks, captured passages, and candidate spans match the blind run. The sole final-answer change is `syn-q-030`. Raw and adjudicated scores agree; no labels or scoring rules were revised. Per-category results and case details are retained in the regression score JSON.

The source hash declared by the release manifest and replay is `51d186b0c06c9077ed34239f3d89be6eb045812215a54fb9408b306fe04368b5`. The manifest file itself has SHA256 `93a17e913c5f972f0385f4d6694f76190acd8ad8ddab75dd211c428ed5e4274c`; these are different hash subjects.

Frozen replay outputs: `b1e0a3ba189a34dd9b4c3f737be9ec287fa069f7716a014b02f2ae7efbaaa297`. Unchanged labels: `a2ab11e3c4eacf524b278179011fe07f3dc2b475b59ecb98c78a6fa4b28ad6cb`. Unchanged input: `5698f09c8b596d0e383b7b8645d238d4ee2699c28b411a3109b95b546951b89c`.

This dataset is now regression data, never blind again.
