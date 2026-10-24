# PESE — Personal Evil Search Engine

PESE is a local hybrid personal search engine using fielded BM25F, local semantic retrieval, structured passages, conservative extractive answers, FAQs and a knowledge CMS.

Phase 2 candidate: **2.0.0-rc.2**. Current acceptance verdict: **PHASE 2 NOT ACCEPTED**. RC2 completed actual browser/CMS checks and improved exposed answer cases, but its new independent evaluation answered only 16/60 answerable questions correctly and made one inappropriate promotion. Retrieval remains strong. The historical RC1 failure and all independent results are preserved.

- [Installation and local synthetic demo](docs/installation-guide.md)
- [RC2 report and verdict](docs/phase-2-rc2-report.md)
- [Historical RC1 final report and verdict](docs/phase-2-final-report.md)
- [Architecture and modification map](docs/phase-2-architecture.md)
- [Independent holdout report](docs/audit/phase2f-holdout-report.md)
- [Post-fix exposed regression replay](docs/audit/phase2f-holdout-regression-report.md)
- [Frozen RC2 source manifest](docs/audit/phase2-rc2-source-freeze.json)
- [RC2 independent evaluation](docs/audit/phase2-rc2-independent-score.json)
- [Historical RC1 source manifest](docs/audit/phase2f-final-snapshot.json)
- [Publication readiness inventory](docs/audit/phase2f-public-readiness.json)

Use the pinned Python requirements and `npm ci` as described in the installation guide. Start with the isolated synthetic demo; it does not require a personal corpus or an experimental QA checkpoint. Keep the unauthenticated local API and CMS on loopback.

PESE can extract source-grounded answers for supported patterns and abstain when validation fails. It does not understand arbitrary questions or learn automatically. Neural QA remains experimental and cannot replace authoritative search answers. Relation embeddings remain diagnostic after an independent test demonstrated an unsafe promotion.

This working directory contains private data and audit backups alongside source. Do not publish it wholesale. No public deployment or Phase 3 work was performed.
