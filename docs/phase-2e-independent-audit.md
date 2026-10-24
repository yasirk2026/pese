# Phase 2E — independent engine audit

Date: 2026-10-22. Scope: the supplied working directory and the running local application. This directory has **no `.git` repository**, so prior commits, assertion changes, and provenance of tuning constants cannot be reconstructed. No production Firebase writes, external LLMs, model enlargement, chat, or Phase 2F work were performed.

**Disposition: substantial hardening delivered; product acceptance remains open.** The payment failure is repaired and the live WW2-entry query returns 1941. This is not a claim that PESE now understands arbitrary questions. Attribute retrieval, paraphrases, cross-sentence evidence, and the experimental neural reader remain weak. The final full suite has **107 passes and 5 failures**; those failures were preserved, not hidden by changed expected answers.

## A. Actual current architecture

The implementation is a local, in-memory retrieval pipeline over a persistent document store. It is not a learned end-to-end search engine.

```text
Browser /search (Next.js client component)
  SearchAutocomplete -> router -> SearchPage effect
    GET FastAPI /api/search [normal: skip neural shadow; debug: run shadow]
      RankingEngine.search
        generation-scoped ranking cache [non-neural requests only]
        _search_uncached
          QueryAnalyzer.analyze_query
            quoted phrases / normalization / tokenization
            rule-based interrogative intent
            corpus Damerau-Levenshtein spelling + inflection protection
          QueryRepresentation(content_terms=analyzed content terms)
          CandidateRetriever -> fielded BM25
          SemanticRetriever -> one query embedding
            passage vectors and document-summary vectors queried separately
            cosine dot products -> 70/30 aggregation -> drift penalty
          HybridCandidateFuser -> RRF candidate ordering / rescue labels
          MinimumEvidenceGate -> candidate eligibility
          RankingEngine document scoring
            BM25 + title/headings/phrases/keywords + passage + dense affinity
            coverage multiplier + authority/freshness/quality -> spam multiplier
          PassageScorer -> bounded term counts + sentence coherence
          FeaturedAnswerExtractor [request-local state]
            FAQ / temporal / declarative / causal / procedural candidates
            EACH -> AnswerRelevanceGate
            one arbitration -> validated winner or abstention
          optional PESE-QA shadow [never authoritative for Featured Answer]
      SearchResponse -> is_featured / featured_answer -> React render
    after primary response:
      /api/questions -> main ranking reuse -> <=10 candidate-question searches
        authored titles/headings/FAQs + corpus-derived families
        same validated answer pipeline, source ownership, topical filtering
      /api/related -> main ranking reuse -> primary-source graph/heading/family links
```

`/api/suggest` uses documents, FAQs, history, sessions, spelling, and query families. It does not call neural QA. Click/search events affect discovery suggestions, not the main document ranking formula. Collection is not a learned reranker.

Repository ownership:

| Area | Actual responsibility |
|---|---|
| `engine/api` | FastAPI schemas, lifetime, CRUD, index publication, discovery APIs, neural lab |
| `engine/indexing` | canonical Document, JSON/Firestore store, postings, passage registry |
| `engine/nlp`, `query_analysis` | normalization, tokenizer, Porter rules, shared evidence matching, spelling, intent |
| `engine/retrieval`, `ranking` | fielded lexical candidates, evidence gate, scoring, traces, orchestration/cache |
| `engine/passages` | AST/Markdown/FAQ segmentation, passage scores, clean snippets, extraction/validation |
| `engine/semantic` | local embedding provider, persisted vectors/cache, drift and RRF |
| `engine/link_graph`, `quality` | graph/PageRank, quality features and spam rules |
| `engine/discovery` | autocomplete, history/session stores, PAA and related searches |
| `engine/neural` | custom PyTorch models, tokenizers, tiny synthetic training curricula, checkpoints, inference |
| `engine/evaluation`, `tests` | exposed development datasets, benchmark/regression runners, component/integration tests |
| `engine/data` | private mutable corpus/history, derived index caches and prior reports; also public seed code |
| `web` | CMS, document reader, SERP, discovery, debug panels, Neural Lab |

There is no separate independent search API in Next.js: the client calls FastAPI directly using `NEXT_PUBLIC_ENGINE_API_URL` or localhost:8000. Next navigation/hydration and React presentation therefore add costs outside `engine.search`.

## B. Claimed versus actual behavior

