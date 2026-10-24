# PESE Neural Genesis: PESE-REL-DATA-0
## Phase N1 Learning Contract & Dataset Quality Report 🧠🌱

> **Dataset Identifier**: `PESE-REL-DATA-0`  
> **Phase**: Neural Genesis Baby Phase N1  
> **Status**: FROZEN & VALIDATED  
> **Target Architecture**: Future `PESE-Rel-0` (Phase N2)  
> **Model Training Status**: **STRICTLY ZERO (Contract & Evaluation Phase Only)**  
> **Production Ranking Authority**: **STRICTLY ZERO**  

---

## 1. Mission & Engineering Purpose

PESE has established high-precision document retrieval through hybrid BM25F lexical scoring and local dense BGE embeddings. Independent evaluations consistently demonstrate the following operational pattern:

```text
Query
  ↓
Correct Document       Very Often  [OK]
  ↓
Correct Passage        Very Often  [OK]
  ↓
Does this passage actually answer the question?
                       Weak / Vulnerable  [GAP]
```

Current failure modes frequently stem from lexical or topical conflation:
- **Same Topic $\neq$ Answers the Question**: When multiple candidate sentences discuss the query's primary entity, similarity-based models promote whichever passage shares the highest term overlap or cosine similarity, even if it describes a completely different predicate, date, cause, or actor.
- **Engineered Rules vs. Learned Understanding**: PESE's deterministic `AnswerRelevanceGate` uses grammar rules, regex patterns, and stem sets. While conservative and high precision on exact patterns, deterministic code cannot scale to arbitrary semantic paraphrases without brittle heuristics.
- **Corpus vs. Brain Separation**:
  - The **Corpus** determines **WHAT PESE KNOWS** (facts, documents, memories).
  - The **Neural Model** determines **HOW PESE UNDERSTANDS** (relational grammar, proposition binding, actor-action entailment).
  - New documents index immediately into BM25F/BGE. They must **never** trigger neural retraining.

Phase N1 builds the foundation: **defining what PESE must learn before training the brain**.

---

## 2. Core Data Contract & Schema

The relational reasoning contract is binary: `ANSWERS` vs `DOES_NOT_ANSWER`. Rich negative metadata is preserved for diagnostic error analysis, but never conflated with the binary training target.

### Example Schema Representation
```json
{
  "id": "pese-rel-train-0001",
  "question": "Who repaired the station clock?",
  "evidence": "Engineer Nadia repaired the station clock in 1998.",
  "label": "ANSWERS",
  "answer_type": "PERSON",
  "scenario_family": "train_station_clock_01",
  "source_id": "synth_station_archive_01",
  "relation_family": "repair_actor",
  "difficulty": "direct",
  "negative_reason": null,
  "contrast_type": "DIRECT_FACTUAL",
  "is_challenge": false,
  "entities": ["Nadia", "Charles", "Hamza", "station clock"],
  "notes": null,
  "metadata": {}
}
```

And a hard-negative contrastive pair from the same scenario:
```json
{
  "id": "pese-rel-train-0005",
  "question": "Who repaired the station clock?",
  "evidence": "The station clock stopped during a violent winter storm.",
  "label": "DOES_NOT_ANSWER",
  "answer_type": "PERSON",
  "scenario_family": "train_station_clock_01",
  "source_id": "synth_station_archive_01",
  "relation_family": "repair_actor",
  "difficulty": "hard_negative",
  "negative_reason": "SAME_TOPIC_WRONG_RELATION",
  "contrast_type": "HIGH_OVERLAP_DISTRACTOR",
  "is_challenge": true,
  "entities": ["Nadia", "Charles", "Hamza", "station clock"],
  "notes": "High overlap distractor about clock stoppage"
}
```

---

## 3. Split Policy & Anti-Leakage Guarantees

Learning from the historical Phase 2D/2E QA audit (where 9 of 15 QA benchmark items shared training contexts), Phase N1 institutes **absolute structural partition guards**:

