# PESE Neural Genesis 😈🧠
## Phase 2C Architecture, Laboratory & Scientific Foundations

> **Version**: PESE 2.0 (Phase 2C: Neural Genesis)  
> **Status**: Experimental Laboratory Prototype  
> **Framework**: PyTorch 2.14.1 (CPU-compatible)  
> **Primary Model**: `PESE-NG-0` (~1.08M parameters)  
> **Production Ranking Influence**: **STRICTLY ZERO** (BM25F + BGE Hybrid remain in full control)  
> **Privacy Guarantee**: **ZERO** user documents, queries, or history in training datasets  

---

## 1. Executive Summary & Engineering Philosophy

Phase 2C establishes the first genuine, internal neural machinery of the **Personal Evil Search Engine (PESE)**:

1. **Self-Contained PyTorch Foundations**: Built from mathematical first principles in Python/PyTorch without calling third-party LLM APIs (OpenAI, Anthropic, Gemini) or relying on opaque black-box services.
2. **Deterministic & Lightweight**: Optimized for CPU execution on standard developer laptops without requiring multi-gigabyte CUDA installations or external cloud infrastructure.
3. **Scientific Rigor Over Hype**: We measure exact parameter counts, verify causal invariance, prove micro-overfit convergence ($\ge 70\%$ loss drop), and explicitly catalog model failure modes. Loss reduction is acknowledged as optimization convergence, not artificial general intelligence.
4. **Strict Isolation & Privacy**: PESE-NG-0 does **not** replace BM25F lexical scoring or BGE dense retrieval. It does not train on private user files or history.

---

## 2. Transformer Architecture (`PESE-NG-0`)

PESE-NG-0 is a causal auto-regressive Transformer decoder adhering to modern Pre-LayerNorm architectural principles.

### 2.1 Architectural Specifications

| Hyperparameter | Symbol | Value | Description |
| :--- | :---: | :---: | :--- |
| **Vocabulary Size** | $V$ | 256 / 1024 | Trained subword vocabulary via PESE-BPE-0 |
| **Model Dimension** | $d_{\text{model}}$ | 128 | Embedding and hidden representation dimension |
| **Layers** | $L$ | 4 | Pre-LayerNorm Transformer blocks |
| **Attention Heads** | $h$ | 4 | Parallel multi-head self-attention projections |
| **Head Dimension** | $d_k$ | 32 | $d_k = d_{\text{model}} / h$ |
| **FFN Inner Dimension**| $d_{\text{ff}}$ | 512 | Expansion factor of 4x |
| **Max Sequence Length**| $T_{\text{max}}$ | 128 / 256 | Context window for causal attention |
| **Dropout** | $p$ | 0.1 | Residual and attention dropout |
| **Total Parameters** | $N$ | **~1,088,256** | Analytical parameter equation verified |

---

### 2.2 Mathematical Formulation

For an input sequence of discrete token indices $\mathbf{x} = (x_1, x_2, \dots, x_T) \in \mathbb{N}^T$:

1. **Embedding Layer**:
   $$\mathbf{h}_0 = \mathbf{W}_e[x] + \mathbf{W}_p[pos], \quad \mathbf{h}_0 \in \mathbb{R}^{B \times T \times d_{\text{model}}}$$
   where $\mathbf{W}_e \in \mathbb{R}^{V \times d_{\text{model}}}$ and $\mathbf{W}_p \in \mathbb{R}^{T_{\text{max}} \times d_{\text{model}}}$.

2. **Pre-LayerNorm Transformer Block** ($l = 1, \dots, L$):
   $$\mathbf{u}_l = \mathbf{h}_{l-1} + \text{MultiHeadSelfAttention}(\text{LayerNorm}(\mathbf{h}_{l-1}))$$
   $$\mathbf{h}_l = \mathbf{u}_l + \text{FeedForward}(\text{LayerNorm}(\mathbf{u}_l))$$

3. **Causal Multi-Head Attention**:
   For head $i \in \{1, \dots, h\}$ with projections $\mathbf{W}_i^Q, \mathbf{W}_i^K, \mathbf{W}_i^V \in \mathbb{R}^{d_{\text{model}} \times d_k}$:
   $$\mathbf{Q}_i = \mathbf{X} \mathbf{W}_i^Q, \quad \mathbf{K}_i = \mathbf{X} \mathbf{W}_i^K, \quad \mathbf{V}_i = \mathbf{X} \mathbf{W}_i^V$$
   $$\mathbf{S}_i = \frac{\mathbf{Q}_i \mathbf{K}_i^\top}{\sqrt{d_k}} + \mathbf{M}_{\text{causal}}$$
   $$\text{Attention}(\mathbf{Q}_i, \mathbf{K}_i, \mathbf{V}_i) = \text{softmax}(\mathbf{S}_i) \mathbf{V}_i$$
   where the causal mask $\mathbf{M}_{\text{causal}}(j, k) = 0$ if $j \ge k$ and $-\infty$ otherwise.