| Prior claim / requested check | Independently observed |
|---|---|
| Answer gate prevents unrelated payment answers | Baseline live API AND browser promoted the unrelated employment FAQ; gate verdict was null |
| WW2 query reliably returns 1941 | Baseline changed `enter` to `center`, ranked a war-ending article, and abstained. Repaired path ranks Japan and answers **1941** |
| Meiji query must rank Japan #1 | Current 212-document corpus contains a dedicated Meiji Restoration article, which ranks first. That is relevant evidence, not Japanese-language contamination |
| `japna` correction is fixed | Correction is general edit-distance recovery. Current best result is a dedicated Japan geography article; the original Japan page is also retrieved |
| Neural understanding selects the SERP answer | False: QA was and remains shadow-only. Surrounding deterministic extraction owns the answer |
| Perfect relevance benchmark establishes UI truthfulness | False: it evaluates hand-supplied candidates through a helper, not FAQ extraction/arbitration/API/rendering |
| Old tests were sealed blind acceptance | Their questions, answers, code and tuning examples are accessible in the repository. They are regressions |
| Roughly 42 ms describes search experience | It does not describe current uncached 212-document searches, discovery contention, browser presentation or startup |
| 100% neural generalization / zero hallucinations | Unsupported by independent data. Nine of fifteen QA benchmark items share training contexts |

Historical reports are retained as historical claims. This report supersedes their correctness/performance conclusions. No commit history exists here to prove when individual old expectations were changed.

## C. Duct tape and overfitting findings

1. **Literal Japan exceptions** existed in deterministic temporal weighting and neural span reranking: Japan received a different weight from other query terms. Removed from both paths.
2. **Duplicate acronym/term-matching implementations** existed in the reader and extractor. Consolidated into `nlp/evidence.py`. Removed false equivalences such as treating the Pacific War as interchangeable with all of WW2, and overly broad country aliases.
3. **Unconditional FAQ authority:** any winning FAQ returned its answer without validation against the current question. Removed.
4. **Fail-open validation:** `except Exception: return answer_text, justification`. Removed; exceptions now abstain with a visible structured failure.
5. **Passage-wide yes/no rescue:** another sentence could supply a payment proposition and boost unrelated candidate scores. Validation now uses candidate-local evidence; entity/property constraints cannot be outweighed by a weighted total.
6. **Missing temporal objects:** WHEN/WHO/WHERE were exempted from the property check, so the same predicate with the wrong object could pass. Mandatory requested-term checks now cover those contracts.
7. **Canned discovery:** PAA content tests generated fixed PESE/bicycle/hydration/Hiragana questions, including a specific bicycle date. Removed. Families were hardcoded around the seed corpus. Production families now derive from published content.
8. **Slug-specific PAA exceptions** tried to distinguish personal bicycle sources from a generic breakdown page. Replaced with consistent source ownership.
9. **Function-word question affinity:** `does` could make unrelated PAA questions look relevant. Candidate/relatedness filtering now uses shared stopwords.
10. **Short = spam:** every body below 30 tokens received a 35% penalty, irrespective of factual utility. Removed; repetition/stuffing defenses remain.
11. **Subword answers masquerading as intelligence:** neural output included fragments such as `15 August 1` and mid-word spans. Whole-word constrained context decoding now excludes illegal boundaries before top-K selection and probability normalization.
12. **A question masquerading as its answer:** a passage repeating the question could pass the gate. Question candidates now reject.
13. **Noun mentions masquerading as asserted actions:** a new browser test promoted a roadmap about CPU-aware “execution” for “what does a CPU execute.” A generalized action-versus-nominal-mention check now rejects that candidate.

The exhaustive production-source occurrence listing is in [source-inventory.json](audit/source-inventory.json). Product names/checkpoint filenames, comments, general acronym dictionaries and metadata dates are distinguished from the removed ranking branches above. Presence of `payment` in a synonym lexicon is not itself a literal query override; it is nevertheless a narrow hand-authored semantic approximation, not neural understanding.

## D. Regression inventory

| Severity | Finding | Disposition |
|---|---|---|
| Critical | unrelated FAQ promoted as payment answer | repaired; actual browser/API verified |
| Critical | validator failure promotes unvalidated answer | repaired; injected-failure test |
| High | valid verb corrected to unrelated word before retrieval | repaired with corpus-stem protection |
| High | sentence/topic overlap mistaken for a proposition | strengthened; still a heuristic gate, not general logical entailment |
| High | published -> draft leaves old documents indexed | backend repaired and isolated integration tested |
| High | Save Draft button preserves published status | frontend repaired; actual CMS retest produced zero search results |
| High | personal bicycle specification retrieval | still poor: content-quality commentary can outrank the actual bicycle page |
| High | QA train/benchmark leakage and poor calibration | measured; QA retained as explicit diagnostic shadow |
| Medium | doc embedding cache hashes 500 characters but embeds 600 | repaired: hash exact generated summary + provider identity |
| Medium | mutable answer audit state shared by main search/PAA | request-local extraction state |
| Medium | mutable singleton Porter stemmer and unprotected “thread-safe” QA cache | independent stemmer computations + bounded memoization; real QA cache locking/deep copies |
| Medium | slow secondary discovery competes with primary request | primary-first browser dispatch + bounded ranking reuse; tail latency remains visible |
| Medium | stale async frontend/autocomplete responses | query-generation/active-request guards |
| Medium | private corpus/history not ignored; unsafe pickle loading | ignore rules strengthened; safe checkpoint loading and NumPy pickle disabled |
| Medium | cross-paragraph answers, payment paraphrases, rare typos | remain known weaknesses |