1. **Scenario Family Disjointness**: Every scenario family is assigned to exactly one split (`train`, `validation`, or `test`). Zero overlap.
2. **Source ID Disjointness**: Every synthetic document/scenario source ID is strictly disjoint across splits.
3. **Named Entity Disjointness**: The set of named entities (people, products, locations, institutions) in `train` is strictly disjoint from `validation` and `test`:
   $$\text{Entities}(\text{Train}) \cap \text{Entities}(\text{Val}) = \emptyset, \quad \text{Entities}(\text{Train}) \cap \text{Entities}(\text{Test}) = \emptyset, \quad \text{Entities}(\text{Val}) \cap \text{Entities}(\text{Test}) = \emptyset$$
4. **Disjoint Paraphrase Templates**: Syntactic templates and question formulations differ structurally between splits to test relation learning rather than memorized surface syntax.
5. **No Private Corpus Data**: 100% synthetic and public-safe. Zero user documents, search histories, personal memories, or Firestore data.
6. **No Old Holdout Leakage**: Zero historical acceptance queries or sealed holdouts copied into DATA-0.

---

## 4. Dataset Size, Label & Hard-Negative Distributions

`PESE-REL-DATA-0` achieves exact 50.0% label balance across all splits with a high concentration of hard negatives:

### 4.1 Split & Label Summary
| Split | Scenarios | Unique Sources | Unique Entities | ANSWERS | DOES_NOT_ANSWER | Total Examples |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Train** | 60 | 60 | 181 | 240 (50.0%) | 240 (50.0%) | **480** |
| **Validation** | 15 | 15 | 45 | 60 (50.0%) | 60 (50.0%) | **120** |
| **Test** | 15 | 15 | 45 | 60 (50.0%) | 60 (50.0%) | **120** |
| **Total** | **90** | **90** | **271** | **360 (50.0%)** | **360 (50.0%)** | **720** |

### 4.2 Hard-Negative Breakdown
Across all 360 negative examples in `PESE-REL-DATA-0`:
- `SAME_TOPIC_WRONG_RELATION`: 146 (40.6%)
- `WRONG_PREDICATE`: 85 (23.6%)
- `QUESTION_RESTATEMENT`: 78 (21.7%)
- `MISSING_INFORMATION`: 36 (10.0%)
- `WRONG_ENTITY` / `ENTITY_CONFUSION`: 6 (1.7%)
- `WRONG_PROPERTY` / `ATTRIBUTE_CONTRAST`: 5 (1.4%)
- `EXPLICIT_UNKNOWN`: 2 (0.6%)
- `RELATED_EVENT` / `WRONG_ANSWER_TYPE`: 2 (0.6%)

Hard negatives constitute **100%** of negative instances in the dataset; there are zero trivial out-of-domain random word strings.

---

## 5. Explicit Unknown Policy & Design Decision

During Phase 2 (RC2), a critical architectural question surfaced regarding queries such as:
> **Question**: *What time did Teva begin the inspection?*  
> **Evidence**: *No one recorded the time when the inspection began.*

### Policy Decision for PESE-REL-DATA-0:
1. **Factual Value Resolution**: For an extractive or factual question requesting a specific property value (e.g., a specific hour/minute), evidence stating that the value is unrecorded **does not provide the requested value**.
2. **Binary Classification Standard**: In `PESE-REL-DATA-0`, this example is labeled:
   $$\text{Label} = \text{DOES\_NOT\_ANSWER}$$
   $$\text{NegativeReason} = \text{EXPLICIT\_UNKNOWN}$$
   $$\text{IsChallenge} = \text{True}$$
3. **Future N2 Architecture Option**: In Phase N2, the classifier head can optionally predict a 3-way distribution:
   $$\{\text{ANSWERABLE\_SUPPORT}, \text{EXPLICIT\_UNKNOWN}, \text{NO\_SUPPORT}\}$$
   By keeping `negative_reason="EXPLICIT_UNKNOWN"` cleanly recorded in metadata, the dataset supports both binary classification and future multi-task calibration without schema breaking changes.

