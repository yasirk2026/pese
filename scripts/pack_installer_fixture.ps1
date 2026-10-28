#requires -Version 7.2
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Stage,
    [Parameter(Mandatory)][string]$CanonicalArtifacts,
    [Parameter(Mandatory)][string]$Artifacts,
    [Parameter(Mandatory)][string]$Dotnet,
    [Parameter(Mandatory)][string]$Vpk
)
$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Stage=[IO.Path]::GetFullPath($Stage);$Artifacts=[IO.Path]::GetFullPath($Artifacts)
$CanonicalArtifacts=[IO.Path]::GetFullPath($CanonicalArtifacts)
if (Test-Path -LiteralPath $Artifacts) {throw 'Fresh fixture output required; earlier evidence is immutable'}
if ($Stage.StartsWith($repo+'\',[StringComparison]::OrdinalIgnoreCase) -or $Artifacts.StartsWith($repo+'\',[StringComparison]::OrdinalIgnoreCase) -or $Artifacts.StartsWith($Stage+'\',[StringComparison]::OrdinalIgnoreCase) -or $Stage.StartsWith($Artifacts+'\',[StringComparison]::OrdinalIgnoreCase)) {throw 'Use separate prepared-stage and artifact folders outside source'}
if ((Split-Path $Stage -Leaf) -eq 'current' -or (Test-Path -LiteralPath (Join-Path (Split-Path $Stage) 'Update.exe'))) {throw 'Never modify an installed application as a fixture stage'}
$manifest=Get-Content -LiteralPath (Join-Path $CanonicalArtifacts 'release-manifest.json') -Raw | ConvertFrom-Json
if ($manifest.package_id -ne 'ManiacSoftwares.PESE' -or $manifest.channel -ne 'win' -or $manifest.acceptance_only -or $manifest.version -notmatch '^\d+\.\d+\.\d+-alpha\.\d+$') {throw 'Verified normal release artifacts required'}
$full=@($manifest.artifacts.PSObject.Properties | Where-Object {$_.Name.EndsWith('-full.nupkg')})
if ($full.Count -ne 1 -or [IO.Path]::GetFileName($full[0].Name) -ne $full[0].Name) {throw 'One safe canonical package required'}
$package=Join-Path $CanonicalArtifacts $full[0].Name
if ((Get-FileHash -LiteralPath $package -Algorithm SHA256).Hash.ToLowerInvariant() -ne $full[0].Value) {throw 'Canonical release changed'}
$python=Join-Path $Stage 'runtime/python/python.exe'
if (!(Test-Path -LiteralPath $python)) {throw 'Prepared offline release stage required'}
Push-Location $repo
try {
    & $python -B scripts/verify_release.py $CanonicalArtifacts $manifest.version $manifest.commit --training-update
    if ($LASTEXITCODE) {throw 'Canonical release verification failed'}
    # Reuse sealed build outputs. Never rerun Next or native publish here: even
    # the same source can produce different frontend build IDs.
    $restore=@'
import sys,zipfile,shutil,json
from pathlib import Path
package=Path(sys.argv[1]);stage=Path(sys.argv[2]).resolve()
assert not (stage/'pese-brain.json').exists()
ui=stage/'ui';assert ui.resolve().is_relative_to(stage) and not ui.is_symlink()
shutil.rmtree(ui)
copied=0
with zipfile.ZipFile(package) as z:
 for n in z.namelist():
  if not n.startswith('lib/app/') or n.endswith('/'):continue
  relative=n.removeprefix('lib/app/')
  if not relative.startswith('ui/') and relative not in ('PESE.exe','PESE.dll','PESE.pdb','source-provenance.json'):continue
  target=(stage/relative).resolve();assert target.is_relative_to(stage)
  target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(n));copied+=1
print(json.dumps({'canonical_build_files_restored':copied,'full_final_payload_comparison_required':True}))
'@
    & $python -B -c $restore $package $Stage
    if ($LASTEXITCODE) {throw 'Canonical build-output restore failed'}
    New-Item -ItemType Directory -Path $Artifacts | Out-Null
    $env:DOTNET_ROOT=Split-Path $Dotnet;$env:DOTNET_ROLL_FORWARD='LatestMajor'
    if (((& $Vpk --help) -join "`n") -notmatch 'Velopack CLI 0\.0\.1298,') {throw 'Pinned Velopack 0.0.1298 required'}
    $env:TEMP=Join-Path $Artifacts 'temp';$env:TMP=$env:TEMP
    New-Item -ItemType Directory -Path $env:TEMP | Out-Null
    $notes=Join-Path $CanonicalArtifacts 'release-notes.md'
    & $Vpk pack --packId ManiacSoftwares.PESE.AcceptanceOnly --packVersion $manifest.version --packDir $Stage --mainExe PESE.exe --channel win --icon (Join-Path $Stage 'pese.ico') --packTitle PESE --packAuthors 'Maniac Softwares' --runtime win-x64 --framework 'webview2,vcredist143-x64' --shortcuts None --noPortable --delta None --releaseNotes $notes --outputDir $Artifacts *> (Join-Path $Artifacts 'pack.log')
    if ($LASTEXITCODE) {throw 'Exact-payload fixture packaging failed'}
    $setup=@(Get-ChildItem -LiteralPath $Artifacts -Filter '*Setup.exe')
    if ($setup.Count -ne 1) {throw 'One Setup required'}
    Move-Item -LiteralPath $setup[0].FullName -Destination (Join-Path $Artifacts 'PESE-Setup.exe')
    @{acceptance_only=$true;package_id='ManiacSoftwares.PESE.AcceptanceOnly';compiled_package_id='ManiacSoftwares.PESE';source_commit=$manifest.commit;normal_package_sha256=$full[0].Value;purpose='Actual Setup with canonical release application bytes and separate registration'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Artifacts 'fixture-only.json')
    & $python -B scripts/accept_training_update_install.py $CanonicalArtifacts $Artifacts (Join-Path $Artifacts 'unused-payload-verification-case') --verify-payload-only *> (Join-Path $Artifacts 'payload-verification.json')
    if ($LASTEXITCODE) {throw 'Fixture application bytes or registration manifest differ unexpectedly'}
} finally {Pop-Location}
