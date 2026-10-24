# PESE knowledge corpus completion report

Completed on 22 October 2026. This was a data-generation and observation task. No ranking, architecture, UI, MAAE, model or existing evaluation implementation was edited by the corpus task.

## Corpus

| Measure | Result |
|---|---:|
| Documents before | 34 |
| Documents added | 178 |
| Documents after | 212 |
| New words, approximately, including headings | 60,685 |
| Combined words, approximately | 65,890 |
| Native new-document JSON size | 598,896 bytes |
| Combined local document store | 685,249 bytes |
| Derived semantic-cache files, combined | 5,998,198 bytes |
| Indexed passages | 1,314 |

The preferred 150–180 range was used for the **new** collection. Preserving the 34 original records brings the installed total above that range. The architecture handled the combined collection successfully.

| Primary category of new documents | Documents |
|---|---:|
| History, empires and civilizations | 39 |
| Wars and political conflict | 21 |
| Countries and capital comparisons | 33 |
| Leaders and historical people | 20 |
| Gaming and technology | 42 |
| Science and general knowledge | 23 |
| **Total** | **178** |

All 32 explicitly requested countries are covered. The existing Japan article is preserved, with a separate new article titled *Japan: Islands, Institutions and Regional Geography*. Every requested conflict has a separate entry; the collection also covers all named console families, the requested major games, the main historical examples and the science topics. Comparison articles explain closely related entities rather than collapsing them into synonyms.

## Structural diversity

| Structure | Articles |
|---|---:|
| FAQs | 22 |
| Long-form prose, at least 700 words | 20 |
| Lists | 32 |
| Comparisons or explicit contrasts | 71 |
| Semantically embedded answers | 103 |
| Chronological/narrative treatments | 46 |

These labels overlap. There are eight dedicated comparison articles, with shorter contrasts in other articles. FAQs use the existing Markdown format and passage extractor. The source manuscripts and native JSON contain no generated query-pack labels.

Lengths range from 211 to 830 words, including headings: 78 short articles, 80 medium articles and 20 long articles. This supplies genuine length variation but does **not** reproduce the suggested percentage mix: there are more short articles and fewer long articles, and no sub-150-word focused entries. Articles were not padded to meet a quota. The deliberately buried query evidence includes offsets around words 489, 538, 574, 597, 639 and 708 in different long articles.

## Factual provenance

The summaries are original English prose. Forty source records document selected checks covering 62 articles. `sources.json` records the source URLs, access date and precise scope; `manifest.json` assigns `last_verified` only where a scoped check exists. Other articles explicitly have no exhaustive verification claim.

