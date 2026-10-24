# PESE-Rel-0: Model Card 🧠🌱
## Foundational Cross-Encoder Relation Classifier

> **Model Identifier**: `PESE-Rel-0`  
> **Repository Registry ID**: `PESE-Rel-0`  
> **Status**: `ModelStatus.EXPERIMENT`  
> **Architecture**: Cross-Encoder Bidirectional Transformer (Pre-LayerNorm)  
> **Production Ranking Authority**: **STRICTLY ZERO (`allowed_for_ranking = False`)**  
> **Production Answer Authority**: **STRICTLY ZERO (`allowed_for_answers = False`)**  
> **Checkpoint File**: `engine/neural/checkpoints/relation/peserel0_best.pt`  
> **Checkpoint SHA-256**: `1dd87075cfbf23c09fed5e90be948c6c7af005e9e909ab47e5df6c374b56ff70`  
> **Tokenizer SHA-256**: `e2023f42797473452a4a702ddb0894b6540277b85f5bdcc7436ecd1587ea03ec`  

---

## 1. Purpose

`PESE-Rel-0` is a compact, CPU-first relational answer-support classifier developed under Neural Genesis Baby Phase N2.

Its mission is strictly bounded to answering one fundamental question:
```text
QUESTION
   +
CANDIDATE EVIDENCE
   ↓
Does this evidence actually answer the question?
   ↓
[ P(ANSWERS), P(DOES_NOT_ANSWER) ]
```

### Architectural Responsibilities
- **What it IS**: A binary relation classifier determining proposition-level answer support between a query and a retrieved candidate sentence or passage.
- **What it is NOT**:
  - NOT a search engine or reranker.
  - NOT an answer span extractor or generative language model.
  - NOT a knowledge base or factual memory store.
  - NOT permitted to touch production search ranking, BM25F scores, QueryFrame routing, or Featured Answers.

---

## 2. Architecture

`PESE-Rel-0` implements a bidirectional cross-encoder Transformer using Pre-LayerNorm residual blocks and segment-type embeddings to preserve explicit distinction between query tokens and evidence tokens.

```text
Inputs: [CLS] Question [SEP] Evidence [SEP]
  │
  ├── Token Embeddings (Vocab: 512, d_model: 128)
  ├── Learned Positional Embeddings (Max Seq Len: 128)
  └── Segment Type Embeddings (0 = Question, 1 = Evidence)
  │
  ▼
[+] Element-wise Embedding Sum & Layer Normalization (Pre-LN)
  │
  ▼
4x Transformer Encoder Blocks:
  ├── Multi-Head Bidirectional Self-Attention (4 heads, d_k = 32)
  ├── Residual Addition & Layer Normalization
  ├── Feed-Forward Network (d_model: 128 -> d_ff: 512 -> GELU -> 128)
  └── Residual Addition
  │
  ▼
Final Layer Normalization
  │
  ▼
[CLS] Pooled Representation (d_model = 128)
  │
  ├── Linear Projection (128 -> 128) + GELU + Dropout(0.1)
  └── Classification Head (128 -> 2 logits)
  │
  ▼
Output: [Logit(DOES_NOT_ANSWER), Logit(ANSWERS)]
```

---

## 3. Training Data

`PESE-Rel-0` was trained exclusively on the frozen `PESE-REL-DATA-0` train split created in Phase N1.

- **Split Partitioning**: Primary grouping by `scenario_family` and `source_id`.
- **Distribution Balance**: Exactly 50.0% `ANSWERS` and 50.0% `DOES_NOT_ANSWER`.
- **Dataset Partition Counts**:
  - **Train**: 480 examples (240 positive, 240 negative)
  - **Validation**: 120 examples (60 positive, 60 negative)
  - **Test**: 120 examples (60 positive, 60 negative)
  - **Total**: 720 examples

---

## 4. Split Integrity

Strict disjointness invariants enforced and verified cryptographically:
- **Scenario Families**: 0 overlap between Train, Validation, and Test sets.
- **Source Documents**: 0 overlap between splits.
- **Named Entities**: 0 shared entities across splits.
- **Corpus Independence**: ZERO examples derived from private user search logs, private corpora, or holdout benchmarks.