## E. Root causes and real-query traces

Full function-call order, lexical/semantic candidates, RRF records, passages, temporal candidate verdicts and neural shadow output are saved privately in `.tmp/phase2e-query-traces.json`. Baseline HTTP responses are in `.tmp/phase2e-baseline-http.json`. These contain local corpus text and are intentionally excluded from public report artifacts.

### Flexible-payment query

Original and normalized: `does healing lounge offer flexible payments`. Corrected: unchanged. Content terms: healing, lounge, offer, flexible, payments; Porter stems include `heal`, `loung`, `offer`, `flexibl`, `payment`. Intent classifier routes it to WHAT; the gate's more specific contract is DOES_IS_CAN. Entity = healing/lounge; predicate = offer; properties = flexible/payments.

Baseline retrieval correctly found the Healing Lounge document. Lexical passage scoring selected its FAQ “Who works for The Healing Lounge?” The FAQ contains strong entity overlap and receives ordinary heading/passage signals; neither document nor passage retrieval establishes payment evidence. `FeaturedAnswerExtractor.extract_answer` took `structural_metadata['faq_answer']` and **returned before `_apply_relevance_gate`**. The answer was the Yasir employment sentence. `last_relevance_result` remained null. FastAPI serialized `featured_answer` and `is_featured=True`; React rendered those fields directly. The browser displayed exactly what the backend returned.

The fallback exception bypass existed too, but there is no evidence an exception caused THIS incident. The direct FAQ bypass is sufficient and was reproduced. The new gate rejects the missing offer/payment relationship, while the topical ranked document can remain visible. QA is not allowed to reverse this rejection. PAA and Related Searches are separate requests and cannot replace the main answer.

### Japan / WW2 entry

Baseline spelling changed **enter -> center** despite `entering` being present. That corrupted lexical retrieval and query semantics. Final correction preserves `enter`; entities = japan, predicate = enter, property = ww2. The shared lexical acronym table recognizes World War II; Porter matching recognizes entering. The winning paragraph contains 1889, 1895, 1910, 1937, 1941, 1945 and 1952.

Per-sentence query coverage and relation coverage favor the sentence containing Japan, entering and World War II. Date candidates within that sentence receive `2*specificity + 3*sum(1/(1+character_distance/8))` relative to relation terms. Thus 1941 binds to entering/World War II, rather than annexing Korea in 1910 or invading China in 1937. Each candidate still requires the final evidence gate. The unconditioned “take any date from the passage” fallback is removed. The actual browser returned **1941** from Japan.

This is deterministic evidence matching and arbitration. The neural shadow is separately logged and never votes in Featured Answer selection. It is incorrect to describe harmonic proximity or the acronym dictionary as learned temporal reasoning.

### Remaining historical answers

“When did Yasir dream PESE” now abstains instead of promoting the implementation date. The source requires heading/pronoun/paraphrase resolution across sentences. The neural shadow can still select October 2026. Islamic Golden Age ending needs centuries and a long source passage; the deterministic temporal patterns and passage selection do not reliably handle it. Bicycle invention similarly remains an abstention. These are missed answers, not successful extraction claims.

## F. Changes made, by file

| File(s) | Change |
|---|---|
| `passages/answer_extractor.py` | one validated candidate/arbitration path; FAQ validation; fail-closed exceptions; no unconditioned temporal fallback; removed Japan-specific weighting |
| `passages/answer_relevance.py` | candidate-local evidence, mandatory entity/object support, corrected token stream, negation locality, question/nominal-topic rejection |
| `nlp/evidence.py` | shared bounded acronym/stem/sentence evidence utilities, abbreviation-safe sentence boundaries |
| `nlp/stemmer.py`, `tokenizer.py` | thread-safe memoized stemming; explicit content-only ranking representation |
| `query_analysis/spelling.py`, `intent.py` | preserve known inflections; bounded spelling memoization; remove PESE-specific intent phrases |
| `passages/scorer.py`, `extractor.py` | bounded per-term passage frequency, sentence coherence, relation coverage, Markdown-clean search passages/FAQs |
| `ranking/scorer.py` | request-local answer audit; ordinary search skips neural shadow; observable failures; immutable-generation ranking reuse; real skip_qa behavior |
| `semantic/provider.py`, `index.py`, `retriever.py` | bounded query embeddings; two ONNX threads; stable mock hashing; provider-aware exact input hashes; cache pruning; no NumPy pickle; snapshot drift metadata |
| `indexing/store.py` | explicit local paths cannot silently select Firestore; configured Firestore failures fail visibly; external file mtime invalidation; locked writes/deletes; malformed stores do not become empty corpora |
| `api/main.py` | all save statuses reindex; replacement vector snapshots; index generation/boot IDs; structured search logs; preserve resident reader across CMS reloads |
| `neural/inference/qa_reader.py` | shared matching, removed Japan exception, offset-safe contexts, whole-word decoding, actual cache locking/deep copies |
| `neural/training/checkpoint.py` | weights-only loading with a narrowly allowed TorchVersion metadata class |
| `quality/spam_detector.py` | remove unconditional thin-content penalty |
| `discovery/questions.py`, `families.py`, `related_searches.py` | remove canned examples, derive families from corpus, preserve FAQ metadata, enforce source ownership, remove function-word affinity, use primary-source graph neighborhood |
| `web/src/app/search/page.tsx` | primary-first discovery, no stale query responses, normal/debug QA separation, answer/index diagnostics, browser timing attributes |
| `web/src/components/SearchAutocomplete.tsx` | ignore stale suggestion generations and clear stale selections |
| `web/src/components/DocumentEditorForm.tsx` | Save Draft explicitly saves draft |
| `web/src/lib/api.ts` | response IDs/index/answer-audit types |
| `.gitignore` | broader secrets, private store/history, models, derived data and scratch protection |
| `evaluation/*audit*.py`, `independent_*.py`, `http_probe.py`, `query_trace.py`, `prospective_holdout.py` | reproducible stage, source, memory, HTTP, cold-start, trace and one-run prospective evaluation tooling |
| `tests/test_independent_invariants.py`, `test_index_freshness.py`, `conftest.py` | real pipeline failure/grounding/cache/CMS regressions; bounded CPU test runtime |
| `tests/test_quality.py` | replace the old short=spam policy assertion with short-content neutrality; stuffing tests retained |
| `evaluation/qa_reader_runner.py`, `tests/test_qa_reader.py` | exposed “blind” cases honestly renamed historical regressions; substantive answer assertions preserved |