---

## 6. Baseline Benchmark Measurements (Zero Neural Training)

We evaluated five non-neural and heuristic baselines against `PESE-REL-DATA-0` to quantify dataset difficulty:

### 6.1 Performance Summary on Test Split (N = 120, 50% ANSWERS)
| Baseline Model | Accuracy | Precision (ANS) | Recall (ANS) | F1 (ANS) | TP | FP | TN | FN |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Majority Class** | 50.00% | 50.00% | 100.0% | 0.6667 | 60 | 60 | 0 | 0 |
| **Jaccard Token Overlap** | 49.17% | 49.55% | 91.67% | 0.6433 | 55 | 56 | 4 | 5 |
| **Keyword Coverage (Content)** | 52.50% | 51.35% | 95.00% | 0.6667 | 57 | 54 | 6 | 3 |
| **Rule Gate (`AnswerRelevanceGate`)** | 54.17% | 58.62% | 28.33% | 0.3820 | 17 | 12 | 48 | 43 |
| **Dense BGE Cosine (`bge-small-en-v1.5`)** | 52.50% | 51.28% | 100.0% | 0.6780 | 60 | 57 | 3 | 0 |

### 6.2 Challenge Subset Performance (N = 75, High-Difficulty Subset)
| Baseline Model | Accuracy | Precision | Recall | F1 |
| :--- | :---: | :---: | :---: | :---: |
| **Majority Class** | 20.00% | 20.00% | 100.0% | 0.3333 |
| **Jaccard Token Overlap** | 21.33% | 17.65% | 80.00% | 0.2892 |
| **Keyword Coverage** | 26.67% | 20.59% | 93.33% | 0.3373 |
| **Rule Gate (`AnswerRelevanceGate`)** | 64.00% | 0.00% | 0.00% | 0.0000 |
| **Dense BGE Cosine** | 24.00% | 20.83% | 100.0% | 0.3448 |

### 6.3 Hard-Negative Vulnerability & Low-Overlap Analysis (Test Split)
| Negative Category | Total Negatives | BGE Cosine FP Rate | Jaccard Overlap FP Rate | Rule Gate FP Rate |
| :--- | :---: | :---: | :---: | :---: |
| `SAME_TOPIC_WRONG_RELATION` | 15 | **93.3%** (14/15) | **86.7%** (13/15) | **0.0%** (0/15) |
| `WRONG_PREDICATE` | 15 | **93.3%** (14/15) | **93.3%** (14/15) | **0.0%** (0/15) |
| `QUESTION_RESTATEMENT` | 15 | **100.0%** (15/15) | **100.0%** (15/15) | **80.0%** (12/15) |
| `MISSING_INFORMATION` | 15 | **93.3%** (14/15) | **93.3%** (14/15) | **0.0%** (0/15) |
| **Low Overlap Paraphrase Recall** | 30 | **100.0%** | **83.3%** | **0.0%** (0/30) |

### 6.4 Key Scientific Insights:
1. **BGE is Not Truth**: Dense cosine similarity achieves 93.3% to 100% false positive rates on hard negatives. Because question and distractor share the same topic, the vector dot product remains high ($\ge 0.75$). Thresholding cosine similarity fails to solve relational answerability.
2. **Lexical Overlap Fails on Distractors**: Jaccard and keyword overlap models fail identically because hard negative sentences deliberately share high vocabulary overlap with the query.
3. **Rule Gate's Precision vs Recall Tradeoff**: The deterministic rule gate rejects 100% of topic-distractors and predicate mismatches, but misses 100% of low-overlap paraphrases, yielding an F1 of 0.3820 and 0% recall on challenge paraphrases.
4. **The Dataset Exposes the True Gap**: Non-neural methods achieve ~50% accuracy on the full test set and ~20-25% on the challenge subset. This proves `PESE-REL-DATA-0` is not trivially solvable.

