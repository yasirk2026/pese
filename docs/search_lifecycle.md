# PESE Search Lifecycle: From "Publish & Index" to SERP

This document traces the complete lifecycle of a document from creation through indexing, query processing, ranking competition, and presentation on the SERP.

---

## 1. Document Authoring & "Publish & Index"

1. In the CMS (`/admin/new` or `/admin/edit/[slug]`), the author inputs:
   - `title`: e.g. "My Bicycle Story"
   - `slug`: e.g. "my-bicycle-story"
   - `meta_description`: e.g. "Personal reflective journal entry on purchasing my commuter bicycle."
   - `content`: Markdown text structured with headings (`#`, `##`) and internal links `[My First Bicycle](/doc/my-first-bicycle)`.
   - `keywords`: `["bicycle", "journal", "2024", "story"]`.
   - `status`: `"published"` or `"draft"`.
2. When the author clicks **Publish & Index**:
   - The document is validated against Pydantic schemas.
   - The document is saved to the Firestore collection `documents` (or the local document store `firestore_documents.json`).
   - If `status == "published"`, the indexing pipeline is triggered.

---

## 2. Ingestion & Indexing Pipeline

1. **Passage Segmentation**:
   - The `PassageExtractor` scans the markdown content.
   - It identifies structural paragraph blocks separated by double line breaks.
   - It attaches the nearest preceding heading as `heading_context` (e.g. `## The Search and Decision`).
   - It assigns deterministic passage IDs: `my-bicycle-story#p0`, `my-bicycle-story#p1`, etc.
2. **NLP Field Tokenization & Stemming**:
   - For every document field (`title`, `headings`, `keywords`, `meta_description`, `body`):
     - Unicode normalization (NFKC) and accent stripping (`NFD`).
     - Contraction expansion (`don't` -> `do not`, `when's` -> `when is`).
     - Tokenization into alphanumeric tokens.
     - Porter Stemming with irregular verb lemmatization (`bought` -> `buy` -> `bui`).
3. **Inverted Index Update**:
   - Postings are created for both raw tokens and stems.
   - Positional offsets are recorded per field to enable exact phrase detection.
   - Document field lengths are recorded, and collection averages ($avgdl_f$) are updated.
   - Passages are indexed in the passage inverted index for sub-document density scoring.
4. **Internal Link Graph Reconstruction**:
   - Directed edges are extracted from explicit `internal_links` and inline markdown links `[text](/doc/slug)`.
   - In-degree counts and power-iteration PageRank ($d = 0.85$) are computed across all published nodes.

---

## 3. Query Execution Pipeline

When the user enters a search query (e.g. `when did I buy my bicycle`):

1. **Query Processing (`QueryRepresentation`)**:
   - Explicit quoted phrases are extracted (e.g. `"exact phrase"`).
   - Text is normalized and tokenized.
   - Generic stopwords (`did`, `my`) are filtered, while question intent words (`when`, `how`, `why`) are preserved.
   - Remaining query tokens are stemmed (`when`, `bui`, `bicycl`).
   - Bigram and trigram phrase candidates are generated.
2. **Candidate Retrieval (`CandidateRetriever`)**:
   - The index dictionary is queried for matching terms and stems.
   - Documents matching at least one query term form the candidate set.
3. **Multi-Field BM25F Scoring (`BM25FScorer`)**:
   - Robertson-Spärck Jones IDF is calculated:
     $$\text{IDF}(q) = \ln\left(\frac{N - n + 0.5}{n + 0.5} + 1.0\right)$$
   - Effective normalized term frequency is summed across fields using engine weights:
     - `title`: $3.5$
     - `headings`: $2.5$
     - `keywords`: $2.8$
     - `meta_description`: $1.8$
     - `body`: $1.0$
   - Non-linear BM25 saturation ($k_1 = 1.2$) produces the document's baseline lexical score.
4. **Passage-Level Scoring (`PassageScorer`)**:
   - Every passage of candidate documents is evaluated for term density, query coverage, term proximity, and question-intent temporal bonuses (e.g. presence of dates for `when` queries).
   - The highest scoring passage represents the document's passage signal.
5. **Quality & Spam Penalty Evaluation (`SpamDetector`)**:
   - Analyzes term distribution skew and type-token ratio (TTR).
   - Unnatural keyword stuffing (>15-30% of content is a single term) incurs penalties up to $-95\%$.
6. **Coverage Gating & Final Multi-Signal Combination**:
   - Query term coverage ratio ($k$ of $M$ terms present) gates relevance to prevent single-word matches from beating documents answering the full query.
   - Link authority ($0.0$ to $+1.5$), freshness bonus ($0.0$ to $+0.8$), and quality bonus ($0.0$ to $+1.0$) are blended.
   - The spam penalty multiplier is applied:
     $$\text{FinalScore} = \text{PositiveSignals} \times (1 - P_{\text{spam}})$$
7. **Snippet Selection & Highlighting (`SnippetGenerator`)**:
   - The winning passage is windowed around matched terms (snapping to word boundaries).
   - Query terms are wrapped in `<strong class="pese-hit">`.
   - If temporal intent matches an explicit date (e.g. `17 March 2024`), it is formatted as a featured answer.
8. **SERP Presentation**:
   - Results are sorted descending by `final_score`.
   - The Next.js frontend renders the ranked result list, URL breadcrumb, featured answer box (if applicable), and expandable audit trace drawer.
