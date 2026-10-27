# N3 search and learning contract v1

Status: implemented safety foundation, experimental ranking adapter, **no accepted
relevance model**. This contract does not grant the historical Rel-0 classifier
ranking or answer authority. Activation requirements are frozen separately in
`n3-acceptance-v1.json` before any new holdout is opened.

## Search ownership and order

1. QueryAnalyzer owns spelling, normalization, intent and effective query.
2. BM25F and local BGE retrieve candidates; fusion records their independent ranks.
3. MinimumEvidenceGate owns admission. Rejected candidates never enter reranking.
4. MAAE owns base scores, passage selection, coverage, quality and authority.
5. Optional NeuralReranker consumes at most six admitted candidates ordered by
   **base** score and the effective query. It supplies a bounded delta, never a
   relevance label or permission to display an answer.
6. Search Sync supplies the existing exact-query preference delta (+2 LIKE/-4
   DISLIKE, configured limits -6/+3). Its value is independent of neural output.
7. Final score is `max(0, base + neural_delta + preference_delta)`, rounded to four
   decimals. Stable descending sorting preserves ties.
8. Deterministic answer extraction and AnswerRelevanceGate remain authoritative
   after sorting. A model may change which admitted document is inspected first;
   it cannot bypass answer validation. Wrong promotions must be measured on the
   entire integrated answer path before a model release.

Existing code computes preferences while building each candidate. Neural input
uses only base scores; the final combined sort follows the neural stage. This
preserves N3-A behavior when neural_delta is zero.

## Experimental normalization

Probabilities are never added to MAAE scores. Convert each score to centered
ordinal midrank in [-1,1] within the budget. The scale is the median positive
adjacent **unique base-score** gap. Delta = ordinal × min(relative_cap × abs(base),
gap_cap × scale). Equal base scores have zero scale; equal neural scores have
equal midrank. Monotonic probability calibration cannot change the adjustment.
Two preregistered configurations bound relative_cap to .03/.01 and gap_cap to
.75/.5. These are conservative **experimental ceilings**, not measured selected
weights. There is no approved production configuration.

Candidate count/order, score length, finite values, range [0,1], eligibility and
bounds are validated before mutation. Partial/invalid inference preserves all
baseline scores. Trace records base, neural delta/model identity, preference,
final score, status, resource measurements and authority separately.

## Identity, evidence and cache

SearchResult.evidence_provenance v1 binds request context, effective query,
target type/ID, document revision SHA-256, passage ID/text hash, ranking version,
index generation and model versions. Featured-answer receipts hash the actual
answer separately. Input decorated with a heading has a separate model-input hash.
The server retains at most 64 process-local presented contexts. Client metadata
cannot provide verified provenance. A known context with a mismatched query,
target, slug or rank receives 409. Unknown/expired/restarted contexts remain
unverified preference-only for compatibility and do not acquire an observation.

Cache hits get a new presentation receipt/context, with unchanged revision and
generation. They do not rerun inference, clone persisted observations, or count
as independent judgments. Old neural values are cleared and trace says
CACHED_NOT_OBSERVED. Feedback invalidates the raw presentation query's cache;
permission changes/reset invalidate serving-engine caches.

Diagnostics require exact context + normalized effective query + target type +
target ID. Verified feedback additionally requires revision, passage/hash,
generation, ranking and model identity agreement. Multi-passage or multi-model
ambiguity is reported rather than resolved by first-row/highest-confidence
selection. Legacy joins are explicitly diagnostic-only. Statistics use active
preferences, so repeated audit submissions do not count as independent votes.
LIKE/DISLIKE comparisons use exact enums/labels and the recorded threshold.

## Storage and consent

Canonical Brain/schema/snapshot versions remain unchanged. Existing metadata_json
stores operational receipts/model_versions with old rows left unverified. No
experimental table or dataset enters the snapshot contract. Permissions reside
in `.pese-intelligence-v1/permissions.json`, excluded by the snapshot allowlist.
Recovery requires new optional permissions. Indexing never invokes training.

Existing Search Sync preference learning defaults ON for compatibility, can be
paused and reset, and updates no parameters. Research collection, journal
permission, external contribution permission and neural search default OFF.
Research collection has no desktop implementation and API enablement is refused.
Journal permission is only a recorded future permission; there is no journal
text trainer. Document exclusions are enforced by the permission predicate
required for any future collector. No collector currently reads excluded text.

Turning preference learning off ignores existing preferences and rejects new
votes; records remain until reset. Reset deletes active preferences, feedback
audit and shadow observations; it preserves documents, history and permissions.
Community permission is independent. Its revision counter invalidates pending
exports after revocation, including off→on toggles. Export requires review of the
exact preview hash, can be cancelled, expires in ten minutes and is one-use.
No HTTP upload client, background training or external dependency is introduced.

## Runtime, loading and failure

No accepted model/key is installed. API neural availability is therefore false;
settings cannot bypass it. Fixed architecture workers use CPU/two torch threads,
128 tokens and at most six passages (each input bounded). Missing files, bad
signature/hash/version, invalid scores, model crash, resource excess, concurrent
busy worker and timeout all preserve deterministic search.

Candidate inference uses a fresh hidden subprocess, a two-second killable wall
deadline and 256 MiB sampled peak-working-set ceiling on Windows. Memory sampling
is every 10 ms, **not a kernel hard allocation limit**; a transient overshoot is
possible. Other platforms fail closed until a limiter is verified. There is no
persistent worker, cancellation queue or model-swap daemon. Active requests keep
an immutable bundle reference; update/rollback never deletes previous bundles.

In the production profile unvalidated relation shadow is now OFF by default.
Explicit developer opt-in uses the same killable isolation; failure opens a
circuit until restart. An observed cold shadow worker exceeded its two-second
budget on this machine, so this implementation is not approved for interactive
production neural influence. Development direct shadow remains for reproducible
diagnostics. Disabled observability never invokes loading. Normal release startup
does not initialize either experimental model.

## Model releases and rollback

Bundles contain exactly manifest.json, weights.pt and tokenizer.json. Ed25519
verification uses application-pinned public keys; no private key or trust-on-first
use is allowed. Model size/hash, architecture, tokenizer, minimum app version,
dataset/code/environment/protocol provenance and independent acceptance metrics
are checked before loading. Rel-0 is explicitly refused as a relevance release.
torch.load uses weights_only=True; architecture code is fixed in the application.

ModelStore verifies an immutable staged copy, requires a health check, and only
then atomically switches its pointer. Previous bundles/pointer remain recoverable;
rollback re-verifies the signature and compatibility. Production trust keys and
model installation UI are deliberately unconfigured. The store is an offline
research/release foundation, not an automatic desktop update service.