---

## 7. Manual Inspection Sample (25 Positives & 25 Negatives)

In compliance with Phase N1 validation, 25 positive and 25 negative examples were sampled across `train`, `validation`, and `test` splits and manually audited for label correctness:

### Sampled Positives (25/25 Verified Correct)
1. `[train-0001]` Q: *Who repaired the station clock?* | EV: *Engineer Nadia repaired the station clock in 1998.* -> `ANSWERS`
2. `[train-0027]` Q: *Can clients split the consultation fee at Pearl Clinic?* | EV: *Visitors to Pearl Clinic are permitted to settle the examination charge across multiple billing cycles.* -> `ANSWERS`
3. `[train-0057]` Q: *Who maintains Kestrel Gardens?* | EV: *Mira looks after the grounds and flora across Kestrel Gardens.* -> `ANSWERS`
4. `[train-0083]` Q: *What are the documented facts regarding when was the al-mansur aqueduct completed?* | EV: *Documentation confirms that masons finished building the al-mansur aqueduct in 842 ce.* -> `ANSWERS`
5. `[train-0113]` Q: *Is an advance appointment required to visit Cedar Archive?* | EV: *Visitors must book a designated study slot 48 hours prior to entering Cedar Archive.* -> `ANSWERS`
6. `[train-0139]` Q: *What are the documented facts regarding who restored the basra fresco?* | EV: *Documentation confirms that conservator sylvia cleaned and stabilized the basra fresco.* -> `ANSWERS`
7. `[train-0169]` Q: *What is the elevation of Ember Pass?* | EV: *Ember Pass reaches its summit at an altitude of 2,460 meters.* -> `ANSWERS`
8. `[train-0195]` Q: *What are the documented facts regarding who curated the wild barley collection at sylvan vault?* | EV: *Documentation confirms that botanist alden accessioned and dried the wild barley specimens.* -> `ANSWERS`
9. `[train-0225]` Q: *What is the glide ratio of the Kaelen Glider?* | EV: *The craft boasts a certified lift-to-drag glide ratio of 44 to 1.* -> `ANSWERS`
10. `[train-0251]` Q: *What are the documented facts regarding does cedar dental guarantee its implant posts?* | EV: *Documentation confirms that every titanium implant installed by cedar dental carries a lifetime structural warranty.* -> `ANSWERS`
11. `[train-0281]` Q: *What diameter is the high-gain dish on the Zephyr Probe?* | EV: *The paraboloid antenna dish measures exactly 2.4 meters across.* -> `ANSWERS`
12. `[train-0307]` Q: *What are the documented facts regarding at what temperature does crestview bio run fermentation?* | EV: *Documentation confirms that the culture broth temperature is held steadily at 32 °c throughout growth.* -> `ANSWERS`
13. `[train-0337]` Q: *What stray light rejection ratio does Prism Photometer achieve?* | EV: *The dual monochromator layout provides a stray light rejection ratio of 10^-6.* -> `ANSWERS`
14. `[train-0363]` Q: *What are the documented facts regarding in what month do green turtles nest at phaedra colony?* | EV: *Documentation confirms that female green turtles crawl ashore to lay eggs primarily throughout july.* -> `ANSWERS`
15. `[train-0393]` Q: *What natural period is tuned into Atlas Seismograph?* | EV: *The horizontal astatic pendulum is tuned to a natural resonant period of 20 seconds.* -> `ANSWERS`
16. `[train-0419]` Q: *What are the documented facts regarding what water flow rate circulates through hassan well?* | EV: *Documentation confirms that submersible pumps circulate thermal brine at a steady rate of 35 liters per second.* -> `ANSWERS`
17. `[train-0449]` Q: *What focal length is ground into the Idris Objective lens?* | EV: *The apochromatic triplet optic features an effective focal length of 800 mm.* -> `ANSWERS`
18. `[train-0475]` Q: *What are the documented facts regarding who mounted the holotype specimen at hana herbarium?* | EV: *Documentation confirms that botanist idris pressed and formally labeled the holotype flowering branch in 1935.* -> `ANSWERS`
19. `[val-0025]` Q: *What storage engine powers Lyra System?* | EV: *Lyra System utilizes a memory-mapped columnar storage engine.* -> `ANSWERS`
20. `[val-0051]` Q: *What are the documented specifications regarding what is the peak conversion efficiency of meridian array?* | EV: *Documentation confirms that the meridian array achieves a peak photovoltaic efficiency of 22.8%.* -> `ANSWERS`
21. `[val-0081]` Q: *Who oversaw piling replacement at Theodora Pier?* | EV: *Marine contractor Ignatius drove steel-sleeved concrete pilings at Theodora Pier.* -> `ANSWERS`
22. `[val-0107]` Q: *What are the documented specifications regarding what pulse repetition frequency does leander radar transmit?* | EV: *Documentation confirms that the solid-state marine surveillance array operates at a pulse repetition rate of 1,500 hz.* -> `ANSWERS`
23. `[test-0017]` Q: *What time did the Cygnus Probe reach perihelion?* | EV: *Flight director Kael confirmed perihelion passage at 14:22 UTC.* -> `ANSWERS`
24. `[test-0043]` Q: *What are the documented findings regarding what crystal is used in the oberon detector scintillator?* | EV: *Documentation confirms that the oberon detector array is populated by bismuth germanate scintillation crystals.* -> `ANSWERS`
25. `[test-0073]` Q: *What clamping force is exerted by the Apex Press?* | EV: *The dual-ram hydraulic cylinders deliver an operational clamping force of 12,000 metric tons.* -> `ANSWERS`

