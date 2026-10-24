# PESE: Start Next.js Frontend
Write-Host "Starting PESE Next.js Frontend on http://localhost:3000..." -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location "$ProjectRoot\web"

npm run dev
