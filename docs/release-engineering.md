# Windows release engineering

PESE is offline first. Search and the Brain work locally; native update checks use
GitHub when requested/available. Later Google backup builds have their own explicit
opt-in networking. Neither path makes the Brain an installation asset.

## Pinned toolchain and offline assets

Windows 10/11 x64, .NET SDK **10.0.402**, self-contained .NET 10 WPF, embedded
CPython **3.12.10**, WebView2 package **1.0.3650.58**, Velopack SDK/CLI
**0.0.1298**. Python distributions are pinned in `requirements.lock.txt`; frontend
dependencies are pinned by `web/package-lock.json` (`npm ci`). The Evergreen
WebView2 runtime and VC++ x64 redistributable are installation prerequisites.

Model/runtime binaries remain external to Git. A fresh checkout can obtain the
existing public Alpha.4 full package from the official release and run:

```powershell
python scripts/provision_release_assets.py <alpha4-full.nupkg> <new-offline-assets-directory>
cd web
npm ci
cd ..
```

The provisioner requires the pinned public package SHA-256 and extracts only the
runtime, models, base checkpoints and two product model reports. It imports no
Brain, settings, credentials or application source. Do not substitute a personal
Brain or a mutable model cache for these inputs.

## Deliberate build

Commit reviewed source first. Use a **new** build directory outside the checkout
so disposable regression Brains are separate from application source. Run:

```powershell
./scripts/release_windows.ps1 -Version 0.1.0-alpha.5 `
  -BuildRoot <new-build-directory> -AssetSource <offline-assets-directory> `
  -Dotnet <dotnet-10.0.402.exe> -Vpk <vpk-0.0.1298.exe> -NugetCache <optional-cache>
```

The build always runs Python, host, TypeScript and Next checks, publishes WPF,
stages the isolated runtime, stamps the exact commit, embeds version-specific
Markdown notes, packages, checks package/feed identity and SHA-256, rejects known
private Brain files and writes checksums plus a public provenance manifest.
`-AcceptanceOnly` permits experimental source but marks the package unpublishable.
No build command publishes automatically. The historical `build_windows_release`
script is retained for Alpha.4 history; use `release_windows` for new releases.

After two exact-package native acceptance reports pass (default and custom
Unicode paths, including the actual WPF Settings controls), publication is a
separate deliberate command:

```powershell
./scripts/publish_windows_release.ps1 -Artifacts <verified-artifact-directory> `
  -Gh <official-gh.exe> -AcceptanceReports <default-acceptance.json>,<ui-acceptance.json>
# Review the successful gate output, then repeat the same command with -Publish.
```

It refuses dirty/mismatched source, existing tags/releases, unpublishable test
packages, changed artifacts or unrelated update evidence. It integrates source
with a normal fast-forward push, creates an annotated tag and draft prerelease,
uploads the complete artifacts, downloads and compares all draft bytes, and only
then makes the prerelease public. Anonymous asset availability is checked and a
local publication receipt is written. It never force-pushes or replaces assets.

## Update protocol

Preserve package ID `ManiacSoftwares.PESE`, main executable `PESE.exe`, channel
`win` and `releases.win.json`. The product presents this as the alpha channel:
GitHub prereleases are explicitly enabled. The cache directory is never a
production update feed. Release notes come from the target Velopack package.

Settings sends fixed commands over WebView2's native bridge. The host verifies
the message/document origin, serializes operations, downloads/checks packages
through Velopack and rechecks SHA-256 before activation. New engine operations
are rejected during shutdown; Uvicorn drains existing requests. A clean engine
exit is mandatory. The updater then waits for a normal host exit and restarts.
The new launch's native version is the evidence of success.
Velopack's default startup auto-apply is explicitly disabled: a second launch
cannot activate a cached update before the single-instance gate or engine drain.
Appearance/developer choices live in the user's `ui-preferences.json`, separately
from `desktop-settings.json`. They no longer depend on the temporary engine port.
Privacy, profile, feedback and documents remain in the selected Brain. The native
update UI acceptance chooses a nondefault appearance and verifies the updated
loader reads the same preference after the origin changes.

Successful validated index generations atomically checkpoint only the local
content-hashed vector cache. Interrupted writes leave the previous cache intact.
The host displays progress during a bounded 15-minute cache-free startup and
waits for both the completed lifecycle signal and a healthy authenticated API.
No vector cache is part of Google snapshots; G1 transfer/recovery remains separate.

## Local acceptance and account safety

Use a new marked disposable case containing `install/`, `feed/`, a separate Brain
and `LocalAppData/`. A Windows Velopack portable installation has a root
`.portable` marker; the pinned updater skips uninstall-registry and shortcut
modification for this supported mode. This avoids colliding with the owner's
installed package ID while exercising real package download, activation and
restart. `UpdateAcceptance` requires the fixture marker, checks every path,
uses isolated account settings and verifies canonical hashes/pointer after the
restarted binary runs. Its successful pre-handoff report alone is insufficient:
the matching successful `update-after.json` is required.

Test a default fixture Brain and a separate path containing spaces/Unicode;
retain feedback/profile/privacy data. Exercise two increasing versions, active
search at shutdown, duplicate attempts, offline/unavailable/corrupt packages and
an interrupted download. Keep evidence private if it contains local paths.

Alpha.4 selects its existing local package cache and excludes GitHub prereleases
in its fallback. It therefore needs a **one-time Alpha.5 installer transition**.
Do not call that an in-app Alpha.4 upgrade. Once bootstrapped, later releases use
Settings → Updates → Download → Update and restart.

For each real account, before a deliberate installer/update, close PESE and record
the saved pointer hash, Brain ID/schema/document count, canonical hashes, feedback
counts, installation root/version/ownership and independent credentials presence.
Never print credential contents. After restart verify the same pointer/identity,
counts, feedback/profile/privacy, grounded search and the new native version.
Run this in each account's owning Windows context. Do not take ownership or
alter ACLs. Updating one per-user copy does not update another account's copy.

## Publication gate

Publication requires a clean exact source commit, the complete matching artifact
set, all checks passing, native installed-product acceptance, real successful
update/restart with preserved fixture data and a second increasing-version test.
Do not tag or publish a candidate that fails these gates. Verify existing remote
tags/releases before publishing, never replace Alpha.4 or a published asset, and
verify public download hashes after upload. Use deliberate GitHub CLI/API actions
with the owner's authenticated account; do not put tokens into source or logs.

The binaries are unsigned unless a real signing certificate is supplied. A
recorded hash establishes artifact consistency, not publisher identity or
SmartScreen trust. Document account acceptance and signing limitations honestly.
