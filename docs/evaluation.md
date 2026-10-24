# PESE Evaluation: Scientific IR Benchmark 😈

## Purpose

To ensure ranking modifications are justified by empirical evidence rather than subjective impressions ("it feels better"), PESE incorporates an automated evaluation harness and ground-truth dataset.

---

## Benchmark Dataset

Located in `engine/evaluation/dataset.py`, the dataset contains 30 curated test queries covering all 4 core clusters and adversarial spam tests:

1. **Bicycle Cluster**: Personal memoirs, purchase dates, maintenance notes, equipment specs.
2. **Japanese Learning Cluster**: Roadmaps, Kana phonetics, vocabulary, Kanji radicals, immersion.
3. **Engineering Cluster**: Next.js Server Components, React hydration debugging, Firestore architecture, performance, inverted indexes.
4. **SEO & Information Retrieval Cluster**: Internal linking experiments, search intent, crawlability, content quality, BM25 derivation, passage retrieval.
5. **Adversarial Spam Test**: Queries matching keyword-stuffed documents to verify spam suppression.

---

## Metrics Measured

- **Mean Reciprocal Rank (MRR)**:
  $$\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$$
  Measures how high the first relevant document ranks.
- **Precision@K** ($K=1, 3$):
  Fraction of top-$K$ results that are genuinely relevant.
- **Recall@K** ($K=3$):
  Fraction of total relevant documents retrieved in top-$K$.
- **Hit Rate @ K** ($K=1, 3, 5$):
  Percentage of queries where at least one relevant document appears in top $K$.
- **Passage Extraction Accuracy**:
  Percentage of temporal/answer queries where the top result's snippet successfully extracts the expected ground-truth answer.
- **Spam Invasions**:
  Number of queries where an adversarial spam document erroneously attained the #1 rank.

---

## Running the Benchmark

### Option 1: Command Line
```powershell
cd PESE
.\engine\.venv\Scripts\python.exe -m engine.evaluation.runner
```

### Option 2: PowerShell Script
```powershell
cd PESE
.\scripts\run_benchmark.ps1
```

### Option 3: Web Dashboard
Navigate to `http://localhost:3000/admin/eval` and click **Run Scientific Benchmark**.

---

## Baseline Benchmark Results

```text
=================================================================
 [PESE SEARCH ENGINE BENCHMARK REPORT]
=================================================================
Total Test Queries Evaluated:    30
Mean Reciprocal Rank (MRR):      1.0000
Mean Precision@1:                1.0000
Mean Precision@3:                0.5000
Mean Recall@3:                   0.8500
Hit Rate @ 1:                    100.0%
Hit Rate @ 3:                    100.0%
Hit Rate @ 5:                    100.0%
Passage Extraction Accuracy:     100.0% (Temporal answer queries)
Spam Violations (Spam ranked #1): 0
=================================================================
```

Results are persisted as structured JSON in `PESE/engine/data/evaluation_report.json`.
