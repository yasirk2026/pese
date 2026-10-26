#requires -Version 7.2
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Artifacts,
    [Parameter(Mandatory)][string]$Gh,
    [Parameter(Mandatory)][string[]]$AcceptanceReports,
    [switch]$Publish
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Artifacts = [IO.Path]::GetFullPath($Artifacts)
$manifest = Get-Content -LiteralPath (Join-Path $Artifacts 'release-manifest.json') -Raw | ConvertFrom-Json
function Assert-Exit([string]$step) { if ($LASTEXITCODE -ne 0) { throw "$step failed ($LASTEXITCODE)" } }
if ($manifest.repository -ne 'yasirk2026/pese' -or $manifest.package_id -ne 'ManiacSoftwares.PESE' -or
    $manifest.channel -ne 'win' -or !$manifest.prerelease -or $manifest.acceptance_only) { throw 'Unpublishable manifest identity or acceptance-only package' }
if ($manifest.version -notmatch '^\d+\.\d+\.\d+-alpha\.\d+$' -or $manifest.tag -ne "v$($manifest.version)" -or
    $manifest.commit -notmatch '^[a-f0-9]{40}$') { throw 'Invalid release version or source commit' }
$full = @($manifest.artifacts.PSObject.Properties | Where-Object { $_.Name.EndsWith('-full.nupkg') })
if ($full.Count -ne 1) { throw 'Exactly one full update package is required' }
$reports = @($AcceptanceReports | ForEach-Object { Get-Content -LiteralPath $_ -Raw | ConvertFrom-Json })
if ($reports.Count -lt 2 -or !($reports | Where-Object { $_.native_ui }) -or !($reports | Where-Object { $_.unicode_path }) -or
    !($reports | Where-Object { !$_.unicode_path }) -or !($reports | Where-Object { $_.interrupted_update_recovered }) -or
    !($reports | Where-Object { $_.download_faults_checked })) {
    throw 'Real native updates in separate default/custom Unicode fixtures, including WPF UI, are required'
}
foreach ($report in $reports) {
    $outbound = $report.base_version -eq $manifest.version -and $report.base_commit -eq $manifest.commit -and
        $report.base_package_sha256 -eq $full[0].Value -and
        [System.Management.Automation.SemanticVersion]$report.target -gt [System.Management.Automation.SemanticVersion]$manifest.version
    $inbound = $report.target -eq $manifest.version -and $report.target_commit -eq $manifest.commit -and
        $report.target_package_sha256 -eq $full[0].Value -and $report.target_acceptance_only -eq $false -and
        [System.Management.Automation.SemanticVersion]$report.base_version -lt [System.Management.Automation.SemanticVersion]$manifest.version
    if (!$report.passed -or !$report.real_native_update -or !$report.real_restart -or !$report.synthetic_data_only -or
        !$report.canonical_and_pointer_preserved -or !$report.account_sentinel_preserved -or
        !($outbound -or $inbound)) {
        throw 'Native update evidence does not match this exact release artifact'
    }
}
$files = @($manifest.artifacts.PSObject.Properties.Name) + @('checksums.sha256','release-manifest.json')
foreach ($name in $files) {
    if ([IO.Path]::GetFileName($name) -ne $name) { throw 'Unsafe artifact filename' }
    $path = Join-Path $Artifacts $name
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing artifact: $name" }
    $expected = $manifest.artifacts.PSObject.Properties[$name]
    if ($expected -and (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected.Value) {
        throw "Artifact changed after verification: $name"
    }
}
$previousPublisherPath = $env:PATH
Push-Location $repo
try {
    $git = @('-c',"safe.directory=$($repo.Replace('\','/'))",'-c','credential.helper=','-c','credential.helper=!gh auth git-credential')
    $env:PATH = (Split-Path $Gh) + [IO.Path]::PathSeparator + $env:PATH
    $head = (& git @git rev-parse HEAD).Trim(); Assert-Exit 'Source HEAD'
    if ($head -ne $manifest.commit -or (& git @git status --porcelain)) { throw 'Publication requires the clean exact build source checkout' }
    $remote = (& git @git remote get-url origin).Trim()
    if ($remote -notmatch '^https://(?:[^/@]+@)?github\.com/yasirk2026/pese(?:\.git)?$') { throw 'Wrong official origin' }
    & $Gh repo view yasirk2026/pese --json nameWithOwner,viewerPermission; Assert-Exit 'GitHub authorization'
    $existing = & $Gh release view $manifest.tag --repo yasirk2026/pese --json tagName 2>$null
    if ($LASTEXITCODE -eq 0) { throw 'Release already exists; never overwrite an existing release or its assets' }
    $remoteTag = & git @git ls-remote origin "refs/tags/$($manifest.tag)"; Assert-Exit 'Remote tag check'
    if ($remoteTag -or (& git @git tag --list $manifest.tag)) { throw 'Release tag already exists; investigate rather than replacing it' }
    & git @git fetch origin main; Assert-Exit 'Refresh release branch'
    & git @git merge-base --is-ancestor origin/main $manifest.commit; Assert-Exit 'Fast-forward source integration'
    if (!$Publish) { Write-Output 'Publication gates passed. Re-run with -Publish for deliberate publication.'; return }
    # No force option; protected branches or a concurrent source update stop this operation.
    & git @git push origin 'HEAD:main'; Assert-Exit 'Official source integration'
    & git @git tag -a $manifest.tag $manifest.commit -m "PESE $($manifest.version) verified Windows release"; Assert-Exit 'Annotated release tag'
    & git @git push origin "refs/tags/$($manifest.tag)"; Assert-Exit 'Release tag publication'
    $paths = @($files | ForEach-Object { Join-Path $Artifacts $_ })
    $displayName = 'PESE Alpha ' + ($manifest.version -split '\.')[-1]
    & $Gh release create $manifest.tag @paths --repo yasirk2026/pese --verify-tag --draft --prerelease --title $displayName --notes-file (Join-Path $Artifacts 'release-notes.md'); Assert-Exit 'Draft release upload'
    $verifyDir = Join-Path (Split-Path $Artifacts) ('github-verification-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $verifyDir | Out-Null
    & $Gh release download $manifest.tag --repo yasirk2026/pese --dir $verifyDir; Assert-Exit 'Draft asset download verification'
    foreach ($name in $files) {
        if ((Get-FileHash -LiteralPath (Join-Path $verifyDir $name) -Algorithm SHA256).Hash -ne
            (Get-FileHash -LiteralPath (Join-Path $Artifacts $name) -Algorithm SHA256).Hash) { throw "GitHub asset hash mismatch: $name" }
    }
    & $Gh release edit $manifest.tag --repo yasirk2026/pese --draft=false --prerelease --latest=false; Assert-Exit 'Prerelease publication'
    $release = & $Gh api "repos/yasirk2026/pese/releases/tags/$($manifest.tag)" | ConvertFrom-Json
    Assert-Exit 'Published release metadata'
    if ($release.draft -or !$release.prerelease -or $release.tag_name -ne $manifest.tag) { throw 'Published release metadata mismatch' }
    foreach ($asset in $release.assets) {
        $response = Invoke-WebRequest -Method Head -Uri $asset.browser_download_url -TimeoutSec 60
        if ($response.StatusCode -ne 200) { throw "Published asset unavailable: $($asset.name)" }
    }
    $receipt = @{ tag=$manifest.tag; commit=$manifest.commit; url=$release.html_url; draft=$false; prerelease=$true;
        all_asset_hashes_verified=$true; anonymous_asset_availability_verified=$true; signed=$false }
    $receipt | ConvertTo-Json | Set-Content -LiteralPath (Join-Path (Split-Path $Artifacts) 'publication-receipt.json') -Encoding utf8
    Write-Output $release.html_url
} finally { Pop-Location; $env:PATH = $previousPublisherPath }
