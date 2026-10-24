# PESE: Run Evaluation Benchmark
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

& "$ProjectRoot\engine\.venv\Scripts\python.exe" -m engine.evaluation.runner