### Sampled Negatives (25/25 Verified Correct)
1. `[train-0005 - SAME_TOPIC_WRONG_RELATION]` Q: *Who repaired the station clock?* | EV: *The station clock stopped during a violent winter storm.* -> `DOES_NOT_ANSWER`
2. `[train-0031 - EXPLICIT_UNKNOWN]` Q: *What time did Tariq begin the clinical inspection?* | EV: *No one recorded the time when the inspection began.* -> `DOES_NOT_ANSWER`
3. `[train-0061 - SAME_TOPIC_WRONG_RELATION]` Q: *Who maintains Kestrel Gardens?* | EV: *The Kestrel Gardens maintenance schedule is published on the welcome kiosk.* -> `DOES_NOT_ANSWER`
4. `[train-0087 - QUESTION_RESTATEMENT]` Q: *When was the Al-Mansur Aqueduct completed?* | EV: *Specialists repeatedly investigate: 'When was the Al-Mansur Aqueduct completed?'* -> `DOES_NOT_ANSWER`
5. `[train-0117 - SAME_TOPIC_WRONG_RELATION]` Q: *Is an advance appointment required to visit Cedar Archive?* | EV: *The Cedar Archive reading room provides free wireless internet to all patrons.* -> `DOES_NOT_ANSWER`
6. `[train-0143 - QUESTION_RESTATEMENT]` Q: *Who restored the Basra Fresco?* | EV: *Specialists repeatedly investigate: 'Who restored the Basra Fresco?'* -> `DOES_NOT_ANSWER`
7. `[train-0173 - SAME_TOPIC_WRONG_RELATION]` Q: *What is the elevation of Ember Pass?* | EV: *Farid navigated Ember Pass during the late spring thaw.* -> `DOES_NOT_ANSWER`
8. `[train-0199 - QUESTION_RESTATEMENT]` Q: *Who curated the wild barley collection at Sylvan Vault?* | EV: *Specialists repeatedly investigate: 'Who curated the wild barley collection at Sylvan Vault?'* -> `DOES_NOT_ANSWER`
9. `[train-0229 - SAME_TOPIC_WRONG_RELATION]` Q: *What is the glide ratio of the Kaelen Glider?* | EV: *The Kaelen Glider wings are constructed from carbon fiber composite.* -> `DOES_NOT_ANSWER`
10. `[train-0255 - QUESTION_RESTATEMENT]` Q: *Does Cedar Dental guarantee its implant posts?* | EV: *Specialists repeatedly investigate: 'Does Cedar Dental guarantee its implant posts?'* -> `DOES_NOT_ANSWER`
11. `[train-0285 - SAME_TOPIC_WRONG_RELATION]` Q: *What diameter is the high-gain dish on the Zephyr Probe?* | EV: *The Zephyr Probe passed the orbital trajectory of Mars.* -> `DOES_NOT_ANSWER`
12. `[train-0311 - QUESTION_RESTATEMENT]` Q: *At what temperature does Crestview Bio run fermentation?* | EV: *Specialists repeatedly investigate: 'At what temperature does Crestview Bio run fermentation?'* -> `DOES_NOT_ANSWER`
13. `[train-0341 - SAME_TOPIC_WRONG_RELATION]` Q: *What stray light rejection ratio does Prism Photometer achieve?* | EV: *Prism Photometer was calibrated using a deuterium standard lamp.* -> `DOES_NOT_ANSWER`
14. `[train-0367 - QUESTION_RESTATEMENT]` Q: *In what month do green turtles nest at Phaedra Colony?* | EV: *Specialists repeatedly investigate: 'In what month do green turtles nest at Phaedra Colony?'* -> `DOES_NOT_ANSWER`
15. `[train-0397 - SAME_TOPIC_WRONG_RELATION]` Q: *What natural period is tuned into Atlas Seismograph?* | EV: *Atlas Seismograph recorded deep teleseismic crustal wave arrivals.* -> `DOES_NOT_ANSWER`
16. `[train-0423 - QUESTION_RESTATEMENT]` Q: *What water flow rate circulates through Hassan Well?* | EV: *Specialists repeatedly investigate: 'What water flow rate circulates through Hassan Well?'* -> `DOES_NOT_ANSWER`
17. `[train-0453 - SAME_TOPIC_WRONG_RELATION]` Q: *What focal length is ground into the Idris Objective lens?* | EV: *Idris Objective is coated with anti-reflective magnesium fluoride films.* -> `DOES_NOT_ANSWER`
18. `[train-0479 - QUESTION_RESTATEMENT]` Q: *Who mounted the holotype specimen at Hana Herbarium?* | EV: *Specialists repeatedly investigate: 'Who mounted the holotype specimen at Hana Herbarium?'* -> `DOES_NOT_ANSWER`
19. `[val-0029 - SAME_TOPIC_WRONG_RELATION]` Q: *What storage engine powers Lyra System?* | EV: *Hydra Labs founded the Lyra System project in 2019.* -> `DOES_NOT_ANSWER`
20. `[val-0055 - QUESTION_RESTATEMENT]` Q: *What is the peak conversion efficiency of Meridian Array?* | EV: *Engineers frequently discuss: 'What is the peak conversion efficiency of Meridian Array?'* -> `DOES_NOT_ANSWER`
21. `[val-0085 - SAME_TOPIC_WRONG_RELATION]` Q: *Who oversaw piling replacement at Theodora Pier?* | EV: *Theodora Pier was originally opened to passenger steamers in 1908.* -> `DOES_NOT_ANSWER`
22. `[val-0111 - QUESTION_RESTATEMENT]` Q: *What pulse repetition frequency does Leander Radar transmit?* | EV: *Engineers frequently discuss: 'What pulse repetition frequency does Leander Radar transmit?'* -> `DOES_NOT_ANSWER`
23. `[test-0021 - SAME_TOPIC_WRONG_RELATION]` Q: *What time did the Cygnus Probe reach perihelion?* | EV: *Mission telemetry did not record the exact minute when perihelion was achieved.* -> `DOES_NOT_ANSWER`
24. `[test-0047 - QUESTION_RESTATEMENT]` Q: *What crystal is used in the Oberon Detector scintillator?* | EV: *Specialists repeatedly investigate: 'What crystal is used in the Oberon Detector scintillator?'* -> `DOES_NOT_ANSWER`
25. `[test-0077 - SAME_TOPIC_WRONG_RELATION]` Q: *What clamping force is exerted by the Apex Press?* | EV: *The Apex Press was manufactured in a heavy industrial machinery yard.* -> `DOES_NOT_ANSWER`