## G. Deleted / consolidated architecture

Removed duplicate acronym/matching implementations, Japan-specific weights, corpus-specific PAA fact generation, slug-specific PAA rescue, unconditional FAQ promotion, unconditional temporal fallback and fail-open answer validation. The extractor now collects candidates, validates them, then arbitrates. It does not let a second producer restore a rejected answer.

QA remains a separately labeled diagnostic; it is not another authoritative answer route. Normal SERP requests do not pay for its inference. This preserves experiment access without pretending the model improves current main-search answers.

## H–K. Search, passage, truthfulness and abstention metrics

Dataset: **64 inspected synthetic development/regression cases**, 28 documents including five authority-conflict hubs. Categories include entity/predicate/attribute confusion, dates, people, prices, locations, negation, contradiction, missing/paraphrased evidence, typo/acronym/synonym, long/short/spam/FAQ/Markdown and linking conflict. Fifty cases require answers, eleven require abstention, and three keyword queries assess retrieval only.

| Metric | Before | After |
|---|---:|---:|
| Document @1 | 93.75% | 95.31% |
| Document @3 | 95.31% | 95.31% |
| Passage @1, answerable cases | 90% | 92% |
| Passage @3, answerable cases | 94% | 94% |
| Valid direct answer, 50 answerable cases | 42% | 66% |
| Correct abstention, 11 absent-answer cases | 63.64% | 100% |
| Incorrect promotions, 61 answer-scored cases | 11 | 0 observed |

These are **not blind or production-wide percentages**. Zero observed wrong promotions in this small development set did not prevent the new live CPU failure; that failure was subsequently added as an explicit regression and repaired. The evaluation oracle uses expected source/value containment, exact years for deterministic date cases and source-text grounding; it is not an independent entailment judge and can miss overly broad answers.

The first harness draft mistakenly treated the three keyword queries as mandatory abstentions. The original baseline is preserved in `phase2e-before.json`; `phase2e-before-normalized.json` applies the corrected rubric to that SAME recorded run. Final evaluation excludes those three answer assertions too. This correction is disclosed rather than presenting incompatible before/after denominators.

Artifacts: [before, normalized](audit/phase2e-before-normalized.json), [after, neural shadow](audit/phase2e-after.json), [hybrid ablation](audit/phase2e-hybrid-after.json). The hybrid artifact is an earlier documented snapshot, not a substitute for final browser acceptance. It did not produce a material recall improvement on this synthetic set.

The runner stores query, Doc@1/@3, Passage@1/@3, answer validity, abstention, effective query, timing, source ranking and failure class separately. A right answer cannot erase retrieval failures. Passage metrics represent the ranked passage sequence, not a claim of general cross-paragraph reasoning.

### Neural data / calibration

Actual checkpoint: BPE vocabulary 450, 128-dimensional embeddings, four bidirectional encoder blocks, four heads, FFN 512, maximum sequence length 128, segment/position embeddings, start/end span heads and a binary answerability head; **884,612 parameters**. Windows overlap with stride 32. The final curriculum uses 15 micro-overfit examples plus 44 synthetic “public” examples, not a large externally sourced QA corpus. Five separate sanity examples precede training.

Current training code shuffles features with seed 42, then splits 85/15. Reconstruction using the saved tokenizer yields 50 training and 9 validation features; **five identical contexts cross that split**. The tokenizer itself is trained on all examples before splitting. Nine of fifteen reader benchmark items reuse training contexts; near-duplicate leakage may be higher. No independent held-out corpus or calibration fit is established by those experiments.

