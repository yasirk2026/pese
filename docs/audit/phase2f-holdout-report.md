# PESE Phase 2F independent holdout report

The frozen run retrieved most supporting documents, but rarely returned correct answers. Correct final answers were produced for 5/45 (11.11%) of answerable questions. One irrelevant sentence was promoted as an answer. All three unanswerable questions received abstentions.

The dataset was authored independently without inspecting implementation code, previous benchmarks, or private user data. Original questions and labels were sealed before the single production run. No inputs or labels were revised and no engine rerun was performed during scoring.

| Stage | Result |
|---|---|
| Doc@1 | 43/45 (95.56%) |
| Doc@3 | 45/45 (100.00%) |
| Passage@1 | 41/45 (91.11%) |
| Passage@3 | 45/45 (100.00%) |
| Answerable recall | 5/45 (11.11%) |
| Overall answer/abstention accuracy | 8/48 (16.67%) |
| Unanswerable abstention accuracy | 3/3 (100.00%) |
| Promoted answer precision | 5/6 (83.33%) |
| Wrong promotions / all questions | 1/48 (2.08%) |
| Correct candidate spans, diagnostic only | 25/45 (55.56%) |

Passage metrics use the first three flattened passages exactly as captured, without reranking or taking one passage from each document. Retrieval and answerable recall denominators exclude the three unanswerable questions. Raw and adjudicated scores are identical.

There were 39 false abstentions among 45 answerable questions. The run suppressed 20 correct candidate spans. Candidate correctness is diagnostic only; an abstained candidate does not count as a correct final answer.

| Category | Doc@1 | Doc@3 | Passage@1 | Passage@3 | Correct answer/abstention |
|---|---|---|---|---|---|
| exact lexical | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 0/3 (0.00%) |
| semantic paraphrase | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 0/3 (0.00%) |
| entity attribute | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 1/3 (33.33%) |
| multiple dates | 2/3 (66.67%) | 3/3 (100.00%) | 2/3 (66.67%) | 3/3 (100.00%) | 0/3 (0.00%) |
| multiple entities | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 0/3 (0.00%) |
| negation | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 0/3 (0.00%) |
| FAQ | 3/3 (100.00%) | 3/3 (100.00%) | 1/3 (33.33%) | 3/3 (100.00%) | 1/3 (33.33%) |
| procedural | 2/3 (66.67%) | 3/3 (100.00%) | 2/3 (66.67%) | 3/3 (100.00%) | 0/3 (0.00%) |
| definition | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 1/3 (33.33%) |
| cross-sentence | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 0/3 (0.00%) |
| simple coreference | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 0/3 (0.00%) |
| typo | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 1/3 (33.33%) |
| unanswerable | N/A | N/A | N/A | N/A | 3/3 (100.00%) |
| spam competition | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 1/3 (33.33%) |
| short exact answer | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 0/3 (0.00%) |
| semantic distractor | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 0/3 (0.00%) |

The single wrong promotion was `syn-q-030`. Asked who repaired Nimber station’s platform clock, the engine returned “Nimber station's platform clock stopped during the winter storm.” The original evidence identifies Tessa Wren. The returned sentence is grounded but does not answer the requested relation, so it is scored wrong.

Document rank 1 failed on `syn-q-011` (cargo launch outranked the requested ferry) and `syn-q-022` (speaker return instructions outranked projector cooling instructions). Both correct documents and supporting passages appeared within the captured top three. The FAQ support for `syn-q-019` and `syn-q-020` appeared at flattened passage ranks 2 and 3 respectively.

Failure details for every incorrect case, validator reasons, candidate spans, expected facts, supporting evidence, raw flags, and adjudication notes are retained in `phase2f-holdout-score.json`. The original labels are revealed byte-for-byte in `phase2f-holdout-labels.json`.

The 76-document synthetic collection and 48 questions are a small sample. Each category has only three cases, and the unanswerable result has only three examples. QA was disabled, so these results describe the recorded deterministic/FAQ configuration.

Frozen hashes:

- Input: `5698f09c8b596d0e383b7b8645d238d4ee2699c28b411a3109b95b546951b89c`
- Original/revealed labels: `a2ab11e3c4eacf524b278179011fe07f3dc2b475b59ecb98c78a6fa4b28ad6cb`
- Outputs: `8103065bf5ce00df514e186b15c3660e10bee9fb568ae3da9e3297f5e8732699`
- Source: `0f1aca13a0e257ac6c387260c81b758603468fd5315277836426380def98b744`

**This dataset is now regression data, never blind again.**
