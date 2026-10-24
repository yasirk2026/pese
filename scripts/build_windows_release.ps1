[CmdletBinding()]
param(
    [string]$BuildRoot = (Join-Path ([IO.Path]::GetTempPath()) 'PESE Desktop Build'),
    [string]$Dotnet = (Join-Path $PSScriptRoot '..\.tools\dotnet\dotnet.exe'),
    [string]$Vpk = (Join-Path $PSScriptRoot '..\.tools\vpk\vpk.exe'),
    [string]$NugetCache = '',
    [string]$Version = '0.1.0-alpha.3',
    [switch]$SkipVerifiedChecks
)
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$BuildRoot = [IO.Path]::GetFullPath($BuildRoot)
$release = Join-Path $repo "dist\windows\$Version"
$stage = Join-Path $BuildRoot "stage-$Version"
$packages = Join-Path $BuildRoot "packages-$Version"
$python = Join-Path $repo 'packaging\runtime-lab\python-embed\python.exe'
$fallbackDotnet = 'D:\PESE Desktop Build\2026-10-24\dotnet\dotnet.exe'
if (Test-Path -LiteralPath $fallbackDotnet) { $Dotnet = $fallbackDotnet }
if (!$NugetCache -and (Test-Path -LiteralPath 'D:\PESE Desktop Build\2026-10-24\nuget')) {
    $NugetCache = 'D:\PESE Desktop Build\2026-10-24\nuget'
}
foreach ($file in @($Dotnet, $Vpk, $python)) { if (!(Test-Path -LiteralPath $file)) { throw "Missing prerequisite: $file" } }
if ((& $Dotnet --version) -notlike '10.*') { throw '.NET 10 SDK is required' }
New-Item -ItemType Directory -Force -Path $BuildRoot,$release,$stage,$packages,(Join-Path $BuildRoot 'temp') | Out-Null
$env:DOTNET_ROOT = Split-Path $Dotnet
$env:DOTNET_CLI_HOME = Join-Path $BuildRoot 'dotnet-home'
$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
$env:DOTNET_ROLL_FORWARD = 'LatestMajor' # vpk 0.0.1298 targets net9; host remains net10.
if ($NugetCache) { $env:NUGET_PACKAGES = $NugetCache }
$env:TEMP = Join-Path $BuildRoot 'temp'
$env:TMP = $env:TEMP
$env:HF_HUB_OFFLINE = '1'
$env:PESE_FASTEMBED_CACHE = Join-Path $repo 'packaging\runtime-lab\models\fastembed'
$onnx = @(Get-ChildItem -LiteralPath $env:PESE_FASTEMBED_CACHE -Recurse -Filter 'model_optimized.onnx')
if ($onnx.Count -ne 1) { throw 'Expected one verified bundled ONNX model' }
$env:PESE_FASTEMBED_MODEL_PATH = $onnx[0].DirectoryName
$env:NEXT_TELEMETRY_DISABLED = '1'
function Assert-Exit([string]$Step) { if ($LASTEXITCODE -ne 0) { throw "$Step failed ($LASTEXITCODE)" } }
Push-Location $repo
try {
    if (!$SkipVerifiedChecks) {
        & $python -m pytest -q --basetemp (Join-Path $BuildRoot ('pytest-' + [guid]::NewGuid().ToString('N'))) 2>&1 | Tee-Object (Join-Path $release 'python-tests.log')
        Assert-Exit 'Python regression'
        & $python -m pytest host\tests -q --basetemp (Join-Path $BuildRoot ('host-tests-' + [guid]::NewGuid().ToString('N'))) 2>&1 | Tee-Object (Join-Path $release 'host-tests.log')
        Assert-Exit 'Desktop boundary tests'
        Push-Location web
        try { & npm.cmd run build 2>&1 | Tee-Object (Join-Path $release 'frontend-build.log'); Assert-Exit 'Static frontend build' }
        finally { Pop-Location }
    }
    $routes = Get-Content 'web\.next\server\app-paths-manifest.json' -Raw | ConvertFrom-Json
    if ($routes.PSObject.Properties.Name | Where-Object { $_ -match '\[' }) { throw 'Dynamic frontend routes cannot ship' }
    foreach ($route in @('index.html','search\index.html','doc\index.html','settings\index.html','admin\index.html','admin\new\index.html','admin\edit\index.html','admin\eval\index.html','admin\neural-lab\index.html')) {
        if (!(Test-Path (Join-Path 'web\out' $route))) { throw "Static route missing: $route" }
    }
    & $Dotnet publish host\PESE.Desktop\PESE.Desktop.csproj -c Release -r win-x64 --self-contained true -o $stage 2>&1 | Tee-Object (Join-Path $release 'host-publish.log')
    Assert-Exit 'Self-contained .NET 10 publish'
    & $python scripts\stage_desktop.py $stage; Assert-Exit 'Application staging'
    $vc = Join-Path $BuildRoot 'prerequisites\VC_redist.x64.exe'
    if (!(Test-Path -LiteralPath $vc)) {
        New-Item -ItemType Directory -Force (Split-Path $vc) | Out-Null
        Invoke-WebRequest 'https://aka.ms/vc14/vc_redist.x64.exe' -OutFile $vc
    }
    if ((Get-AuthenticodeSignature -LiteralPath $vc).Status -ne 'Valid') { throw 'VC++ prerequisite signature is not valid' }
    New-Item -ItemType Directory -Force (Join-Path $stage 'prerequisites') | Out-Null
    Copy-Item -LiteralPath $vc -Destination (Join-Path $stage 'prerequisites\VC_redist.x64.exe') -Force
    & $python scripts\audit_desktop_native.py $stage (Join-Path $release 'native-crt-audit.json')
    Assert-Exit 'Native CRT dependency audit'
    & $Vpk pack --packId ManiacSoftwares.PESE --packVersion $Version --packDir $stage --mainExe PESE.exe --icon (Join-Path $stage 'pese.ico') --packTitle PESE --packAuthors 'Maniac Softwares' --runtime win-x64 --framework 'webview2,vcredist143-x64' --shortcuts 'Desktop,StartMenuRoot' --noPortable --delta None --outputDir $packages 2>&1 | Tee-Object (Join-Path $release 'installer-build.log')
    Assert-Exit 'Velopack installer packaging'
    $setup = @(Get-ChildItem -LiteralPath $packages -Filter '*Setup.exe')
    if ($setup.Count -ne 1) { throw 'Expected exactly one setup executable' }
    Copy-Item -LiteralPath $setup[0].FullName -Destination (Join-Path $release 'PESE-Setup.exe') -Force
    $releasePackages = Join-Path $release 'packages'
    New-Item -ItemType Directory -Force -Path $releasePackages | Out-Null
    Get-ChildItem -LiteralPath $packages -File | Where-Object { $_.Extension -ne '.exe' } | Copy-Item -Destination $releasePackages -Force
    $installer = Get-Item (Join-Path $release 'PESE-Setup.exe')
    $hash = (Get-FileHash -LiteralPath $installer.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  PESE-Setup.exe" | Set-Content (Join-Path $release 'checksums.sha256')
    @{ version=$Version; architecture='win-x64'; signed=$false; installer=$installer.FullName; bytes=$installer.Length; sha256=$hash; packages=$packages; stage=$stage } | ConvertTo-Json | Set-Content (Join-Path $release 'release-artifacts.json')
    Write-Output "Installer: $($installer.FullName)"
} finally { Pop-Location }
