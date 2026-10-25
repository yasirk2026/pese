# Alpha.5 preservation checkpoint

The G1 engineering work was preserved on `codex/g1-recovery-hardening`, based on
`428a9e603d68d0f3d4ee7cbe344338eac9a70393` (the existing annotated
`v0.1.0-alpha.4` tag resolves to that commit). The official origin is
`https://github.com/yasirk2026/pese.git`; remote main and the historical tag were
checked without changing either.

The preceding mission recorded 403 Python passes, 13 host passes, successful
TypeScript/Next/WPF builds, native WebView2 acceptance and synthetic real Google
acceptance. See `g1-engineering-report.md` for the evidence and its limits.
Active-Brain integrity in the inaccessible account remains pending. Live Restore
remains disabled; separate-directory recovery is available.

The checkpoint includes source, tests, documentation and acceptance harnesses.
Ignored runtime builds, model checkpoints/caches, personal data, local profiles,
OAuth configuration/credentials and private logs remain outside Git. A private
SHA-256 inventory records the starting source state. A source credential scan
found no credential values. A hardcoded historical Brain ID in the Settings
fallback was removed, and a path-validation test uses a fictitious account name.

Alpha.5 updater engineering is developed separately from this checkpoint so
unaccepted recovery functionality cannot enter a bootstrap release incidentally.
