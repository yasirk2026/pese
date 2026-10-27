"""Exact, versioned closed-BETA agreement. No acceptance inferred from settings."""
from ..evidence import digest

AGREEMENT={"version":1,"title":"PESE NEURAL GENESIS: AGGRESSIVE LEARNING BETA",
 "statements":[
  "Neural ranking is experimental and may be worse than deterministic MAAE.",
  "Eligible searches, feedback and exact result receipts are retained locally for selective learning for up to 30 days by default.",
  "Passage text is collected only for document IDs you explicitly include. Excluded documents are not used for experimental learning.",
  "Notes and journals require their own explicit document scope and journal permission; generated questions are review candidates, never automatic truth labels.",
  "Feedback is validated and human-reviewed before trusted local training. Model confidence cannot certify its own labels.",
  "Candidate models may train on this device with bounded CPU, memory and disk use. Jobs can be cancelled; active weights are never changed in place.",
  "Local model versions may change only after evaluation. Official production signing trust is separate.",
  "You can pause learning, switch to MAAE, roll back, decline or exit this BETA. Documents remain unchanged.",
  "Exit stops future experimental collection and training. Existing local observations and private checkpoints remain until retention expiry or explicit deletion.",
  "Deleting experimental learning data removes its queue, jobs and private checkpoints; it does not remove documents, existing Search Sync votes or previously created backups.",
  "Research sidecars and private checkpoints are excluded from Drive snapshots. Ordinary manual Brain backups still include documents, saved history and canonical feedback.",
  "Private text, queries, embeddings, checkpoints and weight updates are never automatically sent to Maniac Softwares. External sharing requires separate consent.",
  "Owner-private BETA use requires separate native desktop acceptance and a recoverable backup; automated development uses synthetic Brains only."
 ]}
AGREEMENT_HASH=digest(AGREEMENT)