---

## 5. Tokenizer

- **Type**: Custom Subword Byte-Pair Encoding (`RelationTokenizer`).
- **Training Scope**: Trained **strictly on Train Split text only** (zero exposure to validation or test data).
- **Vocabulary Size**: 512 tokens.
- **Special Tokens**:
  - `<pad>`: ID 0
  - `<unk>`: ID 1
  - `[CLS]`: ID 2
  - `[SEP]`: ID 3
- **OOV Audit**: 100.0% token coverage across Train, Validation, and Test splits. 0 unknown tokens encountered. 0.0% sequence truncation at maximum sequence length 128.

---

## 6. Training Configuration

| Parameter | Value |
|---|---|
| Hardware | Local Developer CPU (Intel Core i7-14700K) |
| Optimizer | AdamW |
| Initial Learning Rate | $3 \times 10^{-4}$ |
| Weight Decay | 0.01 |
| Learning Rate Schedule | Cosine Annealing with 20% warmup steps |
| Batch Size | 16 |
| Maximum Sequence Length | 128 tokens |
| Dropout | 0.10 |
| Loss Function | Cross-Entropy Loss |
| Early Stopping Patience | 8 epochs on Validation F1 |
| Total Epochs Executed | 13 epochs (Best: Epoch 5) |
| Total Training Time | 123.46 seconds (~50.5 examples/sec) |

---

## 7. Validation Performance

Validation checkpoints were evaluated at the end of each epoch on the frozen 120-example validation split:

| Epoch | Val Loss | Val Accuracy | Val Precision | Val Recall | Val F1 | Checkpoint Status |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 0.5342 | 75.00% | 0.6970 | 0.7667 | 0.7302 | Saved |
| 2 | 0.4485 | 73.33% | 0.6415 | 0.9000 | 0.7490 | Saved |
| 3 | 0.4619 | 76.67% | 0.6709 | 0.8833 | 0.7626 | Saved |
| 4 | 0.4703 | 75.83% | 0.6552 | 0.9500 | 0.7755 | Saved |
| **5** | **0.5052** | **77.50%** | **0.7037** | **0.9500** | **0.8085** | **BEST CHECKPOINT** |
| 13 | 0.8143 | 75.00% | 0.6923 | 0.9000 | 0.7826 | Early Stopped |

---

## 8. DATA-0 Test Performance

Evaluated against the frozen 120-example test split:

| Metric | Score | Exact Count |
|---|---:|---|
| **Accuracy** | **85.00%** | 102 / 120 correct |
| **Precision** | **77.63%** | 59 TP / (59 TP + 17 FP) |
| **Recall** | **98.33%** | 59 TP / (59 TP + 1 FN) |
| **F1 Score** | **86.76%** | $2 \cdot (P \cdot R) / (P + R)$ |
| **True Positives (TP)** | — | 59 |
| **False Positives (FP)** | — | 17 |
| **True Negatives (TN)** | — | 43 |
| **False Negatives (FN)** | — | 1 |
| **Low-Overlap Positive Recall** | **100.00%** | 30 / 30 correct |
| **High-Overlap Negative Rejection**| **90.00%** | 27 / 30 rejected |

---

## 9. Challenge Set Performance

The challenge subset comprises 75 hard contrastive examples designed to expose keyword and similarity fallacies:

| Metric | Score | Exact Count |
|---|---:|---|
| **Challenge Accuracy** | **77.33%** | 58 / 75 correct |
| **Challenge Precision** | **46.88%** | 15 TP / (15 TP + 17 FP) |
| **Challenge Recall** | **100.00%** | 15 / 15 correct |
| **Challenge F1** | **63.83%** | — |
| **Distractor Rejection Rate** | **71.67%** | 43 / 60 distractors rejected |

---

## 10. Prospective Generalization Check

Evaluated against 48 brand-new synthetic pairs across 8 unseen scenario families and 10 unseen entities generated post-freeze (0 overlap with DATA-0):