Final synthetic shadow confidence buckets (confidence is an uncalibrated combined score, including abstained outputs):

| Score bucket | Count | Observed answer/abstention correctness |
|---|---:|---:|
| .50–.60 | 15 | 20% |
| .60–.70 | 7 | 14.29% |
| .70–.80 | 5 | 20% |
| .80–.90 | 5 | 0% |
| .90–1.00 | 19 | 26.32% |

This is not a calibrated probability curve: some high values are answerability scores on abstentions, and extraction/type constraints intervene. It is decisive evidence against interpreting 0.99 as 99% end-answer correctness. No claim is made that the model improves SERP accuracy. Acronym expansion, interrogative checks, word-boundary constraints, lexical “semantic binding,” temporal proximity and arbitration weights are **hand-written post-processing**, not learned capabilities.

## L. Performance, caches, concurrency and memory

### Measured user path

| Measurement | p50 | p95 / tail | Conditions |
|---|---:|---:|---|
| Actual browser primary-visible proxy, 12 queries | **516.9 ms** | **1038.5 ms** | model warm, mixed uncached requests, rapid navigation and real discovery contention |
| Isolated HTTP main, final probe, 24 requests | 146.5 ms | 263.3 ms | primarily fresh rankings among discovery traffic |
| Subsequent concurrent HTTP main | 25.46 ms | 45.59 ms | primary ranking already cached; NOT an uncached speed claim |
| PAA final HTTP probe | 53.31 ms | 1097.64 ms | mixed ranking-cache hits/misses |
| Related final HTTP probe | 65.25 ms | 418.73 ms | mixed cache and contention |
| Fresh isolated core, first WW2 query | 405.15 ms | — | models loaded, passage/token caches cold |
| Same core repeat | 5.54 ms | — | explicitly marked ranking cache hit |
| 100 distinct stress queries | 215.66 ms | 281.64 ms | core, bounded ranking cache |

The earlier concurrent three-request HTTP pattern measured main p50/p95 **582.31/1121.87 ms**, PAA **2389.09/3869.98 ms**, related **1397.96/2328.36 ms**. Primary-first dispatch and ranking reuse reduce duplicated work. The preferred <500 ms browser budget is **not consistently met**. A ~1.04-second tail remains; no 42-ms browser claim is justified.

Browser instrumentation measures effect start through two animation frames after primary state commit. It does not include the initial Next shell/hydration and cannot prove compositor paint. Per-query browser records are in [browser-acceptance.json](audit/browser-acceptance.json); the CPU case in that run records the discovered failure before its subsequent retest. Direct HTTP measurements include transport/serialization; engine timings do not. No browser navigation-to-paint p95 is claimed.

Fresh disposable single-worker FastAPI readiness: **9697.62 ms** including lifespan/model warmup; first HTTP query **380.76 ms**, second cached query **8.13 ms**, different payment query **119.74 ms**. Model files and a compatible vector cache already existed. This is not a cold model download. The first HTTP waterfall was query analysis .52, lexical .43, dense 12.70, fusion .63, gating .23, ranking 127.53, passages 223.39, extraction 3.64 ms. Passage work and repeated document-global scoring dominate, not neural QA on normal requests.

Historical 4–20-second incidents cannot be rerun from missing old commits. The old runtime report attributes them to repeated QA in discovery, sequential windows, exhaustive Python span decoding, cold ONNX loading and CPU oversubscription. Current source confirms bounded passages, batched windows, top-K decoding and skip_qa discovery. The old exact 1000-forward-pass and 623x claims remain historical reports, not independently reconstructed measurements.

### Caches

| Cache | Key / value | Bound / invalidation / risk |
|---|---|---|
| Local DocumentStore | path -> document dictionaries | one corpus; file mtime refresh; malformed data raises; external edits still need pipeline rebuild |
| In-memory lexical/passages/graph | document snapshot | entire corpus; replaced on every CMS save/delete/index |
| Persistent embeddings | provider metadata + exact embedded input SHA256 -> vector | prune to current generation; no TTL; provider/model identity included |
| Query embeddings | provider instance + trimmed query -> vector | LRU 256; model lifetime; copies prevent caller mutation |
| Ranking | engine generation + original query/force_raw/mode -> full ranking | LRU 32; limit-independent slices/deep copies; QA diagnostic requests bypass; transient gate/semantic failures not cached |
| QA spans | reader/model + normalized question + passage hash -> QAResult | LRU 512; per-reader lifecycle; locked deep copies |
| Spelling | corrector + token -> correction or null | LRU 4096; cleared when corpus vocabulary rebuilds |
| Porter stems | word -> stem | LRU 32768; pure computation; no mutable global stemmer |
| Sentence/stem evidence | text -> sentence/token-stem structure | LRU 2048 each; content-keyed, bounded entry count, not a byte cap |
| PAA candidate pool | published authored questions/FAQs | rebuilt with pipeline; no independent answer-result cache |
| Related | no independent response cache | uses current graph/families/history and primary ranking reuse |
| Next fetch | `cache: no-store` | no intended stale API response cache; active-response guards added |