Freshness-sensitive snapshots include Charles III's identity and accession from the [Royal Family's official profile](https://www.royal.uk/the-king), Asif Ali Zardari's presidency from the [National Assembly's official list](https://www.na.gov.pk/en/president_list.php), and GTA VI's announced schedule from [Rockstar Games](https://www.rockstargames.com/VI). They are dated 22 October 2026. A planned game release is not described as a completed release.

Indonesia's capital discussion preserves the date of a [May 2026 Jakarta government report](https://www.beritajakarta.id/en/read/152669/pramono-jakarta-remains-the-capital-city-until-a-presidential-decree-is-issued). It does not pretend that this alone verifies the absence of a later decree. Other entries distinguish approximate ancient dates, uncertain interpretations, disputed sovereignty and modern versus historical names.

This is selected-source research, not an exhaustive independent audit of every historical or scientific statement. Current-officeholder facts were checked rather than filled from memory.

## Evaluation pack

| Measure | Queries |
|---|---:|
| Total | 246 |
| Lexical / exact factual | 149 |
| Semantic label, including natural-language, comparisons and buried answers | 56 |
| Typo / messy | 15 |
| Entity ambiguity | 6 |
| QA cases, including negatives | 240 |
| Expected abstentions | 20 |

The primary query types are 149 exact factual, 19 semantic, 15 natural-language, 15 messy, eight comparison, six ambiguity, six long questions, eight buried-answer cases and 20 abstentions. Label totals overlap; primary-type counts sum to 246. Positive primary targets cover 175 of the 178 new documents.

Each case has a query, type, primary and acceptable document references, reference answer phrase, answer-presence flag, intended behavior, notes and a date. Answerable cases include exact source offsets and surrounding evidence. All generated offsets were checked against the installed document text. The reference phrase is not always a complete explanation: multi-part comparisons, negation and causal answers require semantic review.

Abstentions include missing attributes of known entities—Ganymede's diameter, a regional console price, an annual sales total—and absent topics such as Ceres or Georgia's capital. Queries are plausible questions, not indexed articles. No labels, expected answers or query-specific exceptions were passed into the engine or used for training.

## Observed baseline

The observer sent only query strings through the existing lexical, semantic and hybrid pipelines. Gold remained outside the engine. All 246 cases were run in each mode; the real PESE-QA-0 reader was loaded for the hybrid run.

| Mode | Acceptable top-1 hit | Acceptable top-5 hit | MRR at 10 |
|---|---:|---:|---:|
| Lexical | 82.73% | 98.64% | 0.8967 |
| Semantic | 75.00% | 98.64% | 0.8550 |
| Hybrid | 82.73% | 99.09% | 0.8973 |

These retrieval measures use 220 answerable cases and the curated acceptable-document lists. Another defensible document may be missing from a list, so they are a baseline for inspection rather than a universal correctness score. Hybrid search retrieved an acceptable top-five result for 218 of the 220 cases.

On the 20 expected-abstention cases, the deterministic featured-answer path emitted an answer three times and the neural shadow reader emitted an answer 15 times. These outputs are recorded separately in `retrieval_report.json`. An emitted span requires review; this count is not a claim that every output has already received a full semantic error classification. The neural reader ran on 244 of 246 hybrid queries; an empty candidate set can prevent an invocation.

No ranking, evidence-gate or QA change was made to improve these results. Timing measurements were diagnostic and overlapped with test activity for part of the run; they are not presented as isolated performance benchmarks.

## Integration and validation

- All 212 native records load through `Document.from_dict` and the local `DocumentStore`; all are published.
- The real `PassageExtractor` and `InvertedIndex` index all records into 1,314 passages. The link graph builds with 212 nodes and all new internal links resolve.
- The real local `BAAI/bge-small-en-v1.5` provider builds 384-dimensional normalized vectors for all 212 documents and 1,314 passages. Disk reload, vector shape, finiteness and document-vector normalization checks pass. No mock provider was substituted.
- Exact original-record equality is checked against the snapshot. All 34 original documents, including intentional test and spam documents, remain intact. The snapshot also preserves the original file's bytes and SHA256.
- Duplicate-title and normalized exact-content checks find zero duplicates. Five-word shingle checks find zero near-duplicate candidates at Jaccard ≥ 0.35 or containment ≥ 0.65. Related subject matter is intentional; nearest pairs are retained in the validation report.
- All 178 new records have nonempty titles, valid IDs/slugs, content, headings and compatible native fields. No new replacement-character corruption was found.
- No production algorithm, UI, model checkpoint, training corpus, MAAE configuration or existing evaluation implementation was edited by this task. The existing evidence-gate file and original neural files match their initial hashes.
- The local API health endpoint was not reachable from the task. Durable data and vector caches are ready for the next service start. An already-running API should be restarted after file-based installation because it may cache an earlier store.

The importer is repeatable and refuses to replace original records or unknown colliding IDs. It also checks that the store has not changed during validation before performing its atomic write. The original seeder was not changed; intentionally resetting with that seeder requires re-running this importer.

## Tests and concurrent work

The final full suite reports **94 passed, four failed, zero errors**, plus one existing `datetime.utcnow()` deprecation warning. Temporary-directory permission errors in the initial attempt were resolved by placing test temporary files inside the workspace; no tests were modified.

The remaining failures are in `engine/tests/test_performance_runtime.py`:

- `test_ww2_entry_date_arbitration`: a competing WWII document ranks above the original Japan article.
- `test_multidate_historical_arbitration`: the focused Meiji article competes with the original Japan article.
- `test_heading_aware_passage_selection`: a Meiji query selects the focused article rather than the asserted Japan slug.
- `test_skip_qa_bypasses_neural_passes`: the selected WWII result does not produce the expected featured answer `1941`.

These are preserved observations. The new corpus was not weakened and the ranking was not tuned to force the old expectations. The typo-recovery assertion passed in the final run.

This shared workspace changed concurrently. Eight pre-existing files differ from the initial hash snapshot, although none was edited by the corpus task:

```text
engine/api/main.py
engine/passages/answer_extractor.py
engine/query_analysis/spelling.py
engine/ranking/scorer.py
engine/tests/test_evidence_gate.py
web/src/components/SearchTimingAudit.tsx
web/src/lib/api.ts
web/src/app/search/page.tsx
```

Five additional source files appeared through concurrent work:

```text
engine/evaluation/answer_relevance_runner.py
engine/evaluation/performance_runner.py
engine/passages/answer_relevance.py
engine/tests/test_performance_runtime.py
web/src/components/AnswerTruthfulnessAudit.tsx
```

In particular, the failing performance-test module was added concurrently and was absent from the initial file inventory. Those files were preserved. The benchmark records current source hashes and found no changes to its monitored files during the run. This report therefore confirms the scope of the **corpus task**, not that all source code in the shared workspace remained unchanged.

## Files and Git

There was no Git repository in the supplied workspace. No commit was created and no commit SHA is available.

Created by this task:

```text
scripts/build_knowledge_corpus.py
scripts/build_knowledge_queries.py
scripts/evaluate_knowledge_corpus.py
docs/knowledge_corpus_report.md

engine/data/knowledge_corpus/README.md
engine/data/knowledge_corpus/baseline.json
engine/data/knowledge_corpus/existing_documents.snapshot.json
engine/data/knowledge_corpus/history.md
engine/data/knowledge_corpus/conflicts.md
engine/data/knowledge_corpus/countries.md
engine/data/knowledge_corpus/people.md
engine/data/knowledge_corpus/consoles.md
engine/data/knowledge_corpus/games.md
engine/data/knowledge_corpus/science.md
engine/data/knowledge_corpus/comparisons.md
engine/data/knowledge_corpus/longform.md
engine/data/knowledge_corpus/history_details.md
engine/data/knowledge_corpus/country_details.md
engine/data/knowledge_corpus/game_details.md
engine/data/knowledge_corpus/comparison_notes.md
engine/data/knowledge_corpus/documents.json
engine/data/knowledge_corpus/manifest.json
engine/data/knowledge_corpus/sources.json
engine/data/knowledge_corpus/query_cases.txt
engine/data/knowledge_corpus/queries.json
engine/data/knowledge_corpus/validation_report.json
engine/data/knowledge_corpus/retrieval_report.json
engine/data/knowledge_corpus/tests.log
engine/data/knowledge_corpus/tests.xml
```

Updated by this task:

```text
engine/data/firestore_documents.json
engine/data/semantic_index/cache_store.npz
engine/data/semantic_index/doc_vectors.npy
engine/data/semantic_index/passage_vectors.npy
engine/data/semantic_index/doc_meta.json
engine/data/semantic_index/passage_meta.json
engine/data/semantic_index/index_meta.json
```

The store update contains only the appended corpus records and JSON serialization. The six semantic-index files are derived data. Runtime bytecode, pytest caches and temporary test directories are not source deliverables.