4. **Feed-Forward Network (FFN)**:
   $$\text{FFN}(\mathbf{x}) = \text{GELU}(\mathbf{x} \mathbf{W}_1 + \mathbf{b}_1) \mathbf{W}_2 + \mathbf{b}_2$$
   where $\mathbf{W}_1 \in \mathbb{R}^{d_{\text{model}} \times d_{\text{ff}}}$ and $\mathbf{W}_2 \in \mathbb{R}^{d_{\text{ff}} \times d_{\text{model}}}$.

5. **Language Model Output Head**:
   $$\hat{\mathbf{y}}_t = \text{LayerNorm}(\mathbf{h}_L)_t \mathbf{W}_{\text{head}}^\top, \quad \hat{\mathbf{y}}_t \in \mathbb{R}^V$$

---

## 3. Tokenizer Laboratory

PESE Neural Genesis provides two deterministic tokenization options:

### 3.1 `CharTokenizer` (Baseline Sanity)
- Character-level mapping for printable ASCII and unicode characters.
- Out-of-vocabulary rate: 0% for mapped characters.
- Used for micro-overfit sanity checking and testing causal invariants without subword variance.

### 3.2 `BPETokenizer` (`PESE-BPE-0`)
- Custom Byte Pair Encoding implementation built completely from scratch.
- Learns statistical subword merge operations iteratively based on byte/character co-occurrence frequencies:
  $$\text{pair} = \arg\max_{(c_1, c_2)} \text{freq}(c_1, c_2)$$
- Balances vocabulary compactness ($V = 256$–$1024$) with compression ratios of $2.5\times$–$3.8\times$ relative to raw characters.

---

## 4. Training & Optimization Protocol

### 4.1 Optimization Parameters
- **Optimizer**: AdamW ($\beta_1 = 0.9, \beta_2 = 0.95, \epsilon = 10^{-8}$)
- **Weight Decay**: $\lambda = 0.01$
- **Learning Rate Schedule**: Linear warmup (first 10% of steps) followed by cosine decay down to $10\%$ of peak learning rate:
  $$\eta_t = \eta_{\text{min}} + \frac{1}{2}(\eta_{\text{max}} - \eta_{\text{min}})\left(1 + \cos\left(\frac{t - t_{\text{warmup}}}{T - t_{\text{warmup}}} \pi\right)\right)$$
- **Gradient Clipping**: Euclidean norm clipped at $\|\mathbf{g}\|_2 \le 1.0$ to prevent gradient explosion.
- **NaN/Inf Guards**: Active loss monitoring halts training immediately if an unrecoverable floating point exception occurs.

### 4.2 Checkpointing Protocol
Checkpoints are serialized to `.pt` files containing:
- `model_state_dict`
- `optimizer_state_dict`
- `model_config`
- `step`, `loss`, `metrics`, `timestamp`

All checkpoints are strictly isolated in `PESE/engine/neural/checkpoints/` and excluded from git tracking.

---

## 5. Experimental Verification & Results

### 5.1 Micro-Overfit Validation (Mandatory Gate)
- **Dataset**: Fixed 8-sentence synthetic micro-corpus (`MICRO_OVERFIT_TEXTS`).
- **Initial Cross-Entropy Loss**: $3.9071$
- **Final Cross-Entropy Loss**: $0.2134$
- **Loss Reduction**: **$94.54\%$** (Required threshold: $\ge 70.0\%$).
- **Status**: **PASSED**.

### 5.2 Baseline Synthetic Corpus Training
- **Dataset**: Clean, non-private technical corpus (38 sentences on IR, databases, algorithms).
- **Initial Loss**: $4.8722$
- **Final Loss**: $2.6622$
- **Duration**: ~20 seconds on CPU.
- **Status**: **PASSED**.

---

## 6. Documented Limitations & Failure Modes

In accordance with rigorous engineering honesty:

1. **Small Model Capacity (~1.08M parameters)**:
   PESE-NG-0 is an educational laboratory prototype designed for fast local CPU training. It cannot solve multi-step deductive logic or possess deep world knowledge.
2. **Autoregressive Hallucination Without Evidence Grounding**:
   Like all causal autoregressive models, unconstrained generation samples tokens statistically without validating factual claims. It must NEVER generate search results without extractive grounding.
3. **Absence of Extractive Supervision**:
   PESE-NG-0 was trained solely on next-token prediction. Determining whether a passage actually answers a user query requires extractive span heads and abstention training (planned for Phase 2D).

---

## 7. Future PESE-QA-0 Roadmap

Phase 2C establishes the contracts for future extractive QA:
- **`QAExample` Schema**: Questions, contexts, answer text, character offsets `(start_char, end_char)`, token offsets `(start_token, end_token)`.
- **FAQ-to-QA Exporter**: Automates the conversion of structured CMS FAQ items into verified QA training examples.
- **Abstention Contract ("NO EVIDENCE = NO ANSWER")**: Formally encodes unanswerable queries where `is_answerable = False`, forcing future models to emit a null span rather than hallucinating when corpus support is lacking.
- **Pairwise Reranker Schema (`RerankerPair`)**: Establishes training pairs for future cross-encoder relevance reranking.