Index versions identify one published snapshot, with document/lexical/passage/semantic/FAQ/graph IDs plus a process boot ID. They do not constitute independently verified per-subsystem manifests. A failed rebuild after store persistence, external file changes without rebuild, or cross-process writes still require careful inspection; there is no transactional Firestore/index commit protocol. The API is designed/tested as a **single worker** local process, not a multi-worker distributed index.

Threads: PyTorch intra-op 2, observed inter-op 6; Fastembed ONNX configured for 2. FastAPI sync endpoints use worker threads; concurrent discovery can still contend for CPU. Reader initialization and caches have locks; immutable vector/index snapshots protect in-flight primary searches. Discovery globals are not a complete distributed concurrency architecture.

Fresh-process RSS: interpreter 38.47 MB; lexical/passages 110.12; vector arrays 119.73; embedding model 287.21; QA model 453.98; before stress 461.96; after 100 distinct searches 474.72 MB. Ranking cache stopped at 32 entries. This bounded run does not prove leak freedom; allocator retention and content caches account for part of growth. See [runtime.json](audit/runtime.json) and [cold-http.json](audit/cold-http.json).

## M. Test integrity and holdout procedure

The suite contains unit tests (NLP/BM25/graph/model shapes), synthetic integration tests (retrieval, structured authoring), exposed historical regressions, benchmark runners and several tests coupled directly to the mutable private default corpus. None of those existing files is actually blind. The old QA helper benchmark hands the gate a preselected candidate and bypasses FAQ selection; its truthfulness percentage is not a full-pipeline answer metric. PAA tests mostly check that an answer string exists, not that its proposition answers the question. The old temporal runtime tests require particular slugs despite corpus growth.

Substantive old assertions were retained. Final full suite: **107 passed, 5 failed, 2 warnings**, 27.76 seconds. Failing checks:

1. `test_passes_semantic_paraphrase`: supplies “Clients may split…” without any named organization/source context, but expects support for a particular organization. The stricter gate refuses that entity assumption.
2. `test_multidate_historical_arbitration`: fixed Japan #1 assertion fails where a more specific Meiji source now exists; implicit-clause/date handling also remains limited. Do not count this loop as all seven accepted queries.
3. `test_typo_recovery_preservation`: correction succeeds, but dedicated Japan geography outranks the old Japan slug.
4. `test_heading_aware_passage_selection`: dedicated Meiji article outranks the old Japan slug.
5. `test_historical_regression_a_yasir_dream`: neural shadow returns October 2026 instead of 2023. Main answer now abstains.

The new invariant/CMS tests separately passed, including injected gate outage, wrong entity/object, wrong FAQ predicate, nominal mention, question-as-answer, skip_qa model loading, cache isolation, model-aware vector hashes, publish/edit/unpublish, and external local-store refresh. The thin-content test was deliberately changed because its previous expectation encoded the removed 35% short=spam policy. Old blind test names were relabeled; expected substantive answers were not replaced with whatever the implementation returned.

TypeScript checking and the production Next build passed. ESLint on the four inspected web files remains failing: **23 errors and 1 warning**, including numerous existing `any` annotations and React hook/style findings. With no Git baseline, not every lint finding can be attributed historically. The lint failure is not hidden by the successful build.

### Prospective evaluation

After source freeze, `prospective_holdout.py` generated random fact values/entities at execution and ran once, refusing report overwrite. The first run preceded the subsequently discovered CPU fix and is retained as that snapshot's regression data. A final separately generated run is in [prospective-holdout-final.json](audit/prospective-holdout-final.json), with its exact source hash.

Both runs scored **20/24 under the frozen exact-output rubric**. Two failures are missed payment paraphrases. Two are formatting failures: a correct, grounded FAQ sentence containing the expected year rather than the bare year. The untouched raw metric labels those two as wrong promotions; manual review establishes that they are not incorrect facts. Raw reports were not rewritten to manufacture a better result.

These are **prospective sampled-fact checks, not independently authored blind tests**: the author knew the templates and the final run reused template families already exposed in the first run. Do not advertise either as a true external holdout. For a real next acceptance set: freeze code/checkpoint/provider hashes; have an independent evaluator author documents/questions/expected evidence outside the implementation workspace; expose only documents and queries; run once; release labels/results after signing the snapshot; thereafter label it regression data. Split neural training by source document/entity, not feature windows, and deduplicate contexts/paraphrase families before splitting.

## N. Remaining known failures, limits and other subsystem findings

