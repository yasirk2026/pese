# PESE: Start Python Search Engine API
Write-Host "Starting PESE Python Search Engine on http://localhost:8000..." -ForegroundColor Magenta

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

& "$ProjectRoot\engine\.venv\Scripts\python.exe" -m uvicorn engine.api.main:app --host 127.0.0.1 --port 8000 --reload
