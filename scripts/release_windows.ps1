#requires -Version 7.2
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$BuildRoot,
    [Parameter(Mandatory)][string]$AssetSource,
    [Parameter(Mandatory)][string]$Dotnet,
    [Parameter(Mandatory)][string]$Vpk,
    [string]$NugetCache,
    [string]$Version = '0.1.0-alpha.5',
    [switch]$AcceptanceOnly
)
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -ge 7) { $PSNativeCommandUseErrorActionPreference = $false }
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$BuildRoot = [IO.Path]::GetFullPath($BuildRoot)
$AssetSource = [IO.Path]::GetFullPath($AssetSource)
if ($Version -notmatch '^\d+\.\d+\.\d+-alpha\.\d+$') { throw 'A valid alpha SemVer is required' }
if (Test-Path -LiteralPath $BuildRoot) { throw 'BuildRoot must be a new directory; earlier release artifacts are immutable' }
$python = Join-Path $AssetSource 'packaging/runtime-lab/python-embed/python.exe'
$notes = Join-Path $repo "docs/releases/$Version.md"
foreach ($file in @($python,$Dotnet,$Vpk,$notes)) { if (!(Test-Path -LiteralPath $file)) { throw "Missing prerequisite: $file" } }
function Assert-Exit([string]$Step) { if ($LASTEXITCODE -ne 0) { throw "$Step failed ($LASTEXITCODE)" } }
$mutexId = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($repo)))
$buildMutex = [Threading.Mutex]::new($false, "Local\PESE.ReleaseBuild.$mutexId")
if (!$buildMutex.WaitOne(0)) { $buildMutex.Dispose(); throw 'Another release build is using this checkout' }
Push-Location $repo
try {
    $commit = (& git -c "safe.directory=$($repo.Replace('\','/'))" rev-parse HEAD).Trim()
    Assert-Exit 'Source commit'
    $status = & git -c "safe.directory=$($repo.Replace('\','/'))" status --porcelain
    if ($status -and !$AcceptanceOnly) { throw 'Production build requires clean, committed source' }
    [xml]$project = Get-Content -LiteralPath host/PESE.Desktop/PESE.Desktop.csproj
    if ($project.Project.PropertyGroup.Version -ne $Version -and !$AcceptanceOnly) { throw 'Host source version differs from release version' }
    if ((& $Dotnet --version) -ne '10.0.402') { throw 'Pinned .NET SDK 10.0.402 is required' }
    $env:DOTNET_ROOT = Split-Path $Dotnet
    $env:DOTNET_ROLL_FORWARD = 'LatestMajor'
    $env:DOTNET_CLI_HOME = Join-Path $BuildRoot 'dotnet-home'
    $env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
    $env:DOTNET_GENERATE_ASPNET_CERTIFICATE = 'false'
    if ($NugetCache) { $env:NUGET_PACKAGES = $NugetCache }
    $vpkHelp = (& $Vpk --help) -join "`n"
    Assert-Exit 'Velopack CLI preflight'
    if ($vpkHelp -notmatch 'Velopack CLI 0\.0\.1298,') { throw 'Pinned Velopack CLI 0.0.1298 is required' }
    $stage = Join-Path $BuildRoot 'stage'
    $packages = Join-Path $BuildRoot 'artifacts'
    $logs = Join-Path $BuildRoot 'logs'
    New-Item -ItemType Directory -Path $stage,$packages,$logs | Out-Null
    # Tests must never resolve a real account's Brain or saved pointer.
    $env:LOCALAPPDATA = Join-Path $BuildRoot 'test-profile'
    $env:PESE_DATA_DIR = Join-Path $BuildRoot 'test-Brain'
    Remove-Item Env:PESE_BRAIN_PATH -ErrorAction SilentlyContinue
    $env:HF_HUB_OFFLINE = '1'
    $env:TRANSFORMERS_OFFLINE = '1'
    $env:PESE_FASTEMBED_CACHE = Join-Path $AssetSource 'packaging/runtime-lab/models/fastembed'
    $onnx = @(Get-ChildItem -LiteralPath $env:PESE_FASTEMBED_CACHE -Recurse -Filter model_optimized.onnx)
    if ($onnx.Count -ne 1) { throw 'Expected one pinned local ONNX model' }
    $env:PESE_FASTEMBED_MODEL_PATH = $onnx[0].DirectoryName
    & $python -B -c "import sys;sys.path.insert(0,sys.argv[1]);from engine.brain import initialize_brain;initialize_brain(sys.argv[2])" $repo $env:PESE_DATA_DIR
    Assert-Exit 'Disposable regression Brain'
    # Provision immutable model inputs for tests; they stay ignored by Git.
    New-Item -ItemType Directory -Force engine/neural/checkpoints,engine/data | Out-Null
    Copy-Item -Path (Join-Path $AssetSource 'engine/neural/checkpoints/*') -Destination engine/neural/checkpoints -Recurse -Force
    foreach ($name in @('neural_genesis_report.json','qa_experiment_report.json')) {
        Copy-Item -LiteralPath (Join-Path $AssetSource "engine/data/$name") -Destination "engine/data/$name" -Force
    }
    & $python -B -m pytest -q --basetemp (Join-Path $BuildRoot 'pytest') *> (Join-Path $logs 'python.log'); Assert-Exit 'Python tests'
    & $python -B -m pytest host/tests -q --basetemp (Join-Path $BuildRoot 'host-pytest') *> (Join-Path $logs 'host.log'); Assert-Exit 'Host tests'
    Push-Location web
    try {
        $env:NEXT_TELEMETRY_DISABLED = '1'
        & node node_modules/typescript/bin/tsc --noEmit --incremental false *> (Join-Path $logs 'typescript.log'); Assert-Exit 'TypeScript'
        & npm.cmd run build *> (Join-Path $logs 'frontend.log'); Assert-Exit 'Next production build'
    } finally { Pop-Location }
    & $Dotnet publish host/PESE.Desktop/PESE.Desktop.csproj -c Release -r win-x64 --self-contained true "-p:Version=$Version" -o $stage *> (Join-Path $logs 'publish.log'); Assert-Exit 'WPF publish'
    & $python -B scripts/stage_desktop.py $stage --asset-source $AssetSource *> (Join-Path $logs 'stage.log'); Assert-Exit 'Offline runtime staging'
    & (Join-Path $stage 'runtime/python/python.exe') -B -c 'import engine.api.main' *> (Join-Path $logs 'staged-import.log'); Assert-Exit 'Staged engine dependency import'
    $provenanceArgs = @('scripts/source_provenance.py',$stage,$Version)
    if ($AcceptanceOnly) { $provenanceArgs += '--acceptance-only' }
    & $python -B @provenanceArgs; Assert-Exit 'Source provenance'
    & $python -B scripts/audit_desktop_native.py $stage (Join-Path $logs 'native-audit.json'); Assert-Exit 'Native dependencies'
    & $Vpk pack --packId ManiacSoftwares.PESE --packVersion $Version --packDir $stage --mainExe PESE.exe --channel win --icon (Join-Path $stage 'pese.ico') --packTitle PESE --packAuthors 'Maniac Softwares' --runtime win-x64 --framework 'webview2,vcredist143-x64' --shortcuts 'Desktop,StartMenuRoot' --noPortable --delta None --releaseNotes $notes --outputDir $packages *> (Join-Path $logs 'pack.log'); Assert-Exit 'Velopack packaging'
    $setup = @(Get-ChildItem -LiteralPath $packages -Filter '*Setup.exe')
    if ($setup.Count -ne 1) { throw 'Expected one installer' }
    Move-Item -LiteralPath $setup[0].FullName -Destination (Join-Path $packages 'PESE-Setup.exe')
    $assetMap = Get-Content -LiteralPath (Join-Path $packages 'assets.win.json') -Raw | ConvertFrom-Json
    foreach ($asset in $assetMap) { if ($asset.Type -eq 'Installer') { $asset.RelativeFileName = 'PESE-Setup.exe' } }
    ConvertTo-Json -InputObject @($assetMap) | Set-Content -LiteralPath (Join-Path $packages 'assets.win.json') -Encoding utf8
    Copy-Item -LiteralPath $notes -Destination (Join-Path $packages 'release-notes.md')
    $verifyArgs = @('scripts/verify_release.py',$packages,$Version,$commit)
    if ($AcceptanceOnly) { $verifyArgs += '--acceptance-only' }
    & $python -B @verifyArgs; Assert-Exit 'Artifact verification'
    Write-Output "Verified artifacts: $packages"
} finally { Pop-Location; $buildMutex.ReleaseMutex(); $buildMutex.Dispose() }
