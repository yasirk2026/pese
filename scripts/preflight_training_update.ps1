#requires -Version 7.2
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Stage,
    [Parameter(Mandatory)][string]$Output,
    [Parameter(Mandatory)][string]$Dotnet,
    [Parameter(Mandatory)][string]$NugetCache
)
$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Stage=[IO.Path]::GetFullPath($Stage);$Output=[IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $Output) { throw 'Preflight output must be fresh' }
if ($Stage.StartsWith($repo+'\',[StringComparison]::OrdinalIgnoreCase) -or $Output.StartsWith($repo+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Use isolated directories outside checkout' }
New-Item -ItemType Directory -Path $Output | Out-Null
$env:DOTNET_ROOT=Split-Path $Dotnet;$env:DOTNET_CLI_HOME=Join-Path $Output 'dotnet-home'
$env:NUGET_PACKAGES=$NugetCache;$env:DOTNET_CLI_TELEMETRY_OPTOUT='1';$env:DOTNET_GENERATE_ASPNET_CERTIFICATE='false'
$env:NEXT_TELEMETRY_DISABLED='1'
Push-Location $repo
try {
    $refresh=@'
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
    $python=Join-Path $Stage 'runtime/python/python.exe'
    & $python -B -c $refresh $Stage
    if ($LASTEXITCODE -ne 0) { throw 'Source refresh failed' }
    $ui=[IO.Path]::GetFullPath((Join-Path $Stage 'ui'))
    if (!$ui.StartsWith($Stage+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe UI staging path' }
    if (Test-Path -LiteralPath $ui) { Remove-Item -LiteralPath $ui -Recurse -Force }
    Copy-Item -LiteralPath (Join-Path $repo 'web/out') -Destination $ui -Recurse
    & $Dotnet publish host/PESE.Desktop/PESE.Desktop.csproj --no-restore -c Release -r win-x64 --self-contained true '-p:NeuralChannel=aggressive_learning_beta' '-p:AppDistribution=standard_update_beta' '-p:Version=0.1.0-alpha.7' -o $Stage *> (Join-Path $Output 'publish.log')
    if ($LASTEXITCODE -ne 0) { throw 'Native publish failed' }
    & $python -B scripts/source_provenance.py $Stage 0.1.0-alpha.7 --acceptance-only
    if ($LASTEXITCODE -ne 0) { throw 'Source provenance failed' }
    foreach ($case in @(@{name='decline-200';size=200;decision='decline'},@{name='accept-200';size=200;decision='accept'},@{name='accept-400';size=400;decision='accept'})) {
        $brain=Join-Path $Output ($case.name+'-Brain');$receipt=Join-Path $Output $case.name
        & $python -B scripts/create_n3e_fixture.py $brain --count $case.size
        if ($LASTEXITCODE -ne 0) { throw 'Synthetic fixture creation failed' }
        $arguments=@('--accept-training-startup',('"'+$brain+'"'),('"'+$receipt+'"'),$case.decision)
        $process=Start-Process -FilePath (Join-Path $Stage 'PESE.exe') -ArgumentList $arguments -WorkingDirectory $Stage -WindowStyle Hidden -PassThru -Wait
        if ($process.ExitCode -ne 0) { throw "Native startup case failed: $($case.name); inspect retained receipt" }
    }
    $brain=Join-Path $Output 'ranking-200-Brain';$receipt=Join-Path $Output 'ranking-200'
    & $python -B scripts/create_n3e_fixture.py $brain --count 200
    if ($LASTEXITCODE -ne 0) { throw 'Ranking fixture creation failed' }
    $process=Start-Process -FilePath (Join-Path $Stage 'PESE.exe') -ArgumentList @('--accept-neural-beta',('"'+$brain+'"'),('"'+$receipt+'"')) -WorkingDirectory $Stage -WindowStyle Hidden -PassThru -Wait
    if ($process.ExitCode -ne 0) { throw 'Native 200-document ranking case failed; inspect retained receipt' }
} finally { Pop-Location }
