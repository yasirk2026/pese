# PESE Ranking V1: Explainable Scoring Architecture 😈

## Philosophy

PESE does not generate search rankings through opaque black-box neural models or arbitrary magic sums. Every ranking signal has an explicit information-retrieval justification, bounded impact, and auditable trace.

---

## The Ranking Signals

### 1. BM25F Multi-Field Lexical Score ($S_{\text{bm25f}}$)
- **Why it exists**: Raw term frequency is deceptive; repeating a word ten times does not make a page ten times more relevant. BM25 applies term frequency saturation ($k_1 = 1.2$) and document length normalization ($b_f = 0.5 - 0.75$).
- **Engine Field Weights**:
  - `title`: $3.5$ (titles represent high editorial intent)
  - `keywords`: $2.8$ (explicit taxonomy tags)
  - `headings`: $2.5$ (structural section scopes)
  - `meta_description`: $1.8$ (curated summary)
  - `body`: $1.0$ (general content)

### 2. Passage Relevance Signal ($S_{\text{passage}}$)
- **Why it exists**: A broad, long document might answer an exact question in one compact paragraph. Evaluating document-wide length can dilute this concentrated relevance.
- **Components**:
  - Passage term density
  - Term proximity bonus (matched terms occurring within 15 words)
  - Question-intent temporal bonus (+4.5 when query is `when` and passage contains a concrete date expression like `17 March 2024`)

### 3. Title & Heading Match Signals ($S_{\text{title}}, S_{\text{heading}}$)
- **Why it exists**: Direct presence of query terms in the document title or section headings provides an immediate structural alignment signal.

### 4. Exact Phrase Match Signal ($S_{\text{phrase}}$)
- **Why it exists**: Quoted query phrases or sequential query bigrams/trigrams occurring adjacent in the text receive a bonus (+2.0 in body, +4.0 in title).

### 5. Query Term Coverage Gating ($C_{\text{coverage}}$)
- **Why it exists**: If a query has 4 terms (e.g. `when did I buy my bicycle`) and a document contains only one frequent term (`bicycle`), it should not beat a document containing all terms.
- **Formula**:
  $$C_{\text{ratio}} = \frac{\text{matched\_stems}}{\text{total\_query\_stems}}$$
  $$\text{CoverageFactor} = 0.3 + 0.7 \times C_{\text{ratio}}$$
  A document matching 1 of 3 terms has its relevance gated by $\approx 0.53$, whereas a document matching 3 of 3 terms retains $1.0$ ($100\%$).

### 6. Internal Link Graph Authority ($S_{\text{link}}$)
- **Why it exists**: Documents endorsed by other internal knowledge pages carry higher structural authority.
- **Safety Bound**: Maximum bonus is capped at $+1.5$ points (on a $20-50+$ point relevance scale).
- **Golden Rule**: Link authority can never overwhelm query relevance. An irrelevant page with 50 links will never defeat an answer page.

### 7. Freshness Signal ($S_{\text{freshness}}$)
- **Why it exists**: Recently updated knowledge is often more accurate than stale notes.
- **Formula**:
  $$S_{\text{freshness}} = \frac{0.80}{1.0 + \frac{\text{DaysOld}}{180}}$$
- **Safety Bound**: Maximum bonus is $+0.80$ points. Freshness cannot override evergreen topical relevance.

### 8. Structural Quality Bonus ($S_{\text{quality}}$)
- **Why it exists**: Rewards documents that are well-structured (headings, meta descriptions, healthy content depth) with up to $+1.0$ point.

### 9. Spam & Keyword Stuffing Penalty ($P_{\text{spam}}$)
- **Why it exists**: Demonstrates the core rule: **more keywords ≠ automatically better ranking**.
- **Detection Triggers**:
  - Maximum non-stopword term ratio $> 15\%$ of content words
  - Severe keyword stuffing ($> 30-40\%$) incurs a penalty up to $-95\%$
  - Low vocabulary diversity (Type-Token Ratio $< 0.45$)
  - Empty or thin content ($< 30$ words)
- **Application**:
  $$\text{FinalScore} = \text{PositiveTotal} \times (1.0 - P_{\text{spam}})$$

---

## Complete Mathematical Scoring Pipeline

```text
1. BaseRelevance = BM25F + (1.8 * TitleSig) + (1.2 * HeadingSig) 
                 + (1.5 * PassageSig) + (2.0 * PhraseSig) + (1.4 * KeywordSig)

2. RelevanceGated = BaseRelevance * CoverageFactor

3. PositiveTotal = RelevanceGated + LinkAuthority + FreshnessBonus + QualityBonus

4. FinalScore = max(0.0, PositiveTotal * (1.0 - SpamPenalty))
```

---

## The Ranking Trace: "Why did A beat B?"

In developer debug mode, every result exposes its complete audit:
```text
BM25F Lexical: 4.8214
Title Signal: 1.5000
Heading Signal: 1.2000
Passage Signal: 10.3333
Phrase Match Signal: 0.0000
Keyword Tag Signal: 1.5000
Coverage Gating: 1.0000 (3/3 terms)
Link Authority: +1.3423
Freshness Bonus: +0.3892
Quality Bonus: +1.0000
Spam Penalty: -0.0%
----------------------------------------
Final Ranking Score: 35.6634
```
Selecting any competitor document in the audit drawer reveals a side-by-side comparison explaining the exact mathematical divergence.
