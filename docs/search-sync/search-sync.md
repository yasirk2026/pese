# Search Sync 🫁🧠
## The Second Intelligence Organ of PESE

> "The moment a user dislikes a search decision, PESE should learn from that signal and the next comparable search should have the opportunity to improve."

---

## 1. What is Search Sync?

**Search Sync** is PESE's learning, synchronization, and preference adaptation system.

Where PESE previously operated purely as a feed-forward decision engine—evaluating a query, searching an index, arbitrating answers, and terminating—Search Sync introduces the **closed feedback loop**. It provides the engine with memory, the ability to digest user signals, and the framework to adapt future retrieval and answer arbitration safely and deterministically.

---

## 2. Why Does PESE Need Search Sync?

Before Search Sync, PESE suffered from systemic memorylessness:
- If a user searched `"Who develops GTA VI?"` and received an out-of-date or irrelevant result, clicking away or frowning had zero impact.
- Searching the same query 5 seconds later produced the exact same flawed result.
- The only mechanism for improving search was engineer intervention (code changes, rule additions, or offline model training).

Search Sync solves this by creating an asynchronous, local-first bridge between **user experience** and **ranking/arbitration intelligence**.

---

## 3. The Two-Brain Principle

PESE contains two cooperating intelligence systems:

```text
                           ┌──────────────────────────────┐
                           │          USER QUERY          │
                           └──────────────┬───────────────┘
                                          │
                                          ▼
                   ┌──────────────────────────────────────────────┐
                   │                     MAAE                     │
                   │  Multi-Aspect Arbitration Engine (The Brain) │
                   │                                              │
                   │  - Query Understanding (QueryFrame)          │
                   │  - Hybrid Lexical & Dense Retrieval          │
                   │  - Passage Scoring & Evidence Gating         │
                   │  - Deterministic & Neural QA Extraction      │
                   │  - Final Ranking Decision                    │
                   └──────────────┬───────────────────────────────┘
                                  │
                                  │ SERP & Answers
                                  ▼
                   ┌──────────────────────────────────────────────┐
                   │               USER EXPERIENCE                │
                   │                                              │
                   │  - Reads SERP results                        │
                   │  - Clicks 👍 (Helpful) or 👎 (Irrelevant)    │
                   │  - Selects optional feedback reason          │
                   └──────────────┬───────────────────────────────┘
                                  │
                                  │ Immediate Feedback Signal
                                  ▼
                   ┌──────────────────────────────────────────────┐
                   │                 SEARCH SYNC                  │
                   │           Feedback Memory (The Lungs)        │
                   │                                              │
                   │  - Ingests user preference signals           │
                   │  - Maintains SQLite active preference store  │
                   │  - Provides bounded preference adjustments   │
                   │  - Signals MAAE for subsequent searches      │
                   └──────────────────────────────────────────────┘
```

### Roles and Boundaries:
1. **MAAE (The Brain — Decides Now)**:
   - Owns query parsing, lexical retrieval, dense retrieval, evidence verification, answer extraction, and final score arbitration.
   - Answers the immediate question: *"Given the query, corpus, and current models, what should PESE show right now?"*
2. **Search Sync (The Lungs — Learns for Next Time)**:
   - Owns feedback ingestion, preference persistence, query-preference normalization, and adaptive adjustments.
   - Answers the retrospective question: *"What happened after MAAE made its decision, and what should MAAE know next time?"*

---

## 4. The Metaphor: Brain and Lungs

- **MAAE is the Brain**: It performs fast, synchronized, high-intensity cognitive work: scoring hundreds of documents, computing BM25F weights, executing dense semantic cosine dot products, validating answer spans, and rendering answers in milliseconds.
- **Search Sync is the Lungs**: It breathes in external reality from the environment (user satisfaction, dislikes, corrections), oxygenates the system's memory, and exhales fresh preference signals back into MAAE so the brain never becomes stale or asphyxiated by its own fixed heuristics.

---

## 5. Long-Term Architecture

In its full mature vision, Search Sync will encompass eight core sub-organs:

