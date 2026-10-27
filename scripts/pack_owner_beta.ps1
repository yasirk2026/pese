#requires -Version 7.2
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Stage,
    [Parameter(Mandatory)][string]$Artifacts,
    [Parameter(Mandatory)][string]$Dotnet,
    [Parameter(Mandatory)][string]$Vpk,
    [Parameter(Mandatory)][string]$NugetCache,
    [Parameter(Mandatory)][string]$Version
)
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Stage = [IO.Path]::GetFullPath($Stage)
$Artifacts = [IO.Path]::GetFullPath($Artifacts)
if ($Version -notmatch '^0\.1\.0-beta\.\d+$') { throw 'Explicit Owner BETA version required' }
if (Test-Path -LiteralPath $Artifacts) { throw 'Artifact directory must be new' }
if ($Stage.StartsWith($repo + '\', [StringComparison]::OrdinalIgnoreCase) -or
    $Artifacts.StartsWith($repo + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Build outside checkout' }
foreach ($name in @('runtime/python/python.exe','models','ui/neural-genesis/index.html','engine/neural/assets/basic_english_beta_v1/weights.pt')) {
    if (!(Test-Path -LiteralPath (Join-Path $Stage $name))) { throw "Missing staged asset: $name" }
}
if (Get-ChildItem -LiteralPath $Stage -Recurse -Filter pese-brain.json) { throw 'A Brain must never be packaged' }
New-Item -ItemType Directory -Path $Artifacts | Out-Null
$packTemp = Join-Path $Artifacts 'temp'
New-Item -ItemType Directory -Path $packTemp | Out-Null
$env:TEMP = $packTemp
$env:TMP = $packTemp
$env:DOTNET_ROOT = Split-Path $Dotnet
$env:DOTNET_CLI_HOME = Join-Path (Split-Path $Artifacts) 'dotnet-home'
$env:DOTNET_ROLL_FORWARD = 'LatestMajor'
$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
$env:DOTNET_GENERATE_ASPNET_CERTIFICATE = 'false'
$env:NUGET_PACKAGES = $NugetCache
Push-Location $repo
try {
    # Refresh source bytes before stamping; an older staged runtime must not
    # claim provenance for a later privacy fix in the working tree.
    $refresh = @'
import os,sys,shutil
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from scripts.stage_desktop import tracked_engine_sources
stage=Path(sys.argv[1])
for source in tracked_engine_sources(root):
    relative=source.relative_to(root)
    if any(p in ('tests','.venv','__pycache__','private','demo_runtime') for p in relative.parts):continue
    target=stage/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
'@
    & (Join-Path $Stage 'runtime/python/python.exe') -B -c $refresh $Stage
    if ($LASTEXITCODE -ne 0) { throw 'Source refresh failed' }
    & $Dotnet publish host/PESE.Desktop/PESE.Desktop.csproj --no-restore -c Release -r win-x64 --self-contained true "-p:NeuralChannel=aggressive_learning_beta" "-p:Version=$Version" -o $Stage *> (Join-Path $Artifacts 'publish.log')
    if ($LASTEXITCODE -ne 0) { throw 'Owner BETA publish failed' }
    & (Join-Path $Stage 'runtime/python/python.exe') -B scripts/source_provenance.py $Stage $Version --acceptance-only
    if ($LASTEXITCODE -ne 0) { throw 'Source provenance failed' }
    $notes = Join-Path $Artifacts 'release-notes.md'
    "# PESE Owner BETA $Version`n`nLocal FIRST CONTACT acceptance. Owner activation requires an affirmative per-Brain agreement and explicit scope. Independent human English evaluation is pending. Stable PESE is preserved. No automatic external sharing or public BETA feed." | Set-Content -LiteralPath $notes -Encoding utf8
    & $Vpk pack --packId ManiacSoftwares.PESE.OwnerBeta --packVersion $Version --packDir $Stage --mainExe PESE.exe --channel win-owner-beta --icon (Join-Path $Stage 'pese.ico') --packTitle 'PESE Owner BETA' --packAuthors 'Maniac Softwares' --runtime win-x64 --framework 'webview2,vcredist143-x64' --shortcuts None --noPortable --delta None --releaseNotes $notes --outputDir $Artifacts *> (Join-Path $Artifacts 'pack.log')
    if ($LASTEXITCODE -ne 0) { throw 'Owner BETA packaging failed' }
    Get-ChildItem -LiteralPath $Artifacts -File | Where-Object { $_.Extension -in '.exe','.nupkg' } | ForEach-Object {
        $digest = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$digest  $($_.Name)"
    } | Set-Content -LiteralPath (Join-Path $Artifacts 'checksums.sha256')
} finally { Pop-Location }
