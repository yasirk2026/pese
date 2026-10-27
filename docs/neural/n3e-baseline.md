# N3-E baseline, 27 October 2026

Initial revision `2f6cd18`, branch `codex/g1-recovery-hardening`, clean working tree.
Read the N3 report/contracts and inspected ranking, receipts, privacy, snapshot,
model verification/isolation, trainer/metrics and Windows host/launcher code.
No private Brain was accessed. The new `../n3e-work/baseline` fixture reproduced
**464 passed**, zero failures/errors/skips (34.43 seconds), using existing local
CPU Python/BGE assets and blocked external test networking.

Actual flow remains hybrid retrieval → hard evidence admission → MAAE base →
optional bounded neural delta → existing bounded preference → sort → deterministic
answer grounding. Production model keys remain empty. The current relevance
trainer is development-only; no active Rel-1, local queue, job scheduler, journal
trainer or model evolution dashboard exists. The settings record journal consent
only and reject research collection. Snapshot schema/allowlists exclude the
intelligence sidecar and must remain unchanged.

N3-E will add a separate `aggressive_learning_beta` contract. It will not change
stable signing criteria or interpret votes/model confidence as truth. Development
labels will be explicit synthetic specification labels; external human-reviewed
acceptance is not available and will not be claimed. Any owner-private session
requires separate installed acceptance, affirmative UI participation and a
recoverable backup. Experiments here use disposable synthetic Brains only.

The bundled SDK was incomplete. A separate Microsoft .NET 10 SDK is being restored
under the new test workspace using official release metadata and SHA-512 checking;
no existing install or SDK is overwritten. Native acceptance is not yet a pass.