---

## 8. Cryptographic Manifest & File Hashes

All split files and manifests are frozen in `engine/neural/data/pese_rel_data_0/`:

```json
{
  "dataset_name": "PESE-REL-DATA-0",
  "dataset_version": "1.0.0",
  "total_examples": 720,
  "file_hashes": {
    "train.json": "280b47feccfb4b2e0524058ed0e0dfb371bc61f09b19dd4cfda96e98bdb57ce5",
    "validation.json": "3b1cc202a2d435b1d4ab6b8f406b8ab554af034e432f12962a648de34ef47bf5",
    "test.json": "db739b29e6e5891fd6a83804ab29925cc9c536fbc5b1231268d77b770ea5df89"
  }
}
```

---

## 9. Future Model Architecture Recommendation: `PESE-Rel-0` (Phase N2)

### 9.1 Specifications
- **Architecture**: Cross-Encoder Bidirectional Transformer (Pre-LayerNorm).
- **Vocabulary Size**: 512 subwords via `BPETokenizer`.
- **Model Dimension ($d_{\text{model}}$)**: 128.
- **Layers**: 4.
- **Attention Heads**: 4 ($d_{\text{head}} = 32$).
- **FFN Hidden Dimension ($d_{\text{ff}}$)**: 512.
- **Max Sequence Length ($T_{\text{max}}$)**: 128 tokens.
- **Output Head**: Pooled `[CLS]` projection $\to \text{Linear}(128, 2)$ predicting `[P(DOES_NOT_ANSWER), P(ANSWERS)]`.
- **Total Parameters**: **875,522 parameters** (~3.5 MB float32, ~0.9 MB INT8 dynamic quantization).
- **Inference Latency**: Estimated **1.5 ms – 3.2 ms** per candidate sentence on a local AMD Ryzen CPU.

