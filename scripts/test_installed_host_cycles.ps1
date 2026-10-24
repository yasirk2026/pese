param(
    [Parameter(Mandatory=$true)][string]$Brain,
    [Parameter(Mandatory=$true)][string]$EvidenceDirectory,
    [int]$Cycles = 10
)
$ErrorActionPreference = 'Stop'
$exe = Join-Path $env:LOCALAPPDATA 'ManiacSoftwares.PESE\current\PESE.exe'
New-Item -ItemType Directory -Force -Path $EvidenceDirectory | Out-Null
$results = @()
for ($cycle = 1; $cycle -le $Cycles; $cycle++) {
    $report = Join-Path $EvidenceDirectory "launch-$cycle.json"
    $arguments = @('--self-test', ('"' + $Brain + '"'), ('"' + $report + '"'), '1')
    $process = Start-Process -FilePath $exe -ArgumentList $arguments -PassThru -WindowStyle Hidden
    if (!$process.WaitForExit(150000)) { throw "Host launch $cycle timed out" }
    if ($process.ExitCode -ne 0) { throw "Host launch $cycle failed; inspect $report" }
    $detail = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if (!$detail.passed) { throw "Supervisor failure in launch $cycle" }
    $results += @{launch=$cycle;hostPid=$process.Id;hostExited=$process.HasExited;supervisorPassed=$detail.passed}
}
@{passed=$true;launches=$results} | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $EvidenceDirectory 'launch-exit-summary.json')
Write-Output "$Cycles installed host launch/exit cycles passed."
