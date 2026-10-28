#requires -Version 7.2
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Stage,
    [Parameter(Mandatory)][string]$Artifacts,
    [Parameter(Mandatory)][string]$Dotnet,
    [Parameter(Mandatory)][string]$Vpk,
    [Parameter(Mandatory)][string]$NugetCache,
    [switch]$InstallerFixture
)
$ErrorActionPreference='Stop'
if ($InstallerFixture) { throw 'Use pack_installer_fixture.ps1 with -CanonicalArtifacts. Rebuilding frontend assets changes build IDs and cannot prove an identical installer payload.' }
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Stage=[IO.Path]::GetFullPath($Stage);$Artifacts=[IO.Path]::GetFullPath($Artifacts)
if (Test-Path -LiteralPath $Artifacts) { throw 'Fresh immutable artifact output required' }
if ($Stage.StartsWith($repo+'\',[StringComparison]::OrdinalIgnoreCase) -or $Artifacts.StartsWith($repo+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Use build directories outside source' }
$env:DOTNET_ROOT=Split-Path $Dotnet;$env:DOTNET_ROLL_FORWARD='LatestMajor'
$env:DOTNET_CLI_TELEMETRY_OPTOUT='1';$env:DOTNET_GENERATE_ASPNET_CERTIFICATE='false';$env:NUGET_PACKAGES=$NugetCache
if ((& $Dotnet --version) -ne '10.0.403') { throw 'Verified SDK 10.0.403 required' }
if (((& $Vpk --help) -join "`n") -notmatch 'Velopack CLI 0\.0\.1298,') { throw 'Pinned Velopack 0.0.1298 required' }
New-Item -ItemType Directory -Path $Artifacts | Out-Null
$env:DOTNET_CLI_HOME=Join-Path $Artifacts 'dotnet-home'
$env:TEMP=Join-Path $Artifacts 'temp';$env:TMP=$env:TEMP
New-Item -ItemType Directory -Path $env:TEMP | Out-Null
Push-Location $repo
try {
    $commit=(& git -c "safe.directory=$($repo.Replace('\','/'))" rev-parse HEAD).Trim()
    if (& git -c "safe.directory=$($repo.Replace('\','/'))" status --porcelain) { throw 'Clean committed build source required' }
    $python=Join-Path $Stage 'runtime/python/python.exe'
    foreach ($name in @('ui/neural-genesis/index.html','models','engine/neural/assets/basic_english_beta_v1/weights.pt')) {
        if (!(Test-Path -LiteralPath (Join-Path $Stage $name))) { throw "Incomplete prepared stage: $name" }
    }
    if (Get-ChildItem -LiteralPath $Stage -Recurse -Filter pese-brain.json) { throw 'Never package a Brain' }
    # Refresh source so an old staging directory cannot claim a newer commit.
    $refresh=@'
import sys,shutil,hashlib
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from scripts.stage_desktop import tracked_engine_sources
from engine.intelligence.beta.base_lock import BASE_FILES
stage=Path(sys.argv[1])
for source in tracked_engine_sources(root):
    relative=source.relative_to(root)
    if any(p in ('tests','.venv','__pycache__','private','demo_runtime') for p in relative.parts):continue
    target=stage/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
for name,expected in BASE_FILES.items():
    assert hashlib.sha256((stage/'engine/neural/assets/basic_english_beta_v1'/name).read_bytes()).hexdigest()==expected,'Frozen base changed'
'@
    & $python -B -c $refresh $Stage
    if ($LASTEXITCODE -ne 0) { throw 'Source refresh/base verification failed' }
    Push-Location web
    try {
        $env:NEXT_TELEMETRY_DISABLED='1'
        & node node_modules/typescript/bin/tsc --noEmit --incremental false *> (Join-Path $Artifacts 'typescript.log')
        if ($LASTEXITCODE -ne 0) { throw 'TypeScript verification failed' }
        & npm.cmd run build *> (Join-Path $Artifacts 'frontend.log')
        if ($LASTEXITCODE -ne 0) { throw 'Production frontend build failed' }
    } finally { Pop-Location }
    $ui=[IO.Path]::GetFullPath((Join-Path $Stage 'ui'))
    if (!$ui.StartsWith($Stage+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe UI staging destination' }
    Remove-Item -LiteralPath $ui -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $repo 'web/out') -Destination $ui -Recurse
    # The normal Alpha update uses an explicit build profile. Stable and the
    # separate Owner BETA defaults keep their original identities.
    & $Dotnet publish host/PESE.Desktop/PESE.Desktop.csproj --no-restore -c Release -r win-x64 --self-contained true '-p:NeuralChannel=aggressive_learning_beta' '-p:AppDistribution=standard_update_beta' '-p:Version=0.1.0-alpha.7' -o $Stage *> (Join-Path $Artifacts 'publish.log')
    if ($LASTEXITCODE -ne 0) { throw 'Native training-update publish failed' }
    & $python -B scripts/source_provenance.py $Stage 0.1.0-alpha.7
    if ($LASTEXITCODE -ne 0) { throw 'Clean source provenance failed' }
    & $python -B scripts/audit_desktop_native.py $Stage (Join-Path $Artifacts 'native-audit.json')
    if ($LASTEXITCODE -ne 0) { throw 'Native dependency audit failed' }
    $notes=Join-Path $repo 'docs/releases/0.1.0-alpha.7.md'
    $id='ManiacSoftwares.PESE'
    $shortcuts='Desktop,StartMenuRoot'
    & $Vpk pack --packId $id --packVersion 0.1.0-alpha.7 --packDir $Stage --mainExe PESE.exe --channel win --icon (Join-Path $Stage 'pese.ico') --packTitle PESE --packAuthors 'Maniac Softwares' --runtime win-x64 --framework 'webview2,vcredist143-x64' --shortcuts $shortcuts --noPortable --delta None --releaseNotes $notes --outputDir $Artifacts *> (Join-Path $Artifacts 'pack.log')
    if ($LASTEXITCODE -ne 0) { throw 'Velopack packaging failed' }
    $setup=@(Get-ChildItem -LiteralPath $Artifacts -Filter '*Setup.exe')
    if ($setup.Count -ne 1) { throw 'Exactly one installer required' }
    Move-Item -LiteralPath $setup[0].FullName -Destination (Join-Path $Artifacts 'PESE-Setup.exe')
    $map=Get-Content -LiteralPath (Join-Path $Artifacts 'assets.win.json') -Raw | ConvertFrom-Json
    foreach ($asset in $map) { if ($asset.Type -eq 'Installer') { $asset.RelativeFileName='PESE-Setup.exe' } }
    ConvertTo-Json -InputObject @($map) | Set-Content -LiteralPath (Join-Path $Artifacts 'assets.win.json') -Encoding utf8
    Copy-Item -LiteralPath $notes -Destination (Join-Path $Artifacts 'release-notes.md')
    & $python -B scripts/verify_release.py $Artifacts 0.1.0-alpha.7 $commit --training-update
    if ($LASTEXITCODE -ne 0) { throw 'Release artifact verification failed' }
} finally { Pop-Location }
