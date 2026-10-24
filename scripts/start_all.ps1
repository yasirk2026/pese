# PESE: Start Python Engine and Next.js Web Frontend in parallel
Write-Host "=====================================================" -ForegroundColor Magenta
Write-Host " 😈 LAUNCHING PESE: PERSONAL EVIL SEARCH ENGINE 😈  " -ForegroundColor Magenta
Write-Host "=====================================================" -ForegroundColor Magenta

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "Launching Python API service (http://localhost:8000)..." -ForegroundColor Yellow
$engineProcess = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-File", "$ScriptDir\start_engine.ps1" -PassThru

Start-Sleep -Seconds 2

Write-Host "Launching Next.js Web service (http://localhost:3000)..." -ForegroundColor Green
$webProcess = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-File", "$ScriptDir\start_web.ps1" -PassThru

Write-Host "All PESE services launched!" -ForegroundColor Cyan
Write-Host "  Search Engine UI:  http://localhost:3000"
Write-Host "  Search Engine API: http://localhost:8000"
Write-Host "  API Docs (Swagger):http://localhost:8000/docs"