* **Weakest product component: query-conditioned evidence selection.** The repaired gate is still a rule-based constraint checker with limited predicate vocabulary, a narrow synonym table, crude coreference and no general syntactic/contradiction model. It is not a learned entailment system. Appropriate abstentions have improved, but answerable-query recall remains only 66% in the development set.
* **Personal attributes:** bicycle specification can retrieve a commentary page that mentions bicycle and “specific” information. Porter conflation, broad passage signals and missing entity/attribute modeling remain; the gate suppresses its direct answer. Correct abstention does not excuse bad document ranking.
* **Paraphrases / acronym evidence:** split-fee questions, CPU/expanded-name evidence and pronoun-dependent locations still produce false abstentions. Embedding topic similarity does not solve relational validation.
* **Spelling:** `japna`, `bycycle`, `purhcase` are general edit-distance behaviors, not literal overrides. Unseen inflection protection is tested. On the live corpus's eight requested typo cases and sixteen natural/technical controls, observed correction precision was **100%**, recall **87.5%**, false correction rate **0%**. These are small exposed probes, not dictionary-wide estimates. `instalment` is recorded separately as a legitimate orthographic variant. Rare one-occurrence words and two-edit cases such as `pyskology` remain recall problems. [spelling-semantic.json](audit/spelling-semantic.json) preserves every outcome and cosine probes for bike/cycle/bicycle, Japan/Japanese/japna and payment/installment/split-fee phrases.
* **Semantic rescue:** BGE-small-en-v1.5, 384 normalized dimensions, local ONNX; document and passage matrices remain separate. Summary retrieval is intentionally truncated to 600 characters. Semantic rescue requires RRF eligibility, lexical evidence or high similarity, and a drift check; it cannot prove answerability. Unknown-word gating can reject valid all-synonym queries. No formal probability calibration exists for .30/.55/.58 thresholds.
* **Ranking:** `base = BM25 + 1.8*title + 1.2*heading + 1.5*passage + 2*phrase + 1.4*keyword + 5.5*dense + 45*RRF`; multiply by coverage (`.3+.7*c`, or `.6+.4*dense` for rescue), add authority/freshness/quality, then multiply by `(1-spam)`. Dense similarity and document-global signals are bounded; phrase and lexical contributions are corpus-sensitive. Passage per-term frequency now saturates at four; sentence coherence squares maximum sentence coverage; relation coverage contributes at most six. These rules are understandable but not statistically calibrated.
* **Constants:** [source-inventory.json](audit/source-inventory.json) inventories numeric literals with file, line, owner, purpose context, documentation presence and sensitivity/provenance fields. BM25 k1 1.2, field weights 3.5/2.5/2.8/1.8/1, RRF k=60 and semantic weight .85, rescue .58/.55, answer score thresholds 12/6 (FAQ 9/4.5), gate .38/.18 and weights .25/.30/.20/.15/.10, graph damping .85 / 25 iterations / cap 1.5, freshness 180-day half-life and .8 cap, QA top-K 12 / answerability .5 / early exit .82 / three passage budget are all material. Exact historical origins are unknown without commits/experiment manifests. Ranking weights, gate thresholds, synonym policy and spam boundaries have high sensitivity; tensor dimensions/window sizes have predictable capacity/runtime effects; indexing offsets/loop indices are low sensitivity. Prior tuning reports are not independent calibration evidence.
* **Spam:** stuffing/TTR/tag penalties still compete against exact and authority-linked distractors in the synthetic suite; obvious stuffed pages do not win the Quartz case. Legitimate repeated technical language can still be overpenalized by TTR. Short content alone is no longer a penalty. FAQ-heavy quality scoring needs broader adversarial coverage, especially because reconstruction of ranking-time Document metadata is incomplete.
* **Graph:** known published nodes, set-valued edges, self/broken links ignored, bounded PageRank/in-degree authority. Circular links can confer relative authority but the additive boost is capped at 1.5. Anchor text is not a separate main-ranking signal. Authority cannot make an unsupported direct answer pass the gate.
* **Passages / CMS:** headings, block types, AST marks and FAQ ownership are preserved; FAQ Q+A stays together. Markdown is cleaned for search snippets/passages. Nested lists/blockquote text joining, tiny-block dropping, long-paragraph splitting, adjacent-paragraph merging and source-offset fidelity remain limited. The AST is preferred when supplied; divergent AST versus serialized Markdown remains an authoring-contract risk.
* **PAA:** source-specific answer checks improved, but question relevance and answer truthfulness are separate. It may return no useful questions. This audit does not establish a broad PAA precision percentage. It cannot change main ranking state, record clicks or train a reranker; it can populate shared generation-correct caches and consume CPU. FAQ metadata deduplication was repaired.
* **Related/autocomplete:** meaningful source/graph/family/history signals, not generative answers. Related ranking can still inherit a poor top document. Autocomplete is independent of QA; history reads are unbounded file scans as history grows. Privacy-store exception handling can silently lose telemetry/settings and remains technical debt.
* **Privacy / Firebase:** running service reported local storage. Explicit test stores cannot switch to Firebase via ambient credentials. Configured Firebase initialization now fails visibly rather than silently falling back. No production/shared Firebase writes, service-account disclosure, or credential inspection occurred. No Firestore rules/emulator acceptance or deployed security audit was established from this snapshot. Local APIs have no authentication; loopback hosting is the intended boundary, not CORS-based security.
* **Repository hygiene:** private corpus/history, temporary data, service-account patterns, environment variants, checkpoints and local DB/log paths are ignored. Since this is not a Git checkout, ignore changes cannot prove previously published private files were removed. Public history auditing is still required before any repository publication.
* **Dependencies:** installed versions are inventoried: Torch 2.14.1+cpu, FastAPI .157.0, Fastembed .9.0, ONNX Runtime 1.31.0, NumPy 2.5.4, Pydantic 2.14.1, Firebase Admin 7.7.0. Web uses Next 16.4.2 / React 19.3.0. The Python project lacks a checked-in dependency manifest. No dependency upgrade was performed. Safer serialization was repaired locally; this is not a vulnerability-database scan or license audit.
* **Observability:** per-search IDs, process boot IDs, snapshot versions, ranking contributions, candidate/source/producer/rejection reason and QA status are visible. Semantic/QA exceptions are surfaced and answer-gate failures abstain. Normal logs avoid adding raw corpus/query bodies. Existing access logs and history remain private data. Structured timing components are not all perfectly disjoint measurements; cache-hit stage times are explicitly zeroed and marked.