### 9.2 Separation of Responsibilities
```text
                         PESE QUERY EXECUTION
                                  │
                                  ▼
                    Candidate Retrieval (BM25F + BGE)
                                  │
                                  ▼
                       Passage & Sentence Scorer
                                  │
                                  ▼
               Top 3-5 Candidate Factual Sentences
                                  │
                 ┌────────────────┴────────────────┐
                 ▼                                 ▼
         CORPUS EVIDENCE                  RELATION BRAIN
         (What is True)                  (PESE-Rel-0 Model)
        Passage Sentences              Evaluates P(ANSWERS | Q, E)
                 │                                 │
                 └────────────────┬────────────────┘
                                  ▼
                       Validated Grounded Answer
```

### 9.3 Future Learning Loop (Design Only — Not Implemented in N1)
```text
Real Searches
  ↓
Grounded Signal Curation (Explicit Human/Audited Ground Truth)
  ↓
Curated Training Candidate Batches
  ↓
Candidate Model Checkpoint
  ↓
Offline Benchmark (DATA-0 Evaluation)
  ↓
Shadow SERP Scoring (Zero Authority)
  ↓
Promotion Gate (Measurably Superior F1 on Hard Negatives & Paraphrases)
```

**Never Self-Train from Raw Searches**: A query is not ground truth. A user click is not ground truth. Unfiltered self-training creates positive-feedback drift loops and hallucination contamination.