| Metric | Score | Interpretation |
|---|---:|---|
| **Accuracy** | 41.67% | Rejection degrades on completely novel domain vocabularies. |
| **Precision** | 45.00% | Distractors in unfamiliar domains trigger false positives. |
| **Recall** | 75.00% | Strong retention of answer-identifying capability. |
| **F1 Score** | 56.25% | — |
| **Low-Overlap Recall** | 87.50% | High structural transfer on paraphrased answers (7 / 8). |

---

## 11. Calibration & Operating Thresholds

### Confidence Buckets
| Confidence Range | Total Predictions | Correct Predictions | Empirical Accuracy |
|---|---:|---:|---:|
| 0.50 – 0.60 | 2 | 2 | 100.00% |
| 0.60 – 0.70 | 4 | 2 | 50.00% |
| 0.70 – 0.80 | 7 | 3 | 42.86% |
| 0.80 – 0.90 | 25 | 14 | 56.00% |
| **0.90 – 1.00** | **82** | **81** | **98.78%** |

Over 68% of all test predictions fall into the highest confidence bucket ($[0.90, 1.00]$), achieving 98.78% empirical accuracy.

### Operating Threshold Sweep
| Threshold $T$ | Accuracy | Precision | Recall | F1 | FP | FN |
|---:|---:|---:|---:|---:|---:|---:|
| 0.50 | 85.00% | 77.63% | 98.33% | 86.76% | 17 | 1 |
| 0.70 | 85.83% | 79.45% | 96.67% | 87.22% | 15 | 2 |
| 0.80 | 86.67% | 83.33% | 91.67% | 87.30% | 11 | 5 |
| **0.85** | **88.33%** | **88.33%** | **88.33%** | **88.33%** | **7** | **7** |
| 0.90 | 88.33% | 97.92% | 78.33% | 87.04% | 1 | 13 |

At threshold $T = 0.85$, the model achieves balanced 88.33% precision and recall. At $T = 0.90$, precision reaches 97.92% with only 1 false positive out of 60 negative candidates.

---

## 12. CPU Latency & Resource Footprint

- **Parameter Count**: 892,290 parameters (~3.57 MB float32 weights).
- **Disk Footprint**: 10.29 MB (PyTorch `.pt` file including optimizer state).
- **Cold Load Time**: 93.05 ms.
- **First Inference Latency**: 10.79 ms.
- **CPU Batch Latency Profiles** (Intel i7-14700K):
  - **Batch 1**: Mean 9.90 ms, **p50: 9.51 ms**, **p95: 13.46 ms** (comfortably under the 15 ms target).
  - **Batch 8**: Mean 34.99 ms, p50: 33.62 ms, p95: 48.12 ms (4.37 ms per item).
  - **Batch 32**: Mean 130.35 ms, p50: 126.98 ms, p95: 168.08 ms (4.07 ms per item).
- **INT8 Dynamic Quantization**:
  - Test Accuracy: 85.00% (exact 0.00% drop from FP32).
  - Test F1: 86.76% (exact match).
  - Batch 1 p50 Latency: 11.11 ms.

---

## 13. Known Failures & Diagnostic Boundaries

1. **Subtle Predicate Substitutions (`WRONG_PREDICATE`)**:
   - The model struggles when a sentence shares the query's subject and object, but replaces the core predicate verb with an action that does not resolve the question (e.g. *"Engineer Nadia admired the station clock"* vs *"Engineer Nadia repaired the station clock"*). Error taxonomy shows an 86.67% false positive rate on this specific failure mode.
2. **Unseen Domain Generalization**:
   - On completely novel terminology (e.g. aeroponics flow rates or submarine bathyspheres), the model maintains strong recall on true answers (75-87.5%), but becomes overly trusting of high-overlap distractors in unfamiliar vocabulary.
3. **Absence of Factual World Knowledge**:
   - PESE-Rel-0 does NOT know world facts (e.g. capital cities, company founders). It relies entirely on retrieved evidence.
