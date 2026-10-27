# Community intelligence v1: local export and quarantine

## Implemented boundary

The desktop can preview and download a deliberately small, closed-schema JSON
contract. v1 contains application/model versions and at most three coarse
diagnostic categories, with count buckets 5–9, 10–19, 20–49 or 50+. Counts below
five are suppressed. They come from consolidated active preferences, not audit
click volume, and are not relevance judgments. No free-text field is accepted.

The exact payload is shown before export. The preview initially says reviewed:
false. A hash-bound, one-use confirmation changes that to true. Cancel, expiry,
permission revocation and off→on consent revision changes invalidate old previews.
The destination is a **local file**, not Maniac Softwares or another server.
upload_authorized remains false. The app includes no network upload client.

Raw queries, private passages, journals, embeddings, model deltas, credentials,
Brain archives, device IDs and user IDs are not valid v1 fields. Per-example text
sharing is **unsupported**, even when someone adds an apparent consent field.
A future text-bearing contract needs its own source/publication permissions and
per-example recipient-specific review. Minimized aggregates are not guaranteed
anonymous; rare patterns, versions and later transport metadata may identify users.

`research/mock_intake.py` creates an in-process/loopback test app only when an
explicit test token is supplied. A separate test-review header simulates the
transport-consent boundary: a desktop local export alone is insufficient. This
header is not a production consent protocol. The mock rejects unauthenticated,
unreviewed, malformed, oversize (>16 KiB), unknown-version, unknown-field and
duplicate-category submissions. It rate limits a single test principal and caps
quarantine size. Exact packages deduplicate by canonical content hash. Every
accepted package remains quarantined and training_eligible:false.

The mock has explicit 30-day quarantine expiry/deletion tooling. It does not run
automatically, contact cloud storage or publish datasets. Bucketed diagnostics
cannot supply supervised labels. Contradictions, repeated evidence and cross-split
leakage are separately rejected by the offline reviewed-record curator. These
checks cannot detect every coordinated poisoner or dishonest reviewer.

## Threat model and responses

| Threat | Boundary/control | Remaining limit |
|---|---|---|
| Journal/query leakage | No text-bearing contribution fields; exact preview | Manual Drive Brain backup is a separate intentional transfer and includes private records |
| Embedding inversion or delta memorization | Neither embeddings nor local model deltas accepted | Future protocols need a new privacy analysis; stripping names is insufficient |
| Reidentification | No installation IDs, timestamps, paths or free text; count buckets | Transport IP and rare aggregate combinations may still identify a person |
| Unauthorized collection/sharing | New research permissions off, independent community permission, no uploader | Local JSON files shared outside PESE are under the user's control |
| Repeated fraudulent votes | Active-state counts, quarantine, deduplication, no label conversion | Multiple installations can coordinate; counts must never become truth |
| Poisoned labels | Trusted reviewer registry, receipt-bound labels, contradictions rejected | Reviewer integrity and meaningful group declarations require human governance |
| Malicious model artifacts | Pinned Ed25519 keys, hashes/sizes, exact file inventory, fixed code, weights_only, subprocess deadline | Signed provenance is an accountable release assertion, not proof of model quality |
| Compromised endpoint | No configured endpoint; future pinned HTTPS origin, short-lived capabilities, no redirects | A compromised recipient can retain data already received |
| Schema mismatch | Strict versions/fields, no inferred historical provenance | Legacy evidence remains preference/diagnostic only |
| Resource denial | 16 KiB streaming cap, mock rate/global quotas, bounded inference | Production ingress needs distributed limits and spend controls |

## Deployment-ready specification (not deployed)

An appropriate small-project topology is an HTTPS Worker ingress bound to a
**private** R2 quarantine bucket, followed by an offline/manual curation job.
Workers can access R2 through private bindings; public r2.dev access is unsuitable
for this intake. See [R2 Workers API](https://developers.cloudflare.com/r2/api/workers/workers-api-usage/)
and [R2 limits](https://developers.cloudflare.com/r2/platform/limits/). No cost or
capacity estimate is asserted without actual traffic and account configuration.

Required configuration before any external contribution can be enabled:

1. An owner-approved domain, account, storage region and responsible recipient;
   published purpose, retention period, contact and deletion procedure.
2. A new transport consent contract naming that exact origin/recipient, categories,
   text status, retention/model-improvement use, revocation and deletion limits.
   Local export permission alone never satisfies it.
3. Origin-bound short-lived upload capabilities issued by the gateway after
   abuse-resistant verification. No shared private ingestion secret is embedded
   in the desktop. Authentication/abuse metadata must have its own retention limit.
4. POST-only HTTPS, no redirects, content-type/version validation, 16 KiB streamed
   body cap including missing/false Content-Length, a deadline, distributed
   per-capability/global rate quotas and daily storage/spend ceilings.
5. Private quarantine objects addressed by canonical content digest. No public
   URLs, no request-body logs, no raw IP retention by application code. Review
   infrastructure/provider access logs independently and document their behavior.
6. Store received-at, validation/schema version, processing state and expiry
   separately from contribution content. Run expiry daily. Provide authenticated
   operational deletion by receipt hash and audit deletion outcomes without content.
7. Manual promotion only after provenance/privacy review; immutable curated
   manifests and disjoint train/validation/calibration/final-test families.
   Contributions are never passed straight into a trainer or release signer.
8. Independent evaluation and release review; Ed25519 signing key held offline
   or in a release-signing service, with app-pinned public-key rotation. The
   [Ed25519 verification contract](https://cryptography.io/en/stable/hazmat/primitives/asymmetric/ed25519/)
   is implemented with the already locked cryptography dependency.
9. End-to-end staging tests for consent revocation, expiry, quotas, malicious
   payloads, endpoint compromise and deletion; explicit user-visible deployment
   approval/configuration before adding a desktop uploader.

No infrastructure account, domain, signing key or recipient was configured for
this work. Google Drive OAuth assets are unrelated to this proposed intake and
were not repurposed. GitHub remains suitable for code/reviewed public artifacts,
not private user submissions. Normal offline PESE operation depends on none of
this infrastructure.
