Write-Host "Running PESE Phase 2A Discovery Benchmark..." -ForegroundColor Cyan
$env:PYTHONPATH = (Get-Item -Path "$PSScriptRoot\..").FullName
& "$PSScriptRoot\..\engine\.venv\Scripts\python.exe" -m engine.evaluation.discovery_runner