```text
[ User Clicks 👍/👎 ]
        │
        ▼
1. Feedback Ingestion ────────► 2. SQLite Preference Store
                                           │
                                           ├──────────────────────────┐
                                           │                          │ (Next Search)
                                           ▼                          ▼
                                 3. Adaptive Rank Adjustment    MAAE Scorer
                                           │
                                           ▼
                                 4. Sync Queues & Audits
                                           │
                                           ▼
                                 5. Background Sync Worker (Future)
                                           │
                                           ├──────────────────────────┐
                                           ▼                          ▼
                              6. Corpus Synchronizer     7. Neural Self-Training (PESE-Rel)
                                           │                          │
                                           └──────────┬───────────────┘
                                                      ▼
                                         8. Continuous Evaluation & Challenger
```

1. **Feedback Ingestion**: Zero-latency capture of user interaction signals with query context.
2. **Preference Store**: Local SQLite database storing active preferences and append-only event audit logs.
3. **Adaptive Rank Adjustment**: Bounded additive scoring adjustments applied during MAAE candidate ranking.
4. **Sync Queues & Audits**: Safe event buffers ensuring idempotent updates and full trace replayability.
5. **Background Sync Worker**: Asynchronous queue processor (decoupled from the real-time search loop).
6. **Corpus Synchronizer**: Detects document changes, re-indexes modified passages, and recomputes link graphs.
7. **Neural Self-Training**: Converts high-confidence negative and positive signals into supervised training pairs for relation models (`PESE-Rel`).
8. **Continuous Evaluation & Model Challenger**: Tests shadow models against frozen evaluation sets before promoting checkpoints to production.

---

## 6. Implementation Scope Matrix

| Capability | N3-A Status | Notes |
| :--- | :---: | :--- |
| **Local SQLite Preference Store** | ✅ **IMPLEMENTED** | Thread-safe, WAL-enabled, stored in `search_sync_feedback.db`. |
| **Active Preference Table & Audit Log** | ✅ **IMPLEMENTED** | Primary key `(normalized_query, target_type, target_id)`. |
| **Query Normalization Engine** | ✅ **IMPLEMENTED** | Lowercase, NFKC, contractions, punctuation stripping. |
| **Bounded Preference Scoring** | ✅ **IMPLEMENTED** | DISLIKE: $-4.0$, LIKE: $+2.0$, strictly bounded in $[-6.0, +3.0]$. |
| **MAAE Scorer Integration** | ✅ **IMPLEMENTED** | Integrated in Step 5 & Step 6 of `RankingEngine._search_uncached()`. |
| **Inspectable Base vs Sync Scores** | ✅ **IMPLEMENTED** | `base_score`, `search_sync_adjustment`, and trace audit lines exposed. |
| **Featured Answer Suppression** | ✅ **IMPLEMENTED** | Exact query dislike suppresses featured answer candidate cleanly. |
| **Web UI 👍/👎 Controls** | ✅ **IMPLEMENTED** | One-click feedback on organic results and Featured Answer cards. |
| **Non-blocking Reason Chips** | ✅ **IMPLEMENTED** | Subtle optional reason chips displayed only upon dislike. |
| **Query Cache Invalidation** | ✅ **IMPLEMENTED** | Submitting feedback immediately evicts stale query cache entries. |
| **Query-Specific Contextual Isolation** | ✅ **IMPLEMENTED** | Disliking Doc A for $Q_1$ has strictly $0.0$ penalty for $Q_2$. |
| *Background Worker Daemons (Celery/Cron)* | ❌ **NOT IMPLEMENTED** | Deferred to subsequent Search Sync baby phases. |
| *Corpus Re-indexing Watcher* | ❌ **NOT IMPLEMENTED** | Deferred to corpus sync phases. |
| *Automatic Neural Retraining* | ❌ **NOT IMPLEMENTED** | No automatic backward pass; models remain frozen. |
| *Model Challenger & Gate Promotion* | ❌ **NOT IMPLEMENTED** | Checkpoints remain evaluated offline. |
| *External Cloud Telemetry* | ❌ **FORBIDDEN** | PESE is 100% local-first and privacy-preserving. |