### Direct answers to the twenty required questions

1. **Why the unrelated Yasir answer?** A winning employment FAQ returned before validation.
2. **Was the gate active?** On ordinary non-FAQ candidates, yes; on that FAQ path, no.
3. **Were there bypass fallbacks?** Yes: unconditional FAQs and exception fail-open. Both removed.
4. **Why excellent benchmarks but wrong UI?** Helper-only supplied-candidate checks missed production producers/arbitration; training/benchmark overlap and mutable-corpus assumptions further reduced evidential value.
5. **Backend, cache, contract or rendering?** This incident was backend bypass logic. The API and browser agreed; no stale cache was needed to explain it. Other genuine staleness/race bugs were found separately.
6. **Is japna generalized?** Yes; edit distance/transposition and corpus frequency, with no literal map. The selected Japan article can change with corpus competition.
7. **Meiji for the right reason?** A dedicated Meiji document now wins with relevant passage/heading evidence. Forcing the older Japan slug would be a benchmark patch.
8. **WW2 entry 1941?** Verified through isolated traces, API, regression and actual browser; general inflection/acronym/sentence/date binding. Not a universal date-QA guarantee.
9. **QA useful beyond rules?** No demonstrated current SERP benefit; shadow predictions remain unreliable.
10. **Neural versus rules?** Neural encoder/span/answerability logits; typed decoding, lexical/acronym binding, temporal proximity and arbitration are rules.
11. **Worth runtime complexity?** Diagnostic/research value only at present; ordinary requests now skip it. Its startup/import/RAM cost still needs review.
12. **Embedding efficiency?** One cached query vector; persistent content-hashed corpus vectors; separate matrices; exact hash-input mismatch repaired. Startup, truncation, history and full-corpus scoring still cost time.
13. **PAA answers accurate?** Stronger shared validation, with remaining gate limitations; no proven universal precision.
14. **PAA questions relevant?** Canned and function-word contamination removed; quality still depends on source questions and retrieval.
15. **Featured Answers more trustworthy?** Concrete unsafe routes removed and absent-answer regressions improved, but the CPU incident proves finite development tests are not a truth guarantee.
16. **Historic 4–20 seconds?** Prior report cites QA discovery multiplication, decoding/window work, cold loading/threads; exact historical timings are not independently reproducible here.
17. **Browser p50/p95?** 516.9/1038.5 ms primary-visible proxy over twelve recorded queries, with its instrumentation limits stated above.
18. **Caches masking bugs?** No cache was necessary for the payment failure. Real vector/store/async staleness risks existed; current caches are generation/content keyed and observable, with remaining rebuild/transaction limits disclosed.
19. **CMS reaches every index?** Isolated lexical/passage/vector/FAQ/graph tests passed; actual CMS create/edit/FAQ/unpublish/search passed after fixing Save Draft. Only the temporary article was removed; 212 published documents restored.
20. **Weakest component?** Relational evidence selection/validation and its query decomposition, followed by the neural reader's data integrity and calibration.

## O. Recommendation for Phase 2F

Do **not** begin Phase 2F from a green benchmark claim. First close the remaining Phase 2E acceptance work: personal-attribute ranking, grounded paraphrase/coreference recall, honest corpus-independent tests, an independently authored final-code holdout, bounded PAA tail latency, byte-bounded cache/memory checks, dependency reproducibility and store/index transaction diagnostics. Keep the neural reader in the lab until leakage-free evaluation demonstrates incremental value over the deterministic baseline.

The architecture is clearer and the reproduced unsafe promotion routes are repaired. The evidence does not justify declaring the product generally trustworthy or every acceptance criterion complete.
